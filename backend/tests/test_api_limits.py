import httpx
import pytest

from app.api_limits import KeyedRateLimiter, Tier, is_exempt, parse_networks
from app.main import app

TIER = Tier("t", per_minute=60, burst=3)  # 1 request/second, bursts of 3


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_burst_then_refusal_then_refill() -> None:
    clock = FakeClock()
    limiter = KeyedRateLimiter(clock=clock)
    decisions = [limiter.check("1.2.3.4", TIER) for _ in range(4)]
    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert [d.remaining for d in decisions] == [2, 1, 0, 0]
    refused = decisions[-1]
    assert refused.retry_after == 1
    assert refused.headers()["Retry-After"] == "1"
    clock.t += 1.0
    assert limiter.check("1.2.3.4", TIER).allowed


def test_clients_and_tiers_are_independent() -> None:
    limiter = KeyedRateLimiter(clock=FakeClock())
    for _ in range(3):
        limiter.check("1.1.1.1", TIER)
    assert not limiter.check("1.1.1.1", TIER).allowed
    assert limiter.check("2.2.2.2", TIER).allowed
    assert limiter.check("1.1.1.1", Tier("search", 60, 3)).allowed


def test_memory_is_bounded_by_lru_eviction() -> None:
    limiter = KeyedRateLimiter(max_keys=100, clock=FakeClock())
    for i in range(1_000):
        limiter.check(f"10.0.{i // 256}.{i % 256}", TIER)
    assert len(limiter) == 100


def test_exempt_networks() -> None:
    nets = parse_networks(["127.0.0.0/8", "172.16.0.0/12", "::1/128"])
    assert is_exempt("127.0.0.1", nets)
    assert is_exempt("172.18.0.5", nets)  # a Docker bridge address
    assert is_exempt("::1", nets)
    assert not is_exempt("203.0.113.9", nets)
    assert not is_exempt("not-an-ip", nets)
    assert not is_exempt(None, nets)


@pytest.fixture
def strict_limits(session_factory):
    """Real middleware, tiny limits, and a real DB behind the endpoints."""
    from app.db import get_session

    async def override():
        async with session_factory() as session:
            yield session

    original = (app.state.rate_limiter, app.state.rate_limit_exempt)
    app.state.rate_limiter = KeyedRateLimiter()
    app.state.rate_limit_exempt = parse_networks(["127.0.0.0/8"])
    app.dependency_overrides[get_session] = override
    yield
    app.state.rate_limiter, app.state.rate_limit_exempt = original
    app.dependency_overrides.clear()


def client_from(ip: str) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 5555))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_middleware_returns_429_with_headers(strict_limits) -> None:
    from app.main import SEARCH_TIER

    async with client_from("203.0.113.9") as c:
        codes = [
            (await c.get("/api/search", params={"q": "agents"})).status_code
            for _ in range(SEARCH_TIER.burst + 1)
        ]
        assert codes[:-1] == [200] * SEARCH_TIER.burst and codes[-1] == 429

        refused = await c.get("/api/search", params={"q": "agents"})
        assert refused.status_code == 429
        assert refused.json()["detail"] == "rate limit exceeded"
        assert int(refused.headers["Retry-After"]) >= 1
        assert refused.headers["RateLimit-Remaining"] == "0"

        # Search has its own, stricter bucket: the general API still works.
        ok = await c.get("/api/tools")
        assert ok.status_code == 200
        assert int(ok.headers["RateLimit-Remaining"]) >= 0
        # Health checks are never limited.
        assert (await c.get("/health")).status_code == 200

    async with client_from("198.51.100.7") as other:  # a different visitor is unaffected
        assert (await other.get("/api/search", params={"q": "agents"})).status_code == 200


async def test_internal_callers_are_not_limited(strict_limits) -> None:
    from app.main import SEARCH_TIER

    async with client_from("127.0.0.1") as c:  # our own web server
        for _ in range(SEARCH_TIER.burst * 3):
            response = await c.get("/api/search", params={"q": "agents"})
            assert response.status_code == 200
            assert "RateLimit-Limit" not in response.headers
