"""Scraper for BullionStar (bullionstar.com).

Prices are dynamically rendered via JavaScript — requires Playwright.
Products are in table rows: <tr class="pricing-row product-price-update">
Each row has a link to /buy/product/{slug} and prices in S$ format.
We take the first price (1-9 qty retail price).
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.playwright_base import PlaywrightScraper

logger = logging.getLogger(__name__)


class BullionStarScraper(PlaywrightScraper):
    dealer_name = "BullionStar"
    base_url = "https://www.bullionstar.com"

    CATEGORY_URLS = [
        "/buy/gold-bars",
        "/buy/gold-coins",
        "/buy/silver-bars",
    ]

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        for path in self.CATEGORY_URLS:
            try:
                url = f"{self.base_url}{path}"
                html = await self._get_page_content(url, wait_selector="td.price")
                page_products = self._parse_listing(html)
                products.extend(page_products)
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

    def _parse_listing(self, html: str) -> list[ScrapedProduct]:
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []

        rows = soup.select("tr.pricing-row, tr.product-price-update, tr[class*='pricing-row']")

        if not rows:
            rows = soup.select("tr")
            rows = [r for r in rows if r.select_one("a[href*='/buy/product/']")]

        seen_urls: set[str] = set()

        for row in rows:
            try:
                product = self._parse_row(row)
                if product and product.url not in seen_urls:
                    products.append(product)
                    seen_urls.add(product.url)
            except Exception as e:
                logger.debug("Failed to parse row: %s", e)

        return products

    def _parse_row(self, row) -> ScrapedProduct | None:
        link = row.select_one("a[href*='/buy/product/']")
        if not link:
            return None

        href = link.get("href", "")
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        row_text = row.get_text()

        name = self._extract_name(row_text, href)
        if not name:
            return None

        price = self._extract_first_price(row_text)
        if price is None:
            return None

        in_stock = "in stock" in row_text.lower()

        return ScrapedProduct(
            dealer=self.dealer_name,
            name=name,
            price=price,
            currency="SGD",
            url=url,
            in_stock=in_stock,
        )

    def _extract_name(self, row_text: str, href: str) -> str:
        """Build product name from URL slug and row text.

        BullionStar row text: '1 troy oz (31.1 gram) - Lady Fortuna Design'
        URL slug: 'gold-pamp-1oz-lady-fortuna-design'
        We combine both for a matchable name like:
        'Gold PAMP 1oz Lady Fortuna Design'
        """
        slug = href.split("/")[-1] if "/" in href else href
        slug_name = slug.replace("-", " ").title()

        lines = [line.strip() for line in row_text.split("\n") if line.strip()]
        description = ""
        for line in lines:
            if "troy oz" in line or "gram" in line or "kg" in line:
                cleaned = re.sub(r"Limited Time Offer\s*", "", line).strip()
                if cleaned:
                    description = cleaned
                    break

        return f"{slug_name} {description}".strip()

    @staticmethod
    def _extract_first_price(text: str) -> Decimal | None:
        """Extract the first (retail qty 1-9) S$ price from the row."""
        prices = re.findall(r"S\$([\d,]+\.\d{2})", text)
        if not prices:
            return None

        cleaned = prices[0].replace(",", "")
        try:
            price = Decimal(cleaned)
            if price > 50:
                return price
        except Exception:
            pass

        return None
