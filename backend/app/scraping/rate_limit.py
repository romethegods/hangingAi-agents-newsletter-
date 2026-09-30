"""Per-domain politeness: a token bucket for each host we crawl."""

from urllib.parse import urlsplit

from app.token_bucket import TokenBucket


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
