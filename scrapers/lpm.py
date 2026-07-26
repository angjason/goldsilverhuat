"""Scraper for LPM Singapore (lpm.sg).

LPM uses Cloudflare protection. Bypassed with a persistent browser context
and --disable-blink-features=AutomationControlled.
Magento-based with .product-item-info selectors. Prices in SG$ format.
"""

from __future__ import annotations

import asyncio
import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.playwright_base import CHROME_PATH

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent.parent / ".chrome-lpm"


class LPMScraper:
    dealer_name: ClassVar[str] = "LPM"
    base_url: ClassVar[str] = "https://www.lpm.sg"

    CATEGORY_URLS = [
        "/sg_en/gold/popular-gold-bullion.html",
        "/sg_en/silver/silver-bars.html",
    ]

    max_retries: int = 2

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def scrape(self) -> list[ScrapedProduct]:
        from playwright.async_api import async_playwright

        products: list[ScrapedProduct] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch_persistent_context(
                    str(PROFILE_DIR),
                    headless=False,
                    executable_path=str(CHROME_PATH) if CHROME_PATH.exists() else None,
                    args=["--disable-blink-features=AutomationControlled"],
                )

                page = browser.pages[0] if browser.pages else await browser.new_page()

                for path in self.CATEGORY_URLS:
                    try:
                        url = f"{self.base_url}{path}"
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(4000)

                        content = await page.content()

                        if "just a moment" in content.lower():
                            logger.warning("%s: Cloudflare challenge on %s", self.dealer_name, path)
                            continue

                        page_products = self._parse_listing(content)
                        products.extend(page_products)
                    except Exception as e:
                        logger.error("%s: failed to scrape %s: %s", self.dealer_name, path, e)

                await browser.close()

        except Exception as e:
            logger.error("%s: browser launch failed: %s", self.dealer_name, e)

        if not products:
            logger.warning("%s: no products found — possible layout change or Cloudflare block", self.dealer_name)

        return products

    def _parse_listing(self, html: str) -> list[ScrapedProduct]:
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []

        items = soup.select(".product-item-info, .product-item")
        seen: set[str] = set()

        for item in items:
            try:
                product = self._parse_item(item)
                if product and product.name not in seen:
                    products.append(product)
                    seen.add(product.name)
            except Exception as e:
                logger.debug("Failed to parse item: %s", e)

        return products

    def _parse_item(self, item) -> ScrapedProduct | None:
        name_el = item.select_one(".product-item-link")
        if not name_el:
            return None

        name = name_el.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        price_el = item.select_one("[data-price-amount]")
        if price_el:
            try:
                price = Decimal(price_el["data-price-amount"])
            except Exception:
                price = self._parse_price_text(item)
        else:
            price = self._parse_price_text(item)

        if price is None:
            return None

        href = name_el.get("href", "")
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        text = item.get_text().lower()
        in_stock = "out of stock" not in text

        return ScrapedProduct(
            dealer=self.dealer_name,
            name=name,
            price=price,
            currency="SGD",
            url=url,
            in_stock=in_stock,
        )

    @staticmethod
    def _parse_price_text(item) -> Decimal | None:
        price_el = item.select_one(".price")
        if not price_el:
            return None
        match = re.search(r"([\d,]+\.\d{2})", price_el.get_text())
        if not match:
            return None
        try:
            return Decimal(match.group(1).replace(",", ""))
        except Exception:
            return None
