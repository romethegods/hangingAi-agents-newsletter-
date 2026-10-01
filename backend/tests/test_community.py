"""Guests, handles, comments, reports, votes, merging and moderation."""

import re

import httpx
import pytest
from sqlalchemy import select

from app import community, routes_account
from app.config import get_settings
from app.db import get_session
from app.email import Message
from app.main import app
from app.models import Comment, Follow, Source, User, Vote
from app.scraping.pipeline import IngestStats, save_items, save_tools
from app.scraping.types import ContentType, RawItem, RawTool


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Message] = []

    async def send(self, message: Message) -> None:
        self.sent.append(message)


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


@pytest.fixture
async def targets(session_factory) -> dict[str, int]:
    async with session_factory() as session, session.begin():
        session.add(Source(slug="s", name="S", url="https://s"))
    async with session_factory() as session, session.begin():
        source_id = await session.scalar(select(Source.id))
        await save_items(
            session, source_id, [RawItem("https://s/1", "A story", ContentType.NEWS)], *_now_stats()
        )
        await save_tools(session, [RawTool("acme/agent", "An agent")], *_now_stats())
    from app.models import Article, Tool

    async with session_factory() as session:
        return {
            "article": await session.scalar(select(Article.id)),
            "tool": await session.scalar(select(Tool.id)),
        }


def _now_stats():
    from datetime import UTC, datetime

    return datetime.now(UTC), IngestStats()


async def new_guest(api) -> tuple[dict, dict]:
    response = await api.post("/api/guest")
    assert response.status_code == 201
    body = response.json()
    return body["user"], {"Authorization": f"Bearer {body['session_token']}"}


# --- guests & handles ---------------------------------------------------------------


async def test_guests_get_hanging_handles_and_can_rename(api) -> None:
    user, h = await new_guest(api)
    assert re.fullmatch(r"hanging-\d{4}", user["handle"])
    assert user["is_guest"] and user["email"] is None

    renamed = await api.patch("/api/me", headers=h, json={"handle": "Agent Smith"})
    assert renamed.status_code == 200 and renamed.json()["handle"] == "agent-smith"

    _, other = await new_guest(api)
    assert (
        await api.patch("/api/me", headers=other, json={"handle": "agent-smith"})
    ).status_code == 409
    for bad in ("admin", "x", "no spaces!!", "nsfw-bot"):
        assert (
            await api.patch("/api/me", headers=other, json={"handle": bad})
        ).status_code == 422, bad


async def test_handle_generation_grows_when_crowded(session_factory, monkeypatch) -> None:
    async with session_factory() as session, session.begin():
        session.add(User(handle="hanging-1234"))
    picks = iter([234, 234, 234, 51234])  # 1000 + 234 collides three times; then five digits
    monkeypatch.setattr(community.secrets, "randbelow", lambda n: next(picks))
    async with session_factory() as session:
        assert await community.new_handle(session) == "hanging-61234"


# --- comments ---------------------------------------------------------------------


async def test_comment_thread_with_replies_votes_and_ownership(api, targets) -> None:
    alice, a = await new_guest(api)
    _, b = await new_guest(api)
    tool = targets["tool"]

    first = await api.post(
        "/api/comments",
        headers=a,
        json={"target_kind": "tool", "target_id": tool, "body": "Works great"},
    )
    assert first.status_code == 201
    first_id = first.json()["id"]
    reply = await api.post(
        "/api/comments",
        headers=b,
        json={"target_kind": "tool", "target_id": tool, "body": "Agreed", "parent_id": first_id},
    )
    # Replying to a reply attaches to the thread's top comment (one level deep).
    nested = await api.post(
        "/api/comments",
        headers=a,
        json={
            "target_kind": "tool",
            "target_id": tool,
            "body": "Thanks",
            "parent_id": reply.json()["id"],
        },
    )
    assert nested.json()["parent_id"] == first_id

    assert (await api.post(f"/api/votes/comment/{first_id}", headers=b)).json() == {
        "voted": True,
        "votes": 1,
    }
    thread = (await api.get(f"/api/comments/tool/{tool}", headers=b)).json()
    assert thread["count"] == 3
    top = thread["comments"][0]
    assert (
        top["author"] == alice["handle"] and top["votes"] == 1 and top["voted"] and not top["mine"]
    )
    assert [r["body"] for r in top["replies"]] == ["Agreed", "Thanks"]

    # Anyone can read without an identity.
    assert (await api.get(f"/api/comments/tool/{tool}")).json()["count"] == 3
    # Only the author can delete; deleted text disappears but the thread stays.
    assert (await api.delete(f"/api/comments/{first_id}", headers=b)).status_code == 404
    assert (await api.delete(f"/api/comments/{first_id}", headers=a)).status_code == 204
    after = (await api.get(f"/api/comments/tool/{tool}")).json()
    assert after["comments"][0]["body"] is None and after["comments"][0]["author"] == "[removed]"
    assert len(after["comments"][0]["replies"]) == 2


