"""Scraper for Big Bullion SG (bigbullionsg.com).

JavaScript-rendered custom site. Products listed at /buy?metal=gold and /buy?metal=silver.
Prices in S$X,XXX.XX format. Product links at /products/[slug].
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.playwright_base import PlaywrightScraper

logger = logging.getLogger(__name__)


class BigBullionScraper(PlaywrightScraper):
    dealer_name = "Big Bullion"
    base_url = "https://bigbullionsg.com"

    CATEGORY_URLS = [
        "/buy?metal=gold",
        "/buy?metal=silver",
    ]

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        for path in self.CATEGORY_URLS:
            try:
                url = f"{self.base_url}{path}"
                html = await self._get_page_content(url, wait_selector="a[href*='/products/']")
                page_products = self._parse_listing(html)
                products.extend(page_products)
            except Exception as e:
                logger.error("%s: failed to scrape %s: %s", self.dealer_name, path, e)

        if not products:
            logger.warning("%s: no products found — possible layout change", self.dealer_name)

        return products

    def _parse_listing(self, html: str) -> list[ScrapedProduct]:
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []
        seen: set[str] = set()

        links = soup.select("a[href*='/products/']")

        for link in links:
            try:
                product = self._parse_item(link)
                if product and product.name not in seen:
                    products.append(product)
                    seen.add(product.name)
            except Exception as e:
                logger.debug("Failed to parse item: %s", e)

        return products

    def _parse_item(self, link) -> ScrapedProduct | None:
        name_el = link.select_one("h3")
        if not name_el:
            return None

        name = name_el.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        price = self._extract_price(link.get_text())
        if price is None:
            return None

        href = link.get("href", "")
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        text = link.get_text().lower()
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
    def _extract_price(text: str) -> Decimal | None:
        match = re.search(r"S\$\s*([\d,]+\.\d{2})", text)
        if not match:
            return None
        cleaned = match.group(1).replace(",", "")
        try:
            price = Decimal(cleaned)
            if price > 10:
                return price
        except Exception:
            pass
        return None


Scraper = BigBullionScraper
