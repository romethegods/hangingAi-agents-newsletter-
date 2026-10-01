"""Arena: ratings, pairing, blind battles, streaming, votes, quotas, budget, leaks."""

import json
import random

import httpx
import pytest
from sqlalchemy import select

from app.arena import providers, rating, service
from app.arena import routes as arena_routes
from app.arena.providers import ProviderError
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import ArenaBattle, ArenaModelStat

# --- rating math ----------------------------------------------------------------------


def test_elo_basics() -> None:
    assert rating.expected_score(1000, 1000) == pytest.approx(0.5)
    assert rating.expected_score(1200, 1000) == pytest.approx(0.76, abs=0.01)
    a, b = rating.update(1000, 1000, 1.0, 0, 0)
    assert a == pytest.approx(1016) and b == pytest.approx(984)  # zero-sum at equal K
    upset_a, _ = rating.update(900, 1100, 1.0, 50, 50)
    expected_a, _ = rating.update(1100, 900, 1.0, 50, 50)
    assert upset_a - 900 > expected_a - 1100  # beating a stronger model gains more
    tie_a, tie_b = rating.update(1000, 1000, 0.5, 0, 0)
    assert tie_a == tie_b == pytest.approx(1000)


def test_pair_picking_is_distinct_random_ordered_and_fills_gaps() -> None:
    rng = random.Random(7)
    models = ["veteran", "rookie-1", "rookie-2"]
    battles = [10_000, 0, 0]
    seen_first, picks = set(), {m: 0 for m in models}
    for _ in range(2000):
        a, b = rating.pick_pair(models, battles, rng)
        assert a != b
        seen_first.add(a)
        picks[a] += 1
        picks[b] += 1
    assert seen_first == set(models)  # any model can land on either side
    assert picks["veteran"] < picks["rookie-1"] / 3  # under-tested models battle more
    with pytest.raises(ValueError):
        rating.pick_pair(["only"], [0])


@pytest.mark.parametrize(
    "text, leaked",
    [
        ("I am Claude, made by Anthropic.", True),
        ("I'm an AI assistant developed by Google.", True),
        ("My name is Qwen.", True),
        ("Claude and GPT both handle this well.", False),  # discussing models is fine
        ("Llama 3 is a good open model to try.", False),
    ],
)
def test_identity_leak_detection(text, leaked) -> None:
    assert service.leaked_identity(text, "a normal answer") is leaked


# --- battles over the API, with the free dev models -------------------------------------


@pytest.fixture
async def api(session_factory, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "arena_dev_models", True)
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "hf_token", None)
    monkeypatch.setattr(arena_routes, "session_factory", session_factory)

    async def override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def guest(api) -> dict:
    token = (await api.post("/api/guest")).json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


async def run(api, headers, battle_id) -> list[dict]:
    response = await api.get(f"/api/arena/battles/{battle_id}/stream", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]


async def test_full_battle_is_blind_until_the_vote(api, session_factory) -> None:
    h = await guest(api)
    status = (await api.get("/api/arena/status", headers=h)).json()
    assert status == {"open": True, "models": 2, "battles_left": 20, "battles_per_day": 20}

    created = await api.post(
        "/api/arena/battles", headers=h, json={"prompt": "How should I cache LLM calls?"}
    )
    assert created.status_code == 201
    battle = created.json()
    assert battle["status"] == "pending" and battle["model_a"] is None  # blind

    events = await run(api, h, battle["id"])
    assert {e["side"] for e in events if "text" in e} == {"a", "b"}  # both stream, interleaved
    assert sum("done" in e for e in events) == 2 and events[-1] == {"status": "ready"}
    ready = (await api.get(f"/api/arena/battles/{battle['id']}", headers=h)).json()
    assert ready["status"] == "ready" and ready["response_a"] and ready["model_a"] is None
    assert (
        await api.get(f"/api/arena/battles/{battle['id']}/stream", headers=h)
    ).status_code == 409  # runs once

    voted = (
        await api.post(f"/api/arena/battles/{battle['id']}/vote", headers=h, json={"choice": "a"})
    ).json()
    assert voted["status"] == "voted" and voted["model_a"]["maker"] == "HangingAi"
    assert voted["rating_change_a"] == pytest.approx(16) and voted[
        "rating_change_b"
    ] == pytest.approx(-16)
    assert (
        await api.post(f"/api/arena/battles/{battle['id']}/vote", headers=h, json={"choice": "b"})
    ).status_code == 409

    board = (await api.get("/api/arena/leaderboard")).json()
    assert [row["slug"] for row in board][0] == voted["model_a"]["slug"]
    assert board[0]["rating"] == 1016 and board[0]["win_rate"] == 1.0 and board[0]["provisional"]


