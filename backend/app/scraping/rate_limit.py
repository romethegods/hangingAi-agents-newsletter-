"""Per-domain politeness: a token bucket for each host we crawl."""

import asyncio
import time
from collections.abc import Callable
from urllib.parse import urlsplit


class TokenBucket:
    """Allows `rate` requests per second on average, bursting up to `capacity`."""

    def __init__(
        self, rate: float, capacity: float = 1.0, clock: Callable[[], float] = time.monotonic
    ):
        if rate <= 0 or capacity < 1:
            raise ValueError("rate must be > 0 and capacity >= 1")
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._tokens = capacity
        self._updated = clock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
        self._updated = now

    def try_acquire(self) -> bool:
        self._refill()
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False

    def seconds_until_available(self) -> float:
        self._refill()
        return max(0.0, (1 - self._tokens) / self.rate)

    async def acquire(self) -> None:
        while not self.try_acquire():
            await asyncio.sleep(self.seconds_until_available())


class DomainRateLimiter:
    def __init__(self, default_interval_seconds: float = 2.0) -> None:
        self.default_interval = default_interval_seconds
        self._buckets: dict[str, TokenBucket] = {}

    def bucket_for(self, url: str, min_interval_seconds: float | None = None) -> TokenBucket:
        host = (urlsplit(url).hostname or "").lower()
        interval = max(self.default_interval, min_interval_seconds or 0.0)
        bucket = self._buckets.get(host)
        if bucket is None or bucket.rate != 1 / interval:
            bucket = self._buckets[host] = TokenBucket(rate=1 / interval)
        return bucket

    async def wait(self, url: str, min_interval_seconds: float | None = None) -> None:
        await self.bucket_for(url, min_interval_seconds).acquire()
