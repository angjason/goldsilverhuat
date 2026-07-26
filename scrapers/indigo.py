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
        """Scrape all pages in a category."""
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

        return products

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
        url = href if href.startswith("http") else f"{self.base_url}{href}"

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
        """Parse 'SGD 5,240.38' or 'From SGD 2,571.73' format."""
        match = re.search(r"SGD\s*([\d,]+\.\d{2})", text)
        if not match:
            return None
        cleaned = match.group(1).replace(",", "")
        try:
            price = Decimal(cleaned)
            if price < 10:
                return None
            return price
        except Exception:
            return None
