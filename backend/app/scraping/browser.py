"""Headless Chrome via nodriver: one browser process, a bounded pool of tabs."""

import asyncio
import logging
import re
import subprocess
from typing import Protocol

import nodriver
from nodriver.core.config import find_chrome_executable

log = logging.getLogger(__name__)

BOT_TOKEN = "HangingAiBot/0.1 (+https://hangingai.com/bot)"


class PageFetcher(Protocol):
    async def fetch_html(self, url: str) -> str: ...


def honest_user_agent(executable: str) -> str:
    """A normal Chrome UA plus our bot token, so site owners can identify and block us."""
    try:
        version = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=10
        )
        match = re.search(r"(\d+)\.\d+", version.stdout)
    except (OSError, subprocess.TimeoutExpired):
        match = None
    major = match.group(1) if match else "140"
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36 {BOT_TOKEN}"
    )


class BrowserPool:
    def __init__(
        self,
        *,
        max_tabs: int = 3,
        headless: bool = True,
        sandbox: bool = True,
        executable: str | None = None,
        settle_seconds: float = 3.0,
        page_timeout_seconds: float = 45.0,
    ) -> None:
        self._tabs = asyncio.Semaphore(max_tabs)
        self._headless = headless
        self._sandbox = sandbox
        self._executable = executable
        self._settle = settle_seconds
        self._timeout = page_timeout_seconds
        self._browser: nodriver.Browser | None = None

    async def start(self) -> None:
        executable = self._executable or find_chrome_executable()
        self._browser = await nodriver.start(
            headless=self._headless,
            sandbox=self._sandbox,
            browser_executable_path=executable,
            browser_args=[f"--user-agent={honest_user_agent(executable)}"],
        )
        log.info("browser started: %s", executable)

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.stop()
            self._browser = None

    async def fetch_html(self, url: str) -> str:
        if self._browser is None:
            raise RuntimeError("BrowserPool.start() was not called")
        async with self._tabs:
            tab = await asyncio.wait_for(self._browser.get(url, new_tab=True), self._timeout)
            try:
                await tab.sleep(self._settle)  # let client-side rendering finish
                return await asyncio.wait_for(tab.get_content(), self._timeout)
            finally:
                await tab.close()
