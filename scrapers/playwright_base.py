"""Base class for scrapers that require JavaScript rendering via Playwright."""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import ClassVar

from config.constants import CHROME_PATH, USER_AGENT
from models.product import ScrapedProduct

logger = logging.getLogger(__name__)


class PlaywrightScraper(abc.ABC):
    """Base for dealers whose prices load via JavaScript.

    Launches one browser instance and reuses it for all page loads.
    """

    dealer_name: ClassVar[str]
    base_url: ClassVar[str]

    max_retries: int = 2
    page_timeout: int = 45000

    def __init__(self) -> None:
        self._browser = None
        self._playwright = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _ensure_browser(self):
        """Launch browser if not already running."""
        if self._browser:
            return

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch_kwargs = {"headless": True}
        if CHROME_PATH.exists():
            launch_kwargs["executable_path"] = str(CHROME_PATH)

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def _get_page_content(self, url: str, wait_selector: str | None = None) -> str:
        """Render a page with Playwright and return the HTML after JS execution."""
        await self._ensure_browser()

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                page = await self._browser.new_page(user_agent=USER_AGENT)
                wait_until = "domcontentloaded" if wait_selector else "networkidle"
                await page.goto(url, timeout=self.page_timeout, wait_until=wait_until)

                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=30000)
                    except Exception:
                        pass

                content = await page.content()
                await page.close()
                return content

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(
                        "%s: Playwright attempt %d failed for %s (%s)",
                        self.dealer_name,
                        attempt,
                        url,
                        e,
                    )
                    await asyncio.sleep(2)

        logger.error(
            "%s: all Playwright attempts failed for %s",
            self.dealer_name,
            url,
        )
        raise last_error

    @abc.abstractmethod
    async def scrape(self) -> list[ScrapedProduct]:
        ...