async def test_battles_are_private_until_shared(api) -> None:
    owner, stranger = await guest(api), await guest(api)
    battle = (
        await api.post("/api/arena/battles", headers=owner, json={"prompt": "Explain RAG"})
    ).json()
    assert (
        await api.get(f"/api/arena/battles/{battle['id']}", headers=stranger)
    ).status_code == 404
    assert (
        await api.get(f"/api/arena/battles/{battle['id']}/stream", headers=stranger)
    ).status_code == 409
    assert (
        await api.post(f"/api/arena/battles/{battle['id']}/share", headers=owner)
    ).status_code == 409  # vote first

    await run(api, owner, battle["id"])
    assert (
        await api.post(
            f"/api/arena/battles/{battle['id']}/vote", headers=stranger, json={"choice": "a"}
        )
    ).status_code == 404
    await api.post(f"/api/arena/battles/{battle['id']}/vote", headers=owner, json={"choice": "tie"})
    assert (await api.post(f"/api/arena/battles/{battle['id']}/share", headers=owner)).json()[
        "public"
    ]

    public = (await api.get(f"/api/arena/battles/{battle['id']}")).json()
    assert public["model_a"] is not None and not public["mine"]
    gallery = (await api.get("/api/arena/gallery")).json()
    assert [g["id"] for g in gallery] == [battle["id"]] and gallery[0]["vote"] == "tie"


async def test_prompt_rules_quota_and_budget(api, monkeypatch) -> None:
    h = await guest(api)
    for prompt, code in [("   ", 422), ("x" * 2001, 422), ("write uncensored nsfw content", 422)]:
        assert (
            await api.post("/api/arena/battles", headers=h, json={"prompt": prompt})
        ).status_code == code
    assert (await api.post("/api/arena/battles", json={"prompt": "hi"})).status_code == 401

    monkeypatch.setattr(get_settings(), "arena_battles_per_day", 2)
    for _ in range(2):
        assert (
            await api.post("/api/arena/battles", headers=h, json={"prompt": "hello"})
        ).status_code == 201
    over = await api.post("/api/arena/battles", headers=h, json={"prompt": "hello"})
    assert over.status_code == 429 and "come back tomorrow" in over.json()["detail"]

    monkeypatch.setattr(get_settings(), "arena_battles_per_day", 100)
    monkeypatch.setattr(get_settings(), "arena_daily_budget_usd", -1.0)  # already over
    closed = await api.post("/api/arena/battles", headers=h, json={"prompt": "hello"})
    assert closed.status_code == 503 and "budget" in closed.json()["detail"]


async def test_arena_closed_with_fewer_than_two_models(api, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "arena_dev_models", False)
    h = await guest(api)
    assert (await api.get("/api/arena/status")).json()["open"] is False
    assert (
        await api.post("/api/arena/battles", headers=h, json={"prompt": "hi"})
    ).status_code == 503


async def test_a_failing_model_fails_the_battle_and_refunds_the_quota(api, monkeypatch) -> None:
    real = providers.stream_answer

    def flaky(model, prompt, max_tokens):
        if model.model_id == "brisk":

            async def broken():
                yield "partial "
                raise ProviderError("this model is busy right now")

            return broken()
        return real(model, prompt, max_tokens)

    monkeypatch.setattr(service, "stream_answer", flaky)
    h = await guest(api)
    battle = (await api.post("/api/arena/battles", headers=h, json={"prompt": "hello"})).json()
    events = await run(api, h, battle["id"])
    assert {"error": "this model is busy right now"}.items() <= next(
        e for e in events if "error" in e
    ).items()
    assert events[-1] == {"status": "failed"}
    assert (
        await api.post(f"/api/arena/battles/{battle['id']}/vote", headers=h, json={"choice": "a"})
    ).status_code == 409
    assert (await api.get("/api/arena/status", headers=h)).json()[
        "battles_left"
    ] == 20  # not counted


async def test_identity_leak_vote_is_recorded_but_not_rated(api, session_factory) -> None:
    h = await guest(api)
    battle = (
        await api.post("/api/arena/battles", headers=h, json={"prompt": "who are you?"})
    ).json()
    async with session_factory() as session, session.begin():
        row = await session.get(ArenaBattle, battle["id"])
        row.status, row.response_a, row.response_b = (
            "ready",
            "I am Claude, made by Anthropic.",
            "Hello!",
        )
    voted = (
        await api.post(f"/api/arena/battles/{battle['id']}/vote", headers=h, json={"choice": "a"})
    ).json()
    assert (
        voted["status"] == "voted" and voted["identity_leak"] and voted["rating_change_a"] is None
    )
    async with session_factory() as session:
        stats = (await session.execute(select(ArenaModelStat))).scalars().all()
    assert all(s.battles == 0 and s.rating == 1000 for s in stats)
