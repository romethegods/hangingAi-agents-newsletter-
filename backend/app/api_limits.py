"""Per-client rate limiting for the public API.

Each client IP gets a token bucket per tier; buckets live in an LRU map with a
hard size cap, so a flood of distinct (or spoofed) addresses can't grow memory
without bound: the least recently seen client is evicted first, which just
resets that client to a full bucket.

State is in-process. That is correct for the single API process we run; more
than one replica would need a shared store (e.g. Redis) instead.
"""

import ipaddress
import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from app.token_bucket import TokenBucket


@dataclass(frozen=True, slots=True)
class Tier:
    name: str
    per_minute: float
    burst: int


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int  # until the bucket is full again
    retry_after: int  # until the next request is allowed (0 when allowed)

    def headers(self) -> dict[str, str]:
        """IETF RateLimit header fields, plus Retry-After on refusals."""
        headers = {
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(self.remaining),
            "RateLimit-Reset": str(self.reset_seconds),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class KeyedRateLimiter:
    def __init__(self, max_keys: int = 50_000, clock: Callable[[], float] = time.monotonic):
        self.max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[tuple[str, str], TokenBucket] = OrderedDict()

    def __len__(self) -> int:
        return len(self._buckets)

    def check(self, client: str, tier: Tier) -> Decision:
        key = (tier.name, client)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(rate=tier.per_minute / 60, capacity=tier.burst, clock=self._clock)
            self._buckets[key] = bucket
            if len(self._buckets) > self.max_keys:
                self._buckets.popitem(last=False)  # evict least recently seen
        else:
            self._buckets.move_to_end(key)

        allowed = bucket.try_acquire()
        return Decision(
            allowed=allowed,
            limit=tier.burst,
            remaining=bucket.remaining,
            reset_seconds=math.ceil(bucket.seconds_until_full()),
            retry_after=0 if allowed else max(1, math.ceil(bucket.seconds_until_available())),
        )


def parse_networks(cidrs: list[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    return [ipaddress.ip_network(c, strict=False) for c in cidrs]


def is_exempt(host: str | None, networks) -> bool:
    """Internal callers (our own Next.js server on the private network) aren't limited."""
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    return any(address in net for net in networks)
