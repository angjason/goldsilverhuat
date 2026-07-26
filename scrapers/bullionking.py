"""Scraper for BullionKing (bullionking.sg).

JavaScript-rendered product pages — requires Playwright.
Products: PAMP, Argor-Heraeus gold bars, Canadian Maple Leaf silver coins.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.playwright_base import PlaywrightScraper

logger = logging.getLogger(__name__)


class BullionKingScraper(PlaywrightScraper):
    dealer_name = "BullionKing"
    base_url = "https://www.bullionking.sg"

    CATEGORY_URLS = [
        "/buy-gold-silver",
    ]

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        for path in self.CATEGORY_URLS:
            try:
                url = f"{self.base_url}{path}"
                html = await self._get_page_content(url, wait_selector=".product, [class*='price']")
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

        items = soup.select(
            ".product-card, .product-item, [class*='product'], "
            ".grid-item, .shop-item"
        )

        if not items:
            items = soup.find_all("a", href=re.compile(r"/product/"))

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
        name_el = (
            item.select_one("h2, h3, h4, .product-title, .product-name")
            or item.select_one("a[href*='/product/']")
        )
        if not name_el:
            text = item.get_text(strip=True)
            if len(text) > 10 and len(text) < 200:
                name = text.split("\n")[0].strip()
            else:
                return None
        else:
            name = name_el.get_text(strip=True)

        if not name or len(name) < 5:
            return None

        price = self._extract_price(item)
        if price is None:
            return None

        link = item.select_one("a[href]") or (item if item.name == "a" else None)
        href = link.get("href", "") if link else ""
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        text = item.get_text().lower()
        in_stock = "sold out" not in text and "out of stock" not in text

        return ScrapedProduct(
            dealer=self.dealer_name,
            name=name,
            price=price,
            currency="SGD",
            url=url,
            in_stock=in_stock,
        )

    @staticmethod
    def _extract_price(item) -> Decimal | None:
        text = item.get_text()
        patterns = [
            r"S\$\s*([\d,]+\.\d{2})",
            r"SGD\s*([\d,]+\.\d{2})",
            r"\$\s*([\d,]+\.\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                cleaned = match.group(1).replace(",", "")
                try:
                    price = Decimal(cleaned)
                    if price > 10:
                        return price
                except Exception:
                    continue

        return None
