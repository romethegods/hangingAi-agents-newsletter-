"""Accounts, follows, brief composition and delivery, against real Postgres."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, update

from app import auth, routes_account
from app.brief import compose_brief
from app.brief_delivery import build_message, is_due, send_due_briefs
from app.db import get_session
from app.email import Message
from app.main import app
from app.models import Brief, LoginToken, Source, Tool, User
from app.scraping.parsers.github import parse_releases
from app.scraping.pipeline import IngestStats, save_items, save_releases, save_tools
from app.scraping.types import ContentType, Demo, DemoKind, RawItem, RawRelease, RawTool

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime.now(UTC)


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Message] = []

    async def send(self, message: Message) -> None:
        self.sent.append(message)


class FailingSender:
    async def send(self, message: Message) -> None:
        raise ConnectionError("smtp down")


@pytest.fixture
def outbox(monkeypatch) -> Outbox:
    box = Outbox()
    monkeypatch.setattr(routes_account, "get_sender", lambda: box)
    return box


@pytest.fixture
async def api(session_factory):
    async def override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


def link_token(message: Message) -> str:
    return re.search(r"token=([\w-]+)", message.text).group(1)


async def sign_in(api: httpx.AsyncClient, outbox: Outbox, email: str = "Reader@Example.com") -> str:
    assert (await api.post("/api/auth/request-link", json={"email": email})).status_code == 202
    response = await api.post("/api/auth/verify", json={"token": link_token(outbox.sent[-1])})
    assert response.status_code == 200
    return response.json()["session_token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- sign-in -------------------------------------------------------------------


async def test_sign_in_by_email_link(api, outbox, session_factory) -> None:
    token = await sign_in(api, outbox)
    me = (await api.get("/api/me", headers=bearer(token))).json()
    assert me["email"] == "reader@example.com"  # normalized
    assert me["brief_enabled"] and me["brief_hour"] == 7

    # Links are single-use, and only hashes are stored.
    reuse = await api.post("/api/auth/verify", json={"token": link_token(outbox.sent[-1])})
    assert reuse.status_code == 400
    async with session_factory() as session:
        stored = (await session.execute(select(LoginToken.token_hash))).scalars().all()
    assert link_token(outbox.sent[-1]) not in stored

    # Signing in again finds the same account.
    again = await sign_in(api, outbox, "reader@example.com")
    assert (await api.get("/api/me", headers=bearer(again))).json()["id"] == me["id"]

    assert (await api.post("/api/auth/logout", headers=bearer(token))).status_code == 204
    assert (await api.get("/api/me", headers=bearer(token))).status_code == 401
    assert (await api.get("/api/me")).status_code == 401


async def test_sign_in_guards(api, outbox, session_factory) -> None:
    assert (
        await api.post("/api/auth/request-link", json={"email": "not-an-email"})
    ).status_code == 422
    for _ in range(5):  # same answer every time, but only 3 emails go out per window
        assert (
            await api.post("/api/auth/request-link", json={"email": "a@b.co"})
        ).status_code == 202
    assert len(outbox.sent) == auth.MAX_LINKS_PER_WINDOW

    async with session_factory() as session, session.begin():
        await session.execute(update(LoginToken).values(expires_at=NOW - timedelta(minutes=1)))
    expired = await api.post("/api/auth/verify", json={"token": link_token(outbox.sent[0])})
    assert expired.status_code == 400


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/tools/3", "/tools/3"),
        ("https://evil.com", "/brief"),
        ("//evil.com", "/brief"),
        (None, "/brief"),
    ],
)
def test_sign_in_redirect_stays_on_site(path, expected) -> None:
    assert auth.safe_next(path) == expected


# --- follows -------------------------------------------------------------------


async def make_tools(session_factory) -> dict[str, int]:
    tools = [
        RawTool("acme/agent", "Agent framework", "Python", stars=900, topics=["ai-agents", "llm"]),
        RawTool(
            "acme/rising",
            "Fast-rising MCP server",
            "Go",
            stars=300,
            topics=["mcp"],
            stars_today=500,
        ),
        RawTool(
            "acme/also", "Another agent kit", "Rust", stars=50, topics=["ai-agents"], stars_today=80
        ),
        RawTool(
            "acme/demo",
            "Has a GIF demo",
            "TS",
            stars=10,
            stars_today=40,
            demo=Demo("https://raw.githubusercontent.com/acme/demo/main/demo.gif", DemoKind.GIF),
        ),
    ]
    async with session_factory() as session, session.begin():
        await save_tools(session, tools, NOW, IngestStats())
        rows = (await session.execute(select(Tool.full_name, Tool.id))).all()
    return dict(rows)


async def test_follow_tools_and_topics(api, outbox, session_factory) -> None:
    ids = await make_tools(session_factory)
    token = await sign_in(api, outbox)
    h = bearer(token)
    assert (
        await api.put(f"/api/me/follows/tool/{ids['acme/agent']}", headers=h)
    ).status_code == 204
    assert (
        await api.put(f"/api/me/follows/tool/{ids['acme/agent']}", headers=h)
    ).status_code == 204  # idempotent
    assert (await api.put("/api/me/follows/topic/MCP", headers=h)).status_code == 204  # lowercased
    assert (await api.put("/api/me/follows/tool/999999", headers=h)).status_code == 404
    assert (await api.put("/api/me/follows/topic/bad topic!", headers=h)).status_code == 422
    assert (await api.put("/api/me/follows/user/1", headers=h)).status_code == 404

    follows = (await api.get("/api/me/follows", headers=h)).json()
    assert [t["full_name"] for t in follows["tools"]] == ["acme/agent"]
    assert follows["topics"] == ["mcp"]

    assert (await api.delete("/api/me/follows/topic/mcp", headers=h)).status_code == 204
    assert (await api.get("/api/me/follows", headers=h)).json()["topics"] == []
    assert (await api.put("/api/me/follows/topic/mcp")).status_code == 401  # must be signed in


async def test_settings_validation(api, outbox) -> None:
    h = bearer(await sign_in(api, outbox))
    ok = await api.patch("/api/me", headers=h, json={"brief_hour": 6, "timezone": "Europe/Berlin"})
    assert ok.json()["brief_hour"] == 6 and ok.json()["timezone"] == "Europe/Berlin"
    assert (await api.patch("/api/me", headers=h, json={"brief_hour": 24})).status_code == 422
    assert (
        await api.patch("/api/me", headers=h, json={"timezone": "Mars/Base"})
    ).status_code == 422


# --- composition ---------------------------------------------------------------


async def seed_reader(session_factory, ids) -> User:
    async with session_factory() as session, session.begin():
        session.add(User(email="reader@example.com", handle="hanging-1001"))
    async with session_factory() as session, session.begin():
        user = await session.scalar(select(User))
        from app.models import Follow

        session.add_all(
            [
                Follow(user_id=user.id, kind="tool", target=str(ids["acme/agent"])),
                Follow(user_id=user.id, kind="topic", target="mcp"),
            ]
        )
    async with session_factory() as session:
        return await session.scalar(select(User))


async def seed_stories(session_factory) -> None:
    async with session_factory() as session, session.begin():
        session.add(Source(slug="s", name="Source", url="https://s", weight=1.0))
    async with session_factory() as session, session.begin():
        source_id = await session.scalar(select(Source.id))
        items = [
            RawItem(
                "https://s/1",
                "New MCP server spec lands",
                ContentType.NEWS,
                engagement=1,
                published_at=NOW - timedelta(hours=10),
            ),
            RawItem(
                "https://s/2",
                "Unrelated but very popular robotics paper",
                ContentType.PAPER,
                engagement=900,
                published_at=NOW - timedelta(hours=2),
            ),
            RawItem(
                "https://s/3",
                "<script>alert(1)</script> Agents & tools",
                ContentType.NEWS,
                published_at=NOW - timedelta(hours=3),
            ),
        ]
        await save_items(session, source_id, items, NOW, IngestStats())


async def test_compose_brief_is_personal_and_never_repeats(session_factory) -> None:
    ids = await make_tools(session_factory)
    user = await seed_reader(session_factory, ids)
    await seed_stories(session_factory)
    async with session_factory() as session, session.begin():
        await save_releases(
            session,
            ids["acme/agent"],
            [
                RawRelease(
                    "v2.0",
                    "https://github.com/acme/agent/releases/tag/v2.0",
                    published_at=NOW - timedelta(hours=5),
                ),
                RawRelease(
                    "v1.0",
                    "https://github.com/acme/agent/releases/tag/v1.0",
                    published_at=NOW - timedelta(days=30),
                ),
            ],
            NOW,
        )
        brief = await compose_brief(session, user, NOW)

    assert brief.personalized and brief.followed_topics == ["mcp"]
    assert [r.tag for r in brief.releases] == ["v2.0"]  # the month-old release is not news
    assert [t.full_name for t in brief.rising] == [
        "acme/rising"
    ]  # in #mcp, and not already followed
    assert brief.demo.full_name == "acme/demo"
    titles = [a.title for a in brief.reads]
    assert titles[0] == "New MCP server spec lands"  # topic match outranks a more popular story
    matched = {a.title for a in brief.reads if a.id in brief.matched_article_ids}
    assert matched == {"New MCP server spec lands"}

    # Once sent, the same items don't show up again for a week.
    outbox = Outbox()
    async with session_factory() as session, session.begin():
        await session.execute(update(User).values(brief_hour=0, timezone="UTC"))
    assert (await send_due_briefs(session_factory, outbox, NOW)).sent == 1
    async with session_factory() as session:
        user = await session.scalar(select(User))
        again = await compose_brief(session, user, NOW + timedelta(hours=1))
    assert again.releases == [] and again.rising == [] and again.demo is None
    assert {a.title for a in again.reads}.isdisjoint(titles)


async def test_new_reader_without_follows_gets_a_general_brief(session_factory) -> None:
    await make_tools(session_factory)
    await seed_stories(session_factory)
    async with session_factory() as session, session.begin():
        session.add(User(email="new@example.com", handle="hanging-1002"))
    async with session_factory() as session:
        user = await session.scalar(select(User))
        brief = await compose_brief(session, user, NOW)
    assert not brief.personalized and not brief.is_empty
    assert brief.rising and brief.reads
    message = build_message(user, brief, NOW)
    assert "Follow a few tools or topics" in message.text


# --- delivery ------------------------------------------------------------------


@pytest.mark.parametrize(
    "tz, hour, utc_hour, due",
    [
        ("UTC", 7, 6, False),
        ("UTC", 7, 7, True),
        ("America/New_York", 7, 10, False),  # 06:00 in New York (EDT)
        ("America/New_York", 7, 11, True),
        ("Asia/Tokyo", 7, 22, True),  # already 07:00 the next day in Tokyo
    ],
)
def test_brief_hour_is_local_time(tz, hour, utc_hour, due) -> None:
    user = User(
        email="x@y.co", handle="hanging-1", brief_enabled=True, brief_hour=hour, timezone=tz
    )
    assert is_due(user, datetime(2026, 10, 1, utc_hour, tzinfo=UTC)) is due


async def test_delivery_is_idempotent_retries_failures_and_respects_unsubscribe(
    session_factory, api
) -> None:
    await make_tools(session_factory)
    await seed_stories(session_factory)
    async with session_factory() as session, session.begin():
        session.add(
            User(email="reader@example.com", handle="hanging-1003", brief_hour=0, timezone="UTC")
        )

    failing = await send_due_briefs(session_factory, FailingSender(), NOW)
    assert failing.failed == 1
    async with session_factory() as session:
        assert (await session.scalar(select(Brief))).status == "failed"

    outbox = Outbox()
    assert (await send_due_briefs(session_factory, outbox, NOW)).sent == 1  # retried
    assert (await send_due_briefs(session_factory, outbox, NOW)).skipped == 1  # never twice a day
    assert len(outbox.sent) == 1

    message = outbox.sent[0]
    assert message.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert (
        "<script>" not in message.html and "&lt;script&gt;" in message.html
    )  # scraped titles escaped

    # Unsubscribe link: wrong signature refused, right one works, then no more briefs.
    user_id = int(re.search(r"u=(\d+)", message.headers["List-Unsubscribe"]).group(1))
    assert (
        await api.post("/api/unsubscribe", json={"u": user_id, "t": "forged"})
    ).status_code == 400
    signature = auth.unsubscribe_signature(user_id)
    assert (
        await api.post(f"/api/unsubscribe/one-click?u={user_id}&t={signature}")
    ).status_code == 204
    assert (await send_due_briefs(session_factory, outbox, NOW + timedelta(days=1))).sent == 0


async def test_web_brief_endpoint(api, outbox, session_factory) -> None:
    await make_tools(session_factory)
    await seed_stories(session_factory)
    h = bearer(await sign_in(api, outbox))
    assert (await api.put("/api/me/follows/topic/mcp", headers=h)).status_code == 204
    brief = (await api.get("/api/me/brief", headers=h)).json()
    assert brief["personalized"] and brief["followed_topics"] == ["mcp"]
    assert any(r["matched"] for r in brief["reads"])
    assert brief["rising"][0]["full_name"] == "acme/rising"


# --- releases parser -------------------------------------------------------------


def test_github_releases_parser() -> None:
    releases = parse_releases(
        (FIXTURES / "github_releases_browser-use.html").read_text(),
        "https://github.com/browser-use/browser-use/releases",
    )
    assert len(releases) == 10
    latest = releases[0]
    assert latest.tag == "0.13.10"
    assert latest.url == "https://github.com/browser-use/browser-use/releases/tag/0.13.10"
    assert latest.published_at == datetime(2026, 9, 4, 3, 28, 53, tzinfo=UTC)
    assert latest.notes and len(latest.notes) <= 500
    assert [r.published_at for r in releases] == sorted(
        (r.published_at for r in releases), reverse=True
    )
