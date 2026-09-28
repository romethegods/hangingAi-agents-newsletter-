"""Scrape worker.

python -m app.worker                 # run forever on each source's schedule
python -m app.worker --once          # crawl every enabled source once, then exit
python -m app.worker --once --source hf-papers
"""

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

import nodriver
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db import SessionLocal
from app.models import Source
from app.scraping.browser import BrowserPool
from app.scraping.crawler import Crawler, CrawlError
from app.scraping.pipeline import IngestStats, save_items, save_tools
from app.scraping.rate_limit import DomainRateLimiter
from app.scraping.registry import SOURCES, SOURCES_BY_SLUG, SourceDef
from app.scraping.relevance import is_ai_related
from app.scraping.robots import RobotsCache
from app.scraping.scheduler import CrawlScheduler

log = logging.getLogger("hangingai.worker")


class EmptyParse(CrawlError):
    """The page loaded but the parser found nothing: the site's markup probably changed."""


async def sync_sources() -> dict[str, Source]:
    """Upsert the code-defined registry into the sources table."""
    async with SessionLocal() as session, session.begin():
        for sdef in SOURCES:
            values = {
                "slug": sdef.slug,
                "name": sdef.name,
                "url": sdef.url,
                "weight": sdef.weight,
                "crawl_interval_minutes": sdef.interval_minutes,
                "enabled": sdef.enabled,
            }
            stmt = insert(Source).values(**values)
            await session.execute(
                stmt.on_conflict_do_update(index_elements=[Source.slug], set_=values)
            )
        rows = (await session.execute(select(Source))).scalars().all()
    return {row.slug: row for row in rows}


async def crawl_source(crawler: Crawler, sdef: SourceDef, source_id: int) -> IngestStats:
    now = datetime.now(UTC)
    try:
        html = await crawler.get(sdef.url)
        parsed = sdef.parser(html, sdef.url)
        if not len(parsed):
            raise EmptyParse(f"{sdef.slug}: parser found 0 items; markup may have changed")

        items = [i for i in parsed.items if is_ai_related(i.title, i.summary, mode=sdef.ai_filter)]
        tools = [
            t
            for t in parsed.tools
            if is_ai_related(t.full_name, t.description, " ".join(t.topics), mode=sdef.ai_filter)
        ]
        stats = IngestStats()
        async with SessionLocal() as session, session.begin():
            await save_items(session, source_id, items, now, stats)
            await save_tools(session, tools, now, stats)
            await session.execute(
                update(Source)
                .where(Source.id == source_id)
                .values(last_crawled_at=now, last_error=None, consecutive_failures=0)
            )
        log.info(
            "%s ok: parsed=%d kept=%d %s", sdef.slug, len(parsed), len(items) + len(tools), stats
        )
        return stats
    except Exception as exc:
        async with SessionLocal() as session, session.begin():
            await session.execute(
                update(Source)
                .where(Source.id == source_id)
                .values(
                    last_crawled_at=now,
                    last_error=f"{type(exc).__name__}: {exc}"[:2000],
                    consecutive_failures=Source.consecutive_failures + 1,
                )
            )
        raise


def _build_crawler(browser: BrowserPool) -> Crawler:
    settings = get_settings()
    return Crawler(browser, RobotsCache(), DomainRateLimiter(settings.scrape_min_interval_seconds))


def _browser_from_settings() -> BrowserPool:
    settings = get_settings()
    return BrowserPool(
        max_tabs=settings.browser_max_tabs,
        headless=settings.browser_headless,
        sandbox=settings.browser_sandbox,
        executable=settings.browser_executable,
    )


async def run_once(slugs: list[str] | None = None) -> int:
    rows = await sync_sources()
    targets = [SOURCES_BY_SLUG[s] for s in slugs] if slugs else [s for s in SOURCES if s.enabled]
    browser = _browser_from_settings()
    await browser.start()
    failures = 0
    try:
        crawler = _build_crawler(browser)
        results = await asyncio.gather(
            *(crawl_source(crawler, sdef, rows[sdef.slug].id) for sdef in targets),
            return_exceptions=True,
        )
        for sdef, result in zip(targets, results, strict=True):
            if isinstance(result, BaseException):
                failures += 1
                log.error("%s failed: %s", sdef.slug, result)
    finally:
        browser.stop()
    return 1 if failures else 0


async def run_forever() -> None:
    rows = await sync_sources()
    scheduler = CrawlScheduler()
    wall_now, mono_now = datetime.now(UTC), time.monotonic()
    for sdef in SOURCES:
        if not sdef.enabled:
            continue
        # Resume the schedule across restarts instead of re-crawling everything at boot.
        last = rows[sdef.slug].last_crawled_at
        interval = timedelta(minutes=sdef.interval_minutes)
        wait = max(0.0, ((last + interval) - wall_now).total_seconds()) if last else 0.0
        scheduler.add(sdef.slug, interval.total_seconds(), mono_now + wait)

    browser = _browser_from_settings()
    await browser.start()
    crawler = _build_crawler(browser)

    async def run_one(slug: str) -> None:
        try:
            await crawl_source(crawler, SOURCES_BY_SLUG[slug], rows[slug].id)
            succeeded = True
        except Exception as exc:
            log.error("%s failed: %s", slug, exc)
            succeeded = False
        next_run = scheduler.reschedule(slug, time.monotonic(), succeeded=succeeded)
        log.debug("%s next run in %.0fs", slug, next_run - time.monotonic())

    log.info("worker started with %d sources", len(scheduler))
    try:
        while True:
            due = scheduler.pop_due(time.monotonic())
            if due:
                await asyncio.gather(*(run_one(slug) for slug in due))
                continue
            await asyncio.sleep(min(60.0, scheduler.seconds_until_next(time.monotonic()) or 60.0))
    finally:
        browser.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="HangingAi scrape worker")
    parser.add_argument("--once", action="store_true", help="crawl once and exit")
    parser.add_argument(
        "--source", action="append", choices=sorted(SOURCES_BY_SLUG), help="limit to source(s)"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("nodriver", "uc", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # nodriver manages its own event loop; asyncio.run() leaves Chrome's pipes dangling on exit.
    loop = nodriver.loop()
    if args.once:
        raise SystemExit(loop.run_until_complete(run_once(args.source)))
    loop.run_until_complete(run_forever())


if __name__ == "__main__":
    main()
