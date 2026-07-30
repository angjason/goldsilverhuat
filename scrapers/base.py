from __future__ import annotations

import abc
import asyncio
import logging
from typing import ClassVar

import httpx

from config.constants import USER_AGENT
from models.product import ScrapedProduct

logger = logging.getLogger(__name__)


class BaseScraper(abc.ABC):
    """Base class for all dealer scrapers.

    Subclasses must define `dealer_name` and implement `scrape`.
    """

    dealer_name: ClassVar[str]
    base_url: ClassVar[str]

    max_retries: int = 3
    retry_backoff: float = 1.0
    timeout: float = 30.0

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()

    async def fetch(self, url: str) -> str:
        """Fetch a URL with retry and exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                return response.text
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = self.retry_backoff * (2 ** (attempt - 1))
                    logger.warning(
                        "%s: attempt %d failed for %s (%s), retrying in %.1fs",
                        self.dealer_name,
                        attempt,
                        url,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)

        logger.error(
            "%s: all %d attempts failed for %s",
            self.dealer_name,
            self.max_retries,
            url,
        )
        raise last_error

    @abc.abstractmethod
    async def scrape(self) -> list[ScrapedProduct]:
        """Scrape the dealer's website and return all found products."""
        ...
