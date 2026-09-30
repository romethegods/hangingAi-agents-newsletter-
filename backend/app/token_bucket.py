"""Token bucket: the rate-limiting primitive shared by the scraper (outbound
politeness per domain) and the API (inbound limits per client)."""

import asyncio
import time
from collections.abc import Callable


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

    @property
    def remaining(self) -> int:
        """Whole requests available right now."""
        self._refill()
        return int(self._tokens)

    def seconds_until_full(self) -> float:
        self._refill()
        return max(0.0, (self.capacity - self._tokens) / self.rate)

    def seconds_until_available(self) -> float:
        self._refill()
        return max(0.0, (1 - self._tokens) / self.rate)

    async def acquire(self) -> None:
        while not self.try_acquire():
            await asyncio.sleep(self.seconds_until_available())
