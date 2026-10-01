"""Scrape worker.

python -m app.worker                 # run forever on each source's schedule
python -m app.worker --once          # crawl every enabled source once, then exit
python -m app.worker --once --source hf-papers
python -m app.worker --media         # only scan GitHub READMEs for demos
python -m app.worker --releases      # only check followed tools for new releases
python -m app.worker --briefs        # send daily briefs that are due (no browser)
"""

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

import nodriver
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.brief_delivery import send_due_briefs
from app.config import get_settings
from app.db import SessionLocal
from app.email import get_sender
from app.models import Source
from app.scraping.browser import BrowserPool
from app.scraping.crawler import BlockedPage, Crawler, CrawlError, DisallowedByRobots
from app.scraping.parsers.github import parse_releases, parse_repo_media
from app.scraping.pipeline import (
    IngestStats,
    save_items,
    save_releases,
    save_repo_media,
    save_tools,
    tools_needing_media,
    tools_needing_releases,
)
from app.scraping.rate_limit import DomainRateLimiter
from app.scraping.registry import SOURCES, SOURCES_BY_SLUG, SourceDef
from app.scraping.relevance import is_ai_related, is_safe_for_work
from app.scraping.robots import RobotsCache
from app.scraping.scheduler import CrawlScheduler
from app.scraping.types import RawItem, RawTool

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


def _keep_item(item: RawItem, sdef: SourceDef) -> bool:
    return is_ai_related(item.title, item.summary, mode=sdef.ai_filter) and is_safe_for_work(
        item.title, item.summary
    )


def _keep_tool(tool: RawTool, sdef: SourceDef) -> bool:
    text = (tool.full_name, tool.title, tool.description, " ".join(tool.topics))
    return is_ai_related(*text, mode=sdef.ai_filter) and is_safe_for_work(*text, tags=tool.tags)


MEDIA_JOB = "github-readme-media"
MEDIA_BATCH = 20  # repo pages per run; hourly runs cover ~480 repos/day at ~2s/page


async def scan_readme_media(crawler: Crawler, batch: int = MEDIA_BATCH) -> int:
    """Load a batch of GitHub repo pages and record each README's best demo."""
    async with SessionLocal() as session:
        queue = await tools_needing_media(session, datetime.now(UTC), batch)
    found = 0
    for tool in queue:
        try:
            html = await crawler.get(tool.url)
        except (DisallowedByRobots, BlockedPage) as exc:
            log.warning("readme scan stopped at %s: %s", tool.full_name, exc)
            break  # GitHub-wide problem; the rest of the batch would fail the same way
        except Exception as exc:
            log.warning("readme scan failed for %s: %s", tool.full_name, exc)
            continue
        media = parse_repo_media(html, tool.url)
        found += media.demo is not None
        async with SessionLocal() as session, session.begin():
            await save_repo_media(session, tool.id, media, datetime.now(UTC))
    log.info("%s ok: scanned=%d demos=%d", MEDIA_JOB, len(queue), found)
    return found


RELEASES_JOB = "github-releases"
RELEASES_BATCH = 20
BRIEFS_JOB = "daily-briefs"


async def scan_releases(crawler: Crawler, batch: int = RELEASES_BATCH) -> int:
    """Check the releases page of followed GitHub tools that are due."""
    async with SessionLocal() as session:
        queue = await tools_needing_releases(session, datetime.now(UTC), batch)
    new = 0
    for tool in queue:
        url = f"{tool.url}/releases"
        try:
            html = await crawler.get(url)
        except (DisallowedByRobots, BlockedPage) as exc:
            log.warning("release scan stopped at %s: %s", tool.full_name, exc)
            break
        except Exception as exc:
            log.warning("release scan failed for %s: %s", tool.full_name, exc)
            continue
        async with SessionLocal() as session, session.begin():
            new += await save_releases(
                session, tool.id, parse_releases(html, url), datetime.now(UTC)
            )
    log.info("%s ok: scanned=%d new_releases=%d", RELEASES_JOB, len(queue), new)
    return new


async def send_briefs() -> None:
    stats = await send_due_briefs(SessionLocal, get_sender(), datetime.now(UTC))
    log.info(
        "%s ok: sent=%d failed=%d skipped=%d", BRIEFS_JOB, stats.sent, stats.failed, stats.skipped
    )


async def crawl_source(crawler: Crawler, sdef: SourceDef, source_id: int) -> IngestStats:
    now = datetime.now(UTC)
    try:
        html = await crawler.get(sdef.url)
        parsed = sdef.parser(html, sdef.url)
        if not len(parsed):
            raise EmptyParse(f"{sdef.slug}: parser found 0 items; markup may have changed")

        items = [i for i in parsed.items if _keep_item(i, sdef)]
        tools = [t for t in parsed.tools if _keep_tool(t, sdef)]
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
        if not slugs:  # a full run also refreshes tool demos and followed tools' releases
            await scan_readme_media(crawler)
            await scan_releases(crawler)
    finally:
        browser.stop()
    return 1 if failures else 0


async def run_media_once() -> int:
    browser = _browser_from_settings()
    await browser.start()
    try:
        await scan_readme_media(_build_crawler(browser))
    finally:
        browser.stop()
    return 0


async def run_releases_once() -> int:
    browser = _browser_from_settings()
    await browser.start()
    try:
        await scan_releases(_build_crawler(browser))
    finally:
        browser.stop()
    return 0


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
    # After the first tool crawls have landed, then hourly.
    scheduler.add(MEDIA_JOB, 3600, mono_now + 120)
    scheduler.add(RELEASES_JOB, 1800, mono_now + 180)
    scheduler.add(BRIEFS_JOB, 600, mono_now + 30)  # checks each user's local brief hour

    browser = _browser_from_settings()
    await browser.start()
    crawler = _build_crawler(browser)

    async def run_one(slug: str) -> None:
        try:
            if slug == MEDIA_JOB:
                await scan_readme_media(crawler)
            elif slug == RELEASES_JOB:
                await scan_releases(crawler)
            elif slug == BRIEFS_JOB:
                await send_briefs()
            else:
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
    parser.add_argument(
        "--media", action="store_true", help="only scan GitHub READMEs for demos, then exit"
    )
    parser.add_argument(
        "--releases", action="store_true", help="only check followed tools for releases, then exit"
    )
    parser.add_argument(
        "--briefs", action="store_true", help="send any daily briefs that are due, then exit"
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("nodriver", "uc", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # nodriver manages its own event loop; asyncio.run() leaves Chrome's pipes dangling on exit.
    loop = nodriver.loop()
    if args.media:
        raise SystemExit(loop.run_until_complete(run_media_once()))
    if args.releases:
        raise SystemExit(loop.run_until_complete(run_releases_once()))
    if args.briefs:
        loop.run_until_complete(send_briefs())  # no browser needed
        raise SystemExit(0)
    if args.once:
        raise SystemExit(loop.run_until_complete(run_once(args.source)))
    loop.run_until_complete(run_forever())


if __name__ == "__main__":
    main()
