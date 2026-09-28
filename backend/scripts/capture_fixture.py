"""Save a rendered page's HTML as a test fixture.

When a site changes its markup and a parser test breaks, re-capture:

    uv run python scripts/capture_fixture.py \
        https://github.com/trending tests/fixtures/github_trending.html
"""

import sys
from pathlib import Path

import nodriver


async def capture(url: str, out: Path, settle_seconds: float = 4.0) -> None:
    browser = await nodriver.start(headless=True)
    try:
        page = await browser.get(url)
        await page.sleep(settle_seconds)
        html = await page.get_content()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"saved {len(html):,} bytes -> {out}")
    finally:
        browser.stop()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: capture_fixture.py <url> <output.html>")
    nodriver.loop().run_until_complete(capture(sys.argv[1], Path(sys.argv[2])))