@pytest.mark.parametrize(
    "body, status",
    [
        ("   ", 422),
        ("x" * 2001, 422),
        ("see https://a.co https://b.co https://c.co", 422),  # link cap
        ("uncensored nsfw content here", 422),
    ],
)
async def test_comment_filters(api, targets, body, status) -> None:
    _, h = await new_guest(api)
    response = await api.post(
        "/api/comments",
        headers=h,
        json={"target_kind": "article", "target_id": targets["article"], "body": body},
    )
    assert response.status_code == status


async def test_duplicate_and_bad_targets(api, targets) -> None:
    _, h = await new_guest(api)
    post = {"target_kind": "article", "target_id": targets["article"], "body": "Nice"}
    assert (await api.post("/api/comments", headers=h, json=post)).status_code == 201
    assert (await api.post("/api/comments", headers=h, json=post)).status_code == 409
    assert (
        await api.post("/api/comments", headers=h, json={**post, "target_id": 999999})
    ).status_code == 404
    assert (
        await api.post("/api/comments", json=post)
    ).status_code == 401  # needs at least a guest identity


async def test_three_reports_hide_a_comment_until_reviewed(api, targets, monkeypatch) -> None:
    _, author = await new_guest(api)
    comment = await api.post(
        "/api/comments",
        headers=author,
        json={"target_kind": "tool", "target_id": targets["tool"], "body": "Buy cheap pills"},
    )
    cid = comment.json()["id"]
    assert (
        await api.post(f"/api/comments/{cid}/report", headers=author, json={})
    ).status_code == 422  # not your own

    reporters = [await new_guest(api) for _ in range(3)]
    results = [
        (await api.post(f"/api/comments/{cid}/report", headers=h, json={"reason": "spam"})).json()
        for _, h in reporters
    ]
    assert [r["hidden"] for r in results] == [False, False, True]
    again = await api.post(f"/api/comments/{cid}/report", headers=reporters[0][1], json={})
    assert again.json()["hidden"] is False  # one report per person

    public = (await api.get(f"/api/comments/tool/{targets['tool']}")).json()
    assert public["count"] == 0 and public["comments"][0]["body"] is None

    # A moderator sees it in the queue and can restore it.
    monkeypatch.setattr(get_settings(), "admin_emails", ["mod@hangingai.com"])
    _, mod = await email_account(api, "mod@hangingai.com")
    assert (await api.get("/api/mod/queue", headers=author)).status_code == 403
    queue = (await api.get("/api/mod/queue", headers=mod)).json()
    assert [(q["id"], q["status"], q["report_count"]) for q in queue] == [(cid, "hidden", 3)]
    assert (await api.post(f"/api/mod/comments/{cid}/restore", headers=mod)).status_code == 204
    assert (await api.get(f"/api/comments/tool/{targets['tool']}")).json()["count"] == 1


async def test_ban_stops_posting_and_removes_comments(api, targets, monkeypatch) -> None:
    spammer, h = await new_guest(api)
    await api.post(
        "/api/comments",
        headers=h,
        json={"target_kind": "tool", "target_id": targets["tool"], "body": "spam"},
    )
    monkeypatch.setattr(get_settings(), "admin_emails", ["mod@hangingai.com"])
    _, mod = await email_account(api, "mod@hangingai.com")
    assert (await api.post(f"/api/mod/users/{spammer['id']}/ban", headers=mod)).status_code == 204
    retry = await api.post(
        "/api/comments",
        headers=h,
        json={"target_kind": "tool", "target_id": targets["tool"], "body": "more"},
    )
    assert retry.status_code == 403
    assert (await api.post(f"/api/votes/tool/{targets['tool']}", headers=h)).status_code == 403
    assert (await api.get(f"/api/comments/tool/{targets['tool']}")).json()["comments"] == []


