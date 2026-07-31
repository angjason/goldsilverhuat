"""Scraper for Indigo Precious Metals (indigopreciousmetals.com).

Custom frontend with product grid in section.product-grid.
Product names in div.title, prices as 'SGD X,XXX.XX' in parent container.
Prices auto-refresh based on spot.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.base import BaseScraper
from scrapers.utils import resolve_url

logger = logging.getLogger(__name__)


class IndigoScraper(BaseScraper):
    dealer_name = "Indigo Precious Metals"
    base_url = "https://www.indigopreciousmetals.com"

    CATEGORY_URLS = [
        "/bullion-products/gold/gold-bars.html",
        "/bullion-products/gold/gold-coins.html",
        "/bullion-products/silver/silver-bars.html",
    ]

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        for path in self.CATEGORY_URLS:
            try:
                category_products = await self._scrape_category(path)
                products.extend(category_products)
            except Exception as e:
                logger.error(
                    "%s: failed to scrape %s: %s",
                    self.dealer_name,
                    path,
                    e,
                )

        if not products:
            logger.warning(
                "%s: no products found — possible layout change",
                self.dealer_name,
            )

        return products

    async def _scrape_category(self, path: str) -> list[ScrapedProduct]:
        """Scrape all pages in a category, then fetch Tier 1 prices from detail pages."""
        products: list[ScrapedProduct] = []
        page = 1

        while True:
            url = f"{self.base_url}{path}"
            if page > 1:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}p={page}"

            try:
                html = await self.fetch(url)
            except Exception:
                break

            page_products = self._parse_listing(html)
            if not page_products:
                break

            products.extend(page_products)
            page += 1

            if page > 10:
                break

        await self._fetch_tier1_prices(products)
        return products

    async def _fetch_tier1_prices(self, products: list[ScrapedProduct]) -> None:
        """Fetch Tier 1 (retail) prices from detail pages sequentially.

        The listing page shows the bulk discount (10+ qty) price.
        The detail page has itemprop="price" content="X" with the Tier 1 price.
        """
        import asyncio

        for product in products:
            if not product.url:
                continue
            try:
                await asyncio.sleep(1)
                html = await self.fetch(product.url)
                soup = BeautifulSoup(html, "lxml")
                price_el = soup.select_one('[itemprop="price"][content]')
                if price_el:
                    content = price_el.get("content", "")
                    tier1_price = Decimal(content.replace(",", ""))
                    if tier1_price > 10:
                        product.price = tier1_price
            except Exception:
                pass

    def _parse_listing(self, html: str) -> list[ScrapedProduct]:
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []

        grid = soup.select_one("section.product-grid")
        if not grid:
            return []

        title_els = grid.select("div.title, .title")
        if not title_els:
            return []

        for title_el in title_els:
            try:
                product = self._parse_product_card(title_el)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("Failed to parse product: %s", e)

        return products

    def _parse_product_card(self, title_el) -> ScrapedProduct | None:
        name = title_el.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        card = title_el.parent
        if not card:
            return None

        card_text = card.get_text()
        price = self._extract_price(card_text)
        if price is None:
            return None

        link = card.select_one("a[href]")
        href = link.get("href", "") if link else ""
        url = resolve_url(href, self.base_url)

        in_stock = "out of stock" not in card_text.lower()

        return ScrapedProduct(
            dealer=self.dealer_name,
            name=name,
            price=price,
            currency="SGD",
            url=url,
            in_stock=in_stock,
        )

    @staticmethod
    def _extract_price(text: str) -> Decimal | None:
        from scrapers.utils import parse_sgd_price
        return parse_sgd_price(text)

Scraper = IndigoScraper
