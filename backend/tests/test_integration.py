from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.db import get_session
from app.main import app
from app.models import Article, Source, Tool
from app.scraping.parsers.github import RepoMedia
from app.scraping.pipeline import (
    IngestStats,
    save_items,
    save_repo_media,
    save_tools,
    tools_needing_media,
)
from app.scraping.types import ContentType, Demo, DemoKind, Platform, RawItem, RawTool

NOW = datetime.now(UTC)


def news(url: str, title: str, hours_ago: float = 1, engagement: int | None = None) -> RawItem:
    return RawItem(
        url=url,
        title=title,
        content_type=ContentType.NEWS,
        published_at=NOW - timedelta(hours=hours_ago),
        engagement=engagement,
    )


@pytest.fixture
async def source_id(session_factory) -> int:
    async with session_factory() as session, session.begin():
        source = Source(slug="test", name="Test", url="https://test.com", weight=1.0)
        session.add(source)
    return source.id


@pytest.fixture
async def client(session_factory):
    async def override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def ingest(session_factory, source_id: int, items: list[RawItem]) -> IngestStats:
    stats = IngestStats()
    async with session_factory() as session, session.begin():
        await save_items(session, source_id, items, NOW, stats)
    return stats


async def test_exact_duplicates_collapse_and_reingest_updates(session_factory, source_id) -> None:
    items = [
        news("https://site.com/a?utm_source=x", "OpenAI ships a new agent SDK"),
        news("http://www.site.com/a/", "OpenAI ships a new agent SDK"),  # same URL, canonicalized
        news("https://site.com/b", "Anthropic publishes interpretability research", engagement=5),
    ]
    first = await ingest(session_factory, source_id, items)
    assert (first.inserted, first.updated) == (2, 0)

    second = await ingest(
        session_factory,
        source_id,
        [
            news(
                "https://site.com/b", "Anthropic publishes interpretability research", engagement=50
            )
        ],
    )
    assert (second.inserted, second.updated) == (0, 1)
    async with session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Article))).scalar_one() == 2
        b = (
            await session.execute(
                select(Article).where(Article.url_canonical == "https://site.com/b")
            )
        ).scalar_one()
        assert b.engagement == 50


async def test_near_duplicate_headlines_are_linked_not_shown_twice(
    session_factory, source_id, client
) -> None:
    await ingest(
        session_factory,
        source_id,
        [
            news(
                "https://a.com/1",
                "Nvidia unveils new AI chip for data centers at annual developer conference",
            )
        ],
    )
    stats = await ingest(
        session_factory,
        source_id,
        [
            news(
                "https://b.com/2",
                "Nvidia unveils new AI chip for data centers at annual developer conference today",
            )
        ],
    )
    assert stats.near_duplicates == 1

    feed = (await client.get("/api/feed")).json()
    assert [a["url"] for a in feed["items"]] == ["https://a.com/1"]

    # Either copy's detail page lists the other as coverage.
    original = (await client.get(f"/api/articles/{feed['items'][0]['id']}")).json()
    assert [c["url"] for c in original["coverage"]] == ["https://b.com/2"]
    copy = (await client.get(f"/api/articles/{original['coverage'][0]['id']}")).json()
    assert copy["duplicate_of_id"] == original["id"]
    assert [c["url"] for c in copy["coverage"]] == ["https://a.com/1"]
    assert (await client.get("/api/articles/999999")).status_code == 404


