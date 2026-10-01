"""Compose a user's daily brief.

Four sections, each personal when the user follows things and sensible when
they don't yet:

1. Your stack:     new releases of tools they follow, since their last brief.
2. Rising:         fastest-growing tools in their topics (or their tools' topics),
                   excluding what they already follow.
3. Must-reads:     up to 3 hot stories on their topics ("for you"), then the
                   day's best general stories.
4. Demo to try:    one trending tool with a playable demo.

Nothing that appeared in their last week of briefs repeats.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Brief, BriefItem, Follow, Tool, ToolRelease, User
from app.ranking import diversified_top_k, hot_score

DEDUPE_WINDOW = timedelta(days=7)


def _kind(row) -> str:
    return row[0].content_type


RELEASE_LOOKBACK_MAX = timedelta(days=7)  # after a long break, don't dump a month of releases
RELEASE_LOOKBACK_MIN = timedelta(hours=26)  # daily cadence plus slack
READS_WINDOW = timedelta(hours=36)
READS = 5
MAX_MATCHED = 3  # "for you" stories; the rest of the reads stay general
PLAYABLE_DEMOS = ("video", "embed", "gif", "app")


@dataclass(slots=True)
class BriefContent:
    releases: list[ToolRelease] = field(default_factory=list)
    rising: list[Tool] = field(default_factory=list)
    reads: list[Article] = field(default_factory=list)
    demo: Tool | None = None
    followed_topics: list[str] = field(default_factory=list)
    matched_article_ids: set[int] = field(default_factory=set)  # reads that matched their topics
    personalized: bool = False

    def items(self) -> list[tuple[str, int]]:
        """(kind, id) pairs to record, so they don't repeat next week."""
        pairs = [("release", r.id) for r in self.releases]
        pairs += [("tool", t.id) for t in self.rising]
        pairs += [("article", a.id) for a in self.reads]
        if self.demo:
            pairs.append(("tool", self.demo.id))
        return pairs

    @property
    def is_empty(self) -> bool:
        return not (self.releases or self.rising or self.reads or self.demo)


async def _recently_sent(
    session: AsyncSession, user_id: int, since: datetime
) -> set[tuple[str, int]]:
    rows = await session.execute(
        select(BriefItem.kind, BriefItem.ref_id)
        .join(Brief, Brief.id == BriefItem.brief_id)
        .where(Brief.user_id == user_id, Brief.status == "sent", Brief.sent_at >= since)
    )
    return {(kind, ref_id) for kind, ref_id in rows}


def _topic_query(topics: list[str]):
    """OR-query over topic words: 'ai-agents' also matches stories about 'agents'."""
    words = sorted({w for t in topics for w in t.replace("-", " ").split() if len(w) > 2})
    return func.websearch_to_tsquery("english", " OR ".join(words)) if words else None


async def compose_brief(session: AsyncSession, user: User, now: datetime) -> BriefContent:
    follows = (
        await session.execute(select(Follow.kind, Follow.target).where(Follow.user_id == user.id))
    ).all()
    tool_ids = {int(t) for k, t in follows if k == "tool" and t.isdigit()}
    topics = sorted({t for k, t in follows if k == "topic"})
    seen = await _recently_sent(session, user.id, now - DEDUPE_WINDOW)
    brief = BriefContent(followed_topics=topics, personalized=bool(tool_ids or topics))

    # 1. Releases since the last brief (bounded both ways).
    if tool_ids:
        last_sent = await session.scalar(
            select(func.max(Brief.sent_at)).where(Brief.user_id == user.id, Brief.status == "sent")
        )
        since = max(now - RELEASE_LOOKBACK_MAX, min(last_sent or now, now - RELEASE_LOOKBACK_MIN))
        releases = await session.execute(
            select(ToolRelease)
            .where(ToolRelease.tool_id.in_(tool_ids), ToolRelease.published_at >= since)
            .order_by(ToolRelease.published_at.desc())
            .limit(12)
        )
        brief.releases = [r for r in releases.scalars() if ("release", r.id) not in seen][:6]

    # 2. Rising tools: in followed topics, else the followed tools' own topics, else everything.
    interest = topics
    if not interest and tool_ids:
        own = await session.execute(select(Tool.topics).where(Tool.id.in_(tool_ids)))
        interest = sorted({t for row in own.scalars() for t in row})
    rising = select(Tool).where(Tool.star_velocity > 0)
    if interest:
        rising = rising.where(Tool.topics.overlap(interest))
    if tool_ids:
        rising = rising.where(Tool.id.not_in(tool_ids))
    candidates = await session.execute(rising.order_by(Tool.star_velocity.desc()).limit(20))
    brief.rising = [t for t in candidates.scalars() if ("tool", t.id) not in seen][:3]

    # 3. Must-reads: hot score, boosted by topic match, diversified across content types.
    matches = _topic_query(interest)
    match_column = (
        (Article.search_tsv.op("@@")(matches)).label("match") if matches is not None else None
    )
    reads_query = select(Article, *([match_column] if match_column is not None else [])).where(
        Article.duplicate_of_id.is_(None), Article.published_at >= now - READS_WINDOW
    )
    rows = (
        await session.execute(reads_query.order_by(Article.published_at.desc()).limit(300))
    ).all()

    def score(row) -> float:
        article = row[0]
        return hot_score(
            article.published_at,
            now,
            source_weight=article.source.weight,
            engagement=article.engagement,
        )

    fresh = [row for row in rows if ("article", row[0].id) not in seen]
    # Stories on the reader's topics come first (up to MAX_MATCHED), then the day's best
    # general stories fill the rest, so the brief is personal without becoming an echo chamber.
    matched = [row for row in fresh if match_column is not None and row[1]]
    picked = diversified_top_k(matched, MAX_MATCHED, key=score, group=_kind, max_per_group=2)
    picked_ids = {row[0].id for row in picked}
    general = [row for row in fresh if row[0].id not in picked_ids]
    picked += diversified_top_k(
        general, READS - len(picked), key=score, group=_kind, max_per_group=2
    )
    brief.reads = [row[0] for row in picked]
    brief.matched_article_ids = {row[0].id for row in picked if match_column is not None and row[1]}

    # 4. One demo to try.
    shown = {t.id for t in brief.rising} | tool_ids
    demo = await session.execute(
        select(Tool)
        .where(
            Tool.demo_kind.in_(PLAYABLE_DEMOS),
            or_(Tool.star_velocity > 0, Tool.platform == "huggingface"),
        )
        .order_by(Tool.star_velocity.desc(), Tool.stars.desc())
        .limit(20)
    )
    brief.demo = next(
        (t for t in demo.scalars() if t.id not in shown and ("tool", t.id) not in seen), None
    )
    return brief
