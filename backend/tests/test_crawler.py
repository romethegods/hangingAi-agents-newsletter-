from pathlib import Path

import pytest

from app.scraping.crawler import BlockedPage, Crawler, DisallowedByRobots
from app.scraping.rate_limit import DomainRateLimiter
from app.scraping.robots import RobotsCache

FIXTURES = Path(__file__).parent / "fixtures"
ROBOTS = """
User-agent: ClaudeBot
Disallow: /

User-agent: *
Disallow: /search
Crawl-delay: 1
"""


class FakeFetcher:
    def __init__(self, html: str) -> None:
        self.html = html
        self.urls: list[str] = []

    async def fetch_html(self, url: str) -> str:
        self.urls.append(url)
        return self.html


def robots_with(status: int, body: str = ""):
    calls = []

    async def loader(url: str) -> tuple[int, str]:
        calls.append(url)
        return status, body

    return RobotsCache(loader), calls


async def test_robots_rules_apply_to_our_agent() -> None:
    robots, calls = robots_with(200, ROBOTS)
    assert await robots.allowed("https://site.com/2026/09/story")
    assert not await robots.allowed("https://site.com/search?q=ai")
    assert await robots.crawl_delay("https://site.com/") == 1.0
    assert calls == ["https://site.com/robots.txt"]  # cached after the first lookup


async def test_missing_robots_allows_and_server_error_disallows() -> None:
    missing, _ = robots_with(404)
    assert await missing.allowed("https://site.com/anything")
    broken, _ = robots_with(503)
    assert not await broken.allowed("https://site.com/anything")


async def test_crawler_refuses_disallowed_urls_without_loading_them() -> None:
    robots, _ = robots_with(200, ROBOTS)
    fetcher = FakeFetcher("<html>" + "x" * 5000)
    crawler = Crawler(fetcher, robots, DomainRateLimiter(0.01))
    with pytest.raises(DisallowedByRobots):
        await crawler.get("https://site.com/search?q=ai")
    assert fetcher.urls == []


async def test_crawler_detects_real_bot_wall() -> None:
    """cnn_tech.html is what CNN actually served our headless browser."""
    robots, _ = robots_with(404)
    fetcher = FakeFetcher((FIXTURES / "cnn_tech.html").read_text())
    with pytest.raises(BlockedPage):
        await Crawler(fetcher, robots, DomainRateLimiter(0.01)).get(
            "https://www.cnn.com/business/tech"
        )
