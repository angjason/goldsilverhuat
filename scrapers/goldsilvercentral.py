"""Scraper for GoldSilver Central (goldsilvercentral.com.sg).

WooCommerce-based with server-rendered prices.
Product names are in the title attribute of thumbnail links.
Prices are in SGD format: S$5,530.21
The /shop/ page lists all products with pagination (?product-page=N).

Uses Playwright in CI to avoid IP-based blocking from cloud environments.
Falls back to httpx locally for speed.
"""

from __future__ import annotations

import logging
import os
import re
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.playwright_base import PlaywrightScraper

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class GoldSilverCentralScraper(PlaywrightScraper):
    dealer_name = "GoldSilver Central"
    base_url = "https://www.goldsilvercentral.com.sg"

    SHOP_URL = "/shop/"

    def __init__(self) -> None:
        super().__init__()
        self._use_playwright = os.environ.get("CI") == "true"
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        if not self._use_playwright:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            )
        return self

    async def __aexit__(self, *exc):
        if self._http_client:
            await self._http_client.aclose()
        await super().__aexit__(*exc)

    async def _fetch_page(self, url: str) -> str:
        if self._use_playwright:
            return await self._get_page_content(url, wait_selector="li.product")
        response = await self._http_client.get(url)
        response.raise_for_status()
        return response.text

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        try:
            products = await self._scrape_paginated()
        except Exception as e:
            logger.error("%s: failed to scrape shop: %s", self.dealer_name, e)

        if not products:
            logger.warning(
                "%s: no products found — possible layout change",
                self.dealer_name,
            )

        return products

    async def _scrape_paginated(self) -> list[ScrapedProduct]:
        """Scrape all pages of the shop."""
        products: list[ScrapedProduct] = []
        seen_urls: set[str] = set()
        page = 1

        while True:
            if page == 1:
                url = f"{self.base_url}{self.SHOP_URL}"
            else:
                url = f"{self.base_url}{self.SHOP_URL}page/{page}/"

            try:
                html = await self._fetch_page(url)
            except Exception:
                break

            page_products = self._parse_product_grid(html)
            if not page_products:
                break

            new_products = [p for p in page_products if p.url not in seen_urls]
            if not new_products:
                break
            for p in new_products:
                seen_urls.add(p.url)

            products.extend(new_products)
            page += 1

            if page > 15:
                break

        return products

    def _parse_product_grid(self, html: str) -> list[ScrapedProduct]:
        """Parse a WooCommerce product grid page."""
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []

        items = soup.select("li.product")
        if not items:
            return []

        for item in items:
            try:
                product = self._parse_product_item(item)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("Failed to parse product item: %s", e)

        return products

    def _parse_product_item(self, item) -> ScrapedProduct | None:
        """Extract product data from a single li.product element."""
        title_link = item.select_one("a.thumbnail[title], a[title]")
        if title_link:
            name = title_link.get("title", "").strip()
        else:
            name_el = item.select_one("h2, h3, .product-title")
            name = name_el.get_text(strip=True) if name_el else ""

        if not name:
            return None

        price_el = item.select_one(".woocommerce-Price-amount, .price .amount, .price")
        if not price_el:
            return None

        price = self._parse_price(price_el.get_text(strip=True))
        if price is None:
            return None

        link_el = item.select_one("a[href*='/shop/']") or item.select_one("a[href]")
        url = link_el["href"] if link_el else ""

        in_stock = "instock" in item.get("class", []) or "outofstock" not in item.get("class", [])

        return ScrapedProduct(
            dealer=self.dealer_name,
            name=name,
            price=price,
            currency="SGD",
            url=url,
            in_stock=in_stock,
        )

    @staticmethod
    def _parse_price(text: str) -> Decimal | None:
        """Parse price from text like 'S$5,530.21' or 'SGD 5,530.21'."""
        match = re.search(r"[\d,]+\.\d{2}", text)
        if not match:
            return None
        cleaned = match.group().replace(",", "")
        try:
            return Decimal(cleaned)
        except Exception:
            return None