# --- votes ------------------------------------------------------------------------


async def test_upvotes_toggle_and_count(api, targets) -> None:
    _, a = await new_guest(api)
    _, b = await new_guest(api)
    article = targets["article"]
    assert (await api.post(f"/api/votes/article/{article}", headers=a)).json() == {
        "voted": True,
        "votes": 1,
    }
    assert (await api.post(f"/api/votes/article/{article}", headers=b)).json() == {
        "voted": True,
        "votes": 2,
    }
    assert (await api.post(f"/api/votes/article/{article}", headers=a)).json() == {
        "voted": False,
        "votes": 1,
    }
    assert (await api.get(f"/api/votes/article/{article}", headers=b)).json() == {
        "voted": True,
        "votes": 1,
    }
    assert (await api.get(f"/api/votes/article/{article}")).json() == {"voted": False, "votes": 1}
    assert (await api.post("/api/votes/article/999999", headers=a)).status_code == 404
    assert (await api.post(f"/api/votes/user/{article}", headers=a)).status_code == 422


# --- adding an email to a guest ----------------------------------------------------


async def email_account(
    api, email: str, guest_headers: dict | None = None, box: Outbox | None = None
):
    box = box or Outbox()
    original = routes_account.get_sender
    routes_account.get_sender = lambda: box
    try:
        await api.post("/api/auth/request-link", json={"email": email})
    finally:
        routes_account.get_sender = original  # don't leak into other tests
    token = re.search(r"token=([\w-]+)", box.sent[-1].text).group(1)
    response = await api.post(
        "/api/auth/verify", json={"token": token}, headers=guest_headers or {}
    )
    body = response.json()
    return body["user"], {"Authorization": f"Bearer {body['session_token']}"}


async def test_guest_adding_new_email_keeps_identity(api, targets, outbox, session_factory) -> None:
    guest, h = await new_guest(api)
    await api.put("/api/me/follows/topic/mcp", headers=h)
    user, _ = await email_account(api, "new@example.com", h, outbox)
    assert user["id"] == guest["id"] and user["handle"] == guest["handle"]
    assert user["email"] == "new@example.com" and not user["is_guest"]


async def test_guest_signing_into_existing_account_merges(
    api, targets, outbox, session_factory
) -> None:
    existing, _ = await email_account(api, "me@example.com", box=outbox)
    guest, h = await new_guest(api)
    await api.put("/api/me/follows/topic/rag", headers=h)
    await api.post(f"/api/votes/tool/{targets['tool']}", headers=h)
    await api.post(
        "/api/comments",
        headers=h,
        json={"target_kind": "tool", "target_id": targets["tool"], "body": "hi"},
    )

    merged, _ = await email_account(api, "me@example.com", h, outbox)
    assert merged["id"] == existing["id"]
    async with session_factory() as session:
        assert await session.get(User, guest["id"]) is None  # the guest is folded in
        follows = (
            (await session.execute(select(Follow.target).where(Follow.user_id == existing["id"])))
            .scalars()
            .all()
        )
        votes = (
            (await session.execute(select(Vote.target_id).where(Vote.user_id == existing["id"])))
            .scalars()
            .all()
        )
        comments = (await session.execute(select(Comment.user_id))).scalars().all()
    assert follows == ["rag"] and votes == [targets["tool"]] and comments == [existing["id"]]


async def test_guests_never_get_emailed_briefs(session_factory) -> None:
    from datetime import UTC, datetime

    from app.brief_delivery import send_due_briefs

    async with session_factory() as session, session.begin():
        session.add(User(handle="hanging-5555", brief_hour=0, timezone="UTC"))
    box = Outbox()
    stats = await send_due_briefs(session_factory, box, datetime.now(UTC))
    assert box.sent == [] and stats.sent == 0


async def test_merge_keeps_a_chosen_name_over_an_automatic_one(api, outbox) -> None:
    existing, _ = await email_account(api, "me@example.com", box=outbox)
    assert existing["handle"].startswith("hanging-")
    _, h = await new_guest(api)
    await api.patch("/api/me", headers=h, json={"handle": "rome-tester"})
    merged, _ = await email_account(api, "me@example.com", h, outbox)
    assert merged["id"] == existing["id"] and merged["handle"] == "rome-tester"
