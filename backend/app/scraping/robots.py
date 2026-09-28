"""robots.txt compliance, cached per host (RFC 9309 semantics)."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

ROBOTS_AGENT = "HangingAiBot"

# Returns (status_code, body); raises on network failure.
RobotsLoader = Callable[[str], Awaitable[tuple[int, str]]]


@dataclass(slots=True)
class _Entry:
    parser: RobotFileParser
    expires_at: float


async def httpx_loader(url: str) -> tuple[int, str]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": ROBOTS_AGENT})
        return response.status_code, response.text


class RobotsCache:
    def __init__(
        self,
        loader: RobotsLoader = httpx_loader,
        *,
        ttl_seconds: float = 12 * 3600,
        error_ttl_seconds: float = 600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._loader = loader
        self._ttl = ttl_seconds
        self._error_ttl = error_ttl_seconds
        self._clock = clock
        self._cache: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _parser_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        entry = self._cache.get(origin)
        if entry and entry.expires_at > self._clock():
            return entry.parser
        # Parallel crawls of one host share a single robots.txt request.
        async with self._locks.setdefault(origin, asyncio.Lock()):
            entry = self._cache.get(origin)
            if entry and entry.expires_at > self._clock():
                return entry.parser
            return await self._load(origin)

    async def _load(self, origin: str) -> RobotFileParser:
        parser = RobotFileParser()
        ttl = self._ttl
        try:
            status, body = await self._loader(f"{origin}/robots.txt")
        except httpx.HTTPError:
            status, body = 503, ""
        if 200 <= status < 300:
            parser.parse(body.splitlines())
        elif 400 <= status < 500:
            parser.allow_all = True  # no robots.txt means no restrictions
        else:
            parser.disallow_all = True  # server trouble: back off, retry soon
            ttl = self._error_ttl
        self._cache[origin] = _Entry(parser, self._clock() + ttl)
        return parser

    async def allowed(self, url: str) -> bool:
        return (await self._parser_for(url)).can_fetch(ROBOTS_AGENT, url)

    async def crawl_delay(self, url: str) -> float | None:
        delay = (await self._parser_for(url)).crawl_delay(ROBOTS_AGENT)
        return float(delay) if delay is not None else None
