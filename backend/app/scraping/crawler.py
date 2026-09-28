"""Polite page loading: robots.txt check -> per-domain rate limit -> browser."""

from app.scraping.browser import PageFetcher
from app.scraping.rate_limit import DomainRateLimiter
from app.scraping.robots import RobotsCache

# Real listing pages are hundreds of KB; bot walls ("Access Denied", CNN's
# "Unknown Error") are tiny.
MIN_PAGE_BYTES = 2_000


class CrawlError(Exception):
    pass


class DisallowedByRobots(CrawlError):
    pass


class BlockedPage(CrawlError):
    pass


class Crawler:
    def __init__(
        self, fetcher: PageFetcher, robots: RobotsCache, limiter: DomainRateLimiter
    ) -> None:
        self._fetcher = fetcher
        self._robots = robots
        self._limiter = limiter

    async def get(self, url: str) -> str:
        if not await self._robots.allowed(url):
            raise DisallowedByRobots(f"robots.txt disallows {url}")
        await self._limiter.wait(url, await self._robots.crawl_delay(url))
        html = await self._fetcher.fetch_html(url)
        if len(html) < MIN_PAGE_BYTES:
            raise BlockedPage(f"{url} returned {len(html)} bytes; likely a bot wall")
        return html
