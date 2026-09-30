import base64
import math
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_limits import KeyedRateLimiter, Tier, is_exempt, parse_networks
from app.config import get_settings
from app.db import engine, get_session
from app.models import Article, Source, Tool
from app.ranking import diversified_top_k, hot_score
from app.schemas import (
    ArticleDetail,
    ArticleOut,
    FeedPage,
    SourceStatus,
    ToolOut,
    ToolPage,
    TopicCount,
)
from app.scraping.types import ContentType, Platform

HOT_WINDOW = timedelta(hours=72)
# Trending models keep trending for weeks after their last commit, unlike news.
HOT_WINDOW_BY_TYPE = {ContentType.MODEL: timedelta(days=21)}
HOT_CANDIDATES = 500

Session = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="HangingAi API", version="0.1.0", lifespan=lifespan)
_settings = get_settings()
app.state.rate_limiter = KeyedRateLimiter()
app.state.rate_limit_exempt = parse_networks(_settings.rate_limit_exempt_networks)
DEFAULT_TIER = Tier("api", _settings.rate_limit_per_minute, _settings.rate_limit_burst)
SEARCH_TIER = Tier(
    "search", _settings.rate_limit_search_per_minute, _settings.rate_limit_search_burst
)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    path = request.url.path
    client = request.client.host if request.client else None
    if (
        not _settings.rate_limit_enabled
        or not path.startswith("/api/")
        or is_exempt(client, request.app.state.rate_limit_exempt)
    ):
        return await call_next(request)

    tier = SEARCH_TIER if path == "/api/search" else DEFAULT_TIER
    decision = request.app.state.rate_limiter.check(client or "unknown", tier)
    if not decision.allowed:
        return JSONResponse(
            {"detail": "rate limit exceeded", "retry_after": decision.retry_after},
            status_code=429,
            headers=decision.headers(),
        )
    response = await call_next(request)
    response.headers.update(decision.headers())
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


class FeedSort(StrEnum):
    LATEST = "latest"
    HOT = "hot"


class ToolSort(StrEnum):
    TRENDING = "trending"
    STARS = "stars"
    NEW = "new"


def _encode_cursor(published_at: datetime, article_id: int) -> str:
    return base64.urlsafe_b64encode(f"{published_at.isoformat()}|{article_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        stamp, article_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), int(article_id)
    except ValueError as exc:
        raise HTTPException(400, "invalid cursor") from exc


@app.get("/health")
async def health(session: Session) -> dict:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/feed", response_model=FeedPage)
async def feed(
    session: Session,
    sort: FeedSort = FeedSort.LATEST,
    content_type: ContentType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> FeedPage:
    query = select(Article).where(Article.duplicate_of_id.is_(None))
    if content_type:
        query = query.where(Article.content_type == content_type.value)

    if sort is FeedSort.HOT:
        now = datetime.now(UTC)
        candidates = (
            (
                await session.execute(
                    query.where(
                        Article.published_at
                        >= now - HOT_WINDOW_BY_TYPE.get(content_type, HOT_WINDOW)
                    )
                    .order_by(Article.published_at.desc())
                    .limit(HOT_CANDIDATES)
                )
            )
            .scalars()
            .all()
        )
        ranked = diversified_top_k(
            candidates,
            limit,
            key=lambda a: hot_score(
                a.published_at, now, source_weight=a.source.weight, engagement=a.engagement
            ),
            group=lambda a: a.content_type,
            max_per_group=max(1, math.ceil(limit / 2)),
        )
        return FeedPage(items=ranked)

    # Keyset pagination: stable under inserts and O(limit) at any depth, unlike OFFSET.
    if cursor:
        query = query.where(tuple_(Article.published_at, Article.id) < _decode_cursor(cursor))
    rows = (
        (
            await session.execute(
                query.order_by(Article.published_at.desc(), Article.id.desc()).limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    page, more = rows[:limit], len(rows) > limit
    return FeedPage(
        items=page, next_cursor=_encode_cursor(page[-1].published_at, page[-1].id) if more else None
    )


@app.get("/api/articles/{article_id}", response_model=ArticleDetail)
async def article(article_id: int, session: Session) -> ArticleDetail:
    found = await session.get(Article, article_id)
    if found is None:
        raise HTTPException(404, "article not found")
    # Near-duplicates point at one canonical article; gather the whole cluster.
    root = found.duplicate_of_id or found.id
    coverage = await session.execute(
        select(Article)
        .where(or_(Article.id == root, Article.duplicate_of_id == root), Article.id != found.id)
        .order_by(Article.published_at)
    )
    detail = ArticleDetail.model_validate(found)
    detail.coverage = [ArticleOut.model_validate(a) for a in coverage.scalars()]
    return detail


@app.get("/api/search", response_model=list[ArticleOut])
async def search(
    session: Session,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[Article]:
    ts_query = func.websearch_to_tsquery("english", q)
    rank = func.ts_rank_cd(Article.search_tsv, ts_query)
    rows = await session.execute(
        select(Article)
        .where(Article.search_tsv.op("@@")(ts_query), Article.duplicate_of_id.is_(None))
        .order_by(rank.desc(), Article.published_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


@app.get("/api/tools", response_model=ToolPage)
async def tools(
    session: Session,
    sort: ToolSort = ToolSort.TRENDING,
    platform: Platform | None = None,
    topic: str | None = None,
    language: str | None = None,
    has_demo: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> ToolPage:
    query = select(Tool)
    if platform:
        query = query.where(Tool.platform == platform.value)
    if topic:
        query = query.where(Tool.topics.contains([topic.lower()]))
    if language:
        query = query.where(func.lower(Tool.language) == language.lower())
    if has_demo:
        query = query.where(Tool.demo_url.is_not(None))
    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    order = {
        ToolSort.TRENDING: (Tool.star_velocity.desc(), Tool.stars.desc()),
        ToolSort.STARS: (Tool.stars.desc(),),
        ToolSort.NEW: (Tool.first_seen_at.desc(), Tool.stars.desc()),
    }[sort]
    rows = await session.execute(query.order_by(*order, Tool.id).limit(limit).offset(offset))
    return ToolPage(items=[ToolOut.model_validate(t) for t in rows.scalars()], total=total)


@app.get("/api/tools/{tool_id}", response_model=ToolOut)
async def tool(tool_id: int, session: Session) -> Tool:
    found = await session.get(Tool, tool_id)
    if found is None:
        raise HTTPException(404, "tool not found")
    return found


@app.get("/api/topics", response_model=list[TopicCount])
async def topics(
    session: Session, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[TopicCount]:
    """Most common GitHub topics across tracked tools, for the directory's filter chips."""
    topic = select(func.unnest(Tool.topics).label("topic")).subquery()
    rows = await session.execute(
        select(topic.c.topic, func.count().label("count"))
        .group_by(topic.c.topic)
        .order_by(func.count().desc(), topic.c.topic)
        .limit(limit)
    )
    return [TopicCount(topic=t, count=c) for t, c in rows]


@app.get("/api/sources", response_model=list[SourceStatus])
async def sources(session: Session) -> list[Source]:
    return list((await session.execute(select(Source).order_by(Source.slug))).scalars())
