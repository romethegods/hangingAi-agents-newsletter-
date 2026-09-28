"""Persist parsed items: canonicalize -> exact dedup -> near-dup detection -> upsert."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Tool, ToolStarSnapshot
from app.ranking import star_velocity
from app.scraping.canonical import canonicalize_url, url_hash
from app.scraping.minhash import MinHashLSH, minhash
from app.scraping.types import RawItem, RawTool

NEAR_DUP_LOOKBACK = timedelta(days=3)
VELOCITY_WINDOW = timedelta(days=7)


@dataclass(slots=True)
class IngestStats:
    inserted: int = 0
    updated: int = 0
    near_duplicates: int = 0
    tools_upserted: int = 0

    def __str__(self) -> str:
        return (
            f"inserted={self.inserted} updated={self.updated} "
            f"near_dups={self.near_duplicates} tools={self.tools_upserted}"
        )


async def _recent_signatures(session: AsyncSession, since: datetime) -> MinHashLSH:
    index = MinHashLSH()
    rows = await session.execute(
        select(Article.id, Article.minhash).where(
            Article.fetched_at >= since,
            Article.duplicate_of_id.is_(None),
            Article.minhash.is_not(None),
        )
    )
    for article_id, signature in rows:
        index.add(article_id, signature)
    return index


async def save_items(
    session: AsyncSession, source_id: int, items: list[RawItem], now: datetime, stats: IngestStats
) -> None:
    # Exact dedup inside the batch (the same story often appears twice on one page).
    batch: dict[str, tuple[str, RawItem]] = {}
    for item in items:
        canonical = canonicalize_url(item.url)
        batch.setdefault(url_hash(canonical), (canonical, item))
    if not batch:
        return

    index = await _recent_signatures(session, now - NEAR_DUP_LOOKBACK)
    for digest, (canonical, item) in batch.items():
        signature = minhash(item.title)  # headlines: summaries vary too much across outlets
        values = {
            "source_id": source_id,
            "url": item.url,
            "url_canonical": canonical,
            "url_hash": digest,
            "title": item.title,
            "summary": item.summary,
            "author": item.author,
            "image_url": item.image_url,
            "content_type": item.content_type.value,
            "published_at": item.published_at or now,
            "fetched_at": now,
            "engagement": item.engagement,
            "minhash": signature,
            "duplicate_of_id": index.find_near(signature) if signature else None,
            "extra": item.extra,
        }
        stmt = insert(Article).values(**values)
        # Already stored: refresh the fields that change over time (likes, summary edits).
        stmt = stmt.on_conflict_do_update(
            index_elements=[Article.url_hash],
            set_={
                "title": stmt.excluded.title,
                "summary": stmt.excluded.summary,
                "engagement": stmt.excluded.engagement,
                "extra": stmt.excluded.extra,
            },
        ).returning(Article.id, literal_column("(xmax = 0)").label("inserted"))
        article_id, inserted = (await session.execute(stmt)).one()

        if not inserted:
            stats.updated += 1
        elif values["duplicate_of_id"] is not None:
            stats.near_duplicates += 1
        else:
            stats.inserted += 1
            if signature:
                index.add(article_id, signature)


async def save_tools(
    session: AsyncSession, tools: list[RawTool], now: datetime, stats: IngestStats
) -> None:
    by_name = {t.full_name.lower(): t for t in tools}
    for tool in by_name.values():
        stmt = insert(Tool).values(
            full_name=tool.full_name,
            url=tool.url,
            description=tool.description,
            language=tool.language,
            stars=tool.stars,
            forks=tool.forks,
            topics=tool.topics,
            pushed_at=tool.pushed_at,
            first_seen_at=now,
            last_seen_at=now,
        )
        # Different pages expose different fields; don't erase what another page gave us.
        stmt = stmt.on_conflict_do_update(
            index_elements=[Tool.full_name],
            set_={
                "description": stmt.excluded.description,
                "language": stmt.excluded.language,
                "stars": stmt.excluded.stars,
                "forks": _coalesce(stmt.excluded.forks, Tool.forks),
                "topics": _coalesce(_nullif_empty(stmt.excluded.topics), Tool.topics),
                "pushed_at": _coalesce(stmt.excluded.pushed_at, Tool.pushed_at),
                "last_seen_at": stmt.excluded.last_seen_at,
            },
        ).returning(Tool.id)
        tool_id = (await session.execute(stmt)).scalar_one()

        await session.execute(
            insert(ToolStarSnapshot)
            .values(tool_id=tool_id, captured_at=now, stars=tool.stars)
            .on_conflict_do_nothing()
        )
        history = await session.execute(
            select(ToolStarSnapshot.captured_at, ToolStarSnapshot.stars)
            .where(
                ToolStarSnapshot.tool_id == tool_id,
                ToolStarSnapshot.captured_at >= now - VELOCITY_WINDOW,
            )
            .order_by(ToolStarSnapshot.captured_at)
        )
        snapshots = [(captured_at, stars) for captured_at, stars in history]
        stars_today = float(tool.stars_today) if tool.stars_today is not None else None
        velocity = star_velocity(snapshots, now, window=VELOCITY_WINDOW, fallback=stars_today)
        if velocity is not None:
            await session.execute(
                update(Tool).where(Tool.id == tool_id).values(star_velocity=velocity)
            )
        stats.tools_upserted += 1


def _coalesce(*args):
    return func.coalesce(*args)


def _nullif_empty(array_expr):
    return func.nullif(array_expr, literal_column("'{}'::varchar[]"))
