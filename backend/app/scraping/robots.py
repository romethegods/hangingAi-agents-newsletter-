"""robots.txt compliance, cached per host (RFC 9309 semantics).

We don't use urllib.robotparser: it ignores the `*` and `$` wildcards RFC 9309
requires, so a rule like GitHub's `Disallow: /*/*/tags` silently allowed
everything.
"""

import asyncio
import contextlib
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

ROBOTS_AGENT = "HangingAiBot"


@dataclass(slots=True)
class _Group:
    agents: list[str]
    rules: list[tuple[bool, str, re.Pattern]]  # (allow, raw pattern, compiled)
    crawl_delay: float | None = None


def _compile(pattern: str) -> re.Pattern:
    """`*` matches any run of characters; a trailing `$` anchors the end."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


class RobotsRules:
    """Parsed robots.txt. Same interface as urllib's RobotsRules, correct matching."""

    def __init__(self) -> None:
        self.allow_all = False
        self.disallow_all = False
        self._groups: list[_Group] = []

    def parse(self, lines: list[str]) -> None:
        current: _Group | None = None
        for raw in lines:
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            field, value = (part.strip() for part in line.split(":", 1))
            field = field.lower()
            if field == "user-agent":
                # Consecutive user-agent lines share one group of rules.
                if current is None or current.rules or current.crawl_delay is not None:
                    current = _Group(agents=[], rules=[])
                    self._groups.append(current)
                current.agents.append(value.lower())
            elif current is None:
                continue  # rules before any user-agent line are ignored
            elif field in ("allow", "disallow") and value:
                current.rules.append((field == "allow", value, _compile(value)))
            elif field == "crawl-delay":
                with contextlib.suppress(ValueError):
                    current.crawl_delay = float(value)

    def _groups_for(self, agent: str) -> list[_Group]:
        token = agent.lower()
        mine = [g for g in self._groups if token in g.agents]
        return mine or [g for g in self._groups if "*" in g.agents]

    def can_fetch(self, agent: str, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if path == "/robots.txt":
            return True
        # The longest matching rule wins; on a tie, allow wins (the least restrictive).
        best: tuple[int, bool] | None = None
        for group in self._groups_for(agent):
            for allow, raw, pattern in group.rules:
                if pattern.match(path):
                    candidate = (len(raw), allow)
                    if best is None or candidate > best:
                        best = candidate
        return best is None or best[1]

    def crawl_delay(self, agent: str) -> float | None:
        delays = [g.crawl_delay for g in self._groups_for(agent) if g.crawl_delay is not None]
        return max(delays) if delays else None


# Returns (status_code, body); raises on network failure.
RobotsLoader = Callable[[str], Awaitable[tuple[int, str]]]


@dataclass(slots=True)
class _Entry:
    parser: RobotsRules
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

    async def _parser_for(self, url: str) -> RobotsRules:
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

    async def _load(self, origin: str) -> RobotsRules:
        parser = RobotsRules()
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