async def test_feed_keyset_pagination_covers_every_item_once(
    session_factory, source_id, client
) -> None:
    await ingest(
        session_factory,
        source_id,
        [
            news(
                f"https://site.com/{i}",
                f"Distinct story number {i} about topic {i * 7}",
                hours_ago=i,
            )
            for i in range(7)
        ],
    )
    seen, cursor = [], None
    while True:
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        page = (await client.get("/api/feed", params=params)).json()
        seen += [a["url"] for a in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert seen == [f"https://site.com/{i}" for i in range(7)]  # newest first, no gaps or repeats


async def test_hot_feed_and_search(session_factory, source_id, client) -> None:
    await ingest(
        session_factory,
        source_id,
        [
            news(
                "https://site.com/old",
                "Old but popular diffusion model story",
                hours_ago=60,
                engagement=10_000,
            ),
            news(
                "https://site.com/new",
                "Fresh open-source agent framework launches",
                hours_ago=1,
                engagement=10,
            ),
        ],
    )
    hot = (await client.get("/api/feed", params={"sort": "hot"})).json()["items"]
    assert hot[0]["url"] == "https://site.com/new"

    results = (await client.get("/api/search", params={"q": "diffusion"})).json()
    assert [r["url"] for r in results] == ["https://site.com/old"]
    assert (await client.get("/api/search", params={"q": "x"})).status_code == 422


async def test_tools_upsert_keeps_fields_and_ranks_by_velocity(session_factory, client) -> None:
    async with session_factory() as session, session.begin():
        stats = IngestStats()
        await save_tools(
            session,
            [
                RawTool(
                    "acme/agent",
                    "An agent framework",
                    "Python",
                    stars=500,
                    topics=["ai-agents"],
                    pushed_at=NOW,
                ),
                RawTool("acme/rocket", "Fast inference", "Rust", stars=9000, stars_today=5),
            ],
            NOW,
            stats,
        )
        # Trending page: has stars_today but no topics; must not wipe the topics we already have.
        await save_tools(
            session,
            [RawTool("acme/agent", "An agent framework", "Python", stars=520, stars_today=300)],
            NOW + timedelta(seconds=1),
            stats,
        )

    async with session_factory() as session:
        agent = (
            await session.execute(select(Tool).where(Tool.full_name == "acme/agent"))
        ).scalar_one()
        assert agent.stars == 520 and agent.topics == ["ai-agents"] and agent.pushed_at is not None

    trending = (await client.get("/api/tools")).json()
    assert [t["full_name"] for t in trending["items"]] == ["acme/agent", "acme/rocket"]
    by_topic = (await client.get("/api/tools", params={"topic": "ai-agents"})).json()
    assert by_topic["total"] == 1
    assert (await client.get("/api/topics")).json() == [{"topic": "ai-agents", "count": 1}]


async def test_tool_demos_platforms_and_scan_queue(session_factory, client) -> None:
    space = RawTool(
        "acme/agent",  # same name as a GitHub repo: platforms keep them apart
        "Try the agent live",
        stars=40,
        platform=Platform.HUGGINGFACE,
        title="🤖 Acme Agent",
        preview_image_url="https://cdn/spaces/acme/agent.png",
        demo=Demo("https://acme-agent.hf.space", DemoKind.APP),
    )
    repos = [
        RawTool("acme/agent", "An agent framework", "Python", stars=500),
        RawTool("acme/quiet", "Low activity repo", "Go", stars=10),
    ]
    async with session_factory() as session, session.begin():
        await save_tools(session, [*repos, space], NOW, IngestStats())

    # Only GitHub tools are queued for README scans, never-scanned first.
    async with session_factory() as session, session.begin():
        queue = await tools_needing_media(session, NOW, limit=10)
        assert {t.full_name for t in queue} == {"acme/agent", "acme/quiet"}
        assert all(t.platform == "github" for t in queue)
        agent = next(t for t in queue if t.full_name == "acme/agent")
        demo = Demo("https://github.com/user-attachments/assets/abc", DemoKind.VIDEO)
        await save_repo_media(session, agent.id, RepoMedia("https://og/acme", demo), NOW)
        quiet = next(t for t in queue if t.full_name == "acme/quiet")
        await save_repo_media(session, quiet.id, RepoMedia(None, None), NOW)  # nothing found

    async with session_factory() as session, session.begin():
        assert await tools_needing_media(session, NOW, limit=10) == []  # both scanned this week
        assert len(await tools_needing_media(session, NOW + timedelta(days=8), limit=10)) == 2
        # A later listing crawl (no media on the page) must not wipe the scanned demo.
        await save_tools(session, [repos[0]], NOW + timedelta(hours=1), IngestStats())

    with_demo = (await client.get("/api/tools", params={"has_demo": "true"})).json()
    assert {(t["platform"], t["full_name"], t["demo_kind"]) for t in with_demo["items"]} == {
        ("github", "acme/agent", "video"),
        ("huggingface", "acme/agent", "app"),
    }
    spaces = (await client.get("/api/tools", params={"platform": "huggingface"})).json()
    assert [t["title"] for t in spaces["items"]] == ["🤖 Acme Agent"]
    detail = (await client.get(f"/api/tools/{spaces['items'][0]['id']}")).json()
    assert detail["url"] == "https://huggingface.co/spaces/acme/agent"
    assert detail["demo_url"] == "https://acme-agent.hf.space"
    assert (await client.get("/api/tools/999999")).status_code == 404
    assert (await client.get("/api/tools", params={"platform": "gitlab"})).status_code == 422


async def test_recrawl_fills_in_missing_images(session_factory, source_id) -> None:
    await ingest(
        session_factory, source_id, [news("https://site.com/img", "A story without art yet")]
    )
    later = news("https://site.com/img", "A story without art yet")
    later.image_url = "https://cdn/site/img.jpg"
    await ingest(session_factory, source_id, [later])
    async with session_factory() as session:
        stored = (await session.execute(select(Article))).scalar_one()
        assert stored.image_url == "https://cdn/site/img.jpg"


async def test_hot_models_tab_looks_back_further_than_news(
    session_factory, source_id, client
) -> None:
    model = RawItem(
        url="https://huggingface.co/acme/older-model",
        title="acme/older-model",
        content_type=ContentType.MODEL,
        published_at=NOW - timedelta(days=10),  # still trending, last commit 10 days ago
        engagement=500,
    )
    await ingest(session_factory, source_id, [model])
    models = (await client.get("/api/feed", params={"sort": "hot", "content_type": "model"})).json()
    assert [a["title"] for a in models["items"]] == ["acme/older-model"]
    mixed = (await client.get("/api/feed", params={"sort": "hot"})).json()
    assert mixed["items"] == []  # the front page stays about the last 72 hours


async def test_reader_upvotes_lift_a_story_in_the_hot_feed(
    session_factory, source_id, client
) -> None:
    from app.models import User, Vote

    await ingest(
        session_factory,
        source_id,
        [
            news("https://site.com/a", "Slightly fresher story nobody voted on", hours_ago=1),
            news("https://site.com/b", "Story readers love and upvoted heavily", hours_ago=3),
        ],
    )
    async with session_factory() as session, session.begin():
        b = (
            await session.execute(
                select(Article).where(Article.url_canonical == "https://site.com/b")
            )
        ).scalar_one()
        session.add_all([User(handle=f"hanging-{2000 + i}") for i in range(10)])
    async with session_factory() as session, session.begin():
        users = (await session.execute(select(User.id))).scalars().all()
        session.add_all([Vote(user_id=u, target_kind="article", target_id=b.id) for u in users])
    hot = (await client.get("/api/feed", params={"sort": "hot"})).json()["items"]
    assert [a["url"] for a in hot][:2] == ["https://site.com/b", "https://site.com/a"]
    assert hot[0]["votes"] == 10
