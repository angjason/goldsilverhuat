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

from models.product import Promotion, ScrapedProduct
from scrapers.playwright_base import PlaywrightScraper

logger = logging.getLogger(__name__)


class BullionStarScraper(PlaywrightScraper):
    dealer_name = "BullionStar"
    base_url = "https://www.bullionstar.com"
    page_timeout = 90000

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

        price, promotion = self._extract_price_and_promotion(row_text)
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
            promotion=promotion,
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
    def _extract_price_and_promotion(text: str) -> tuple[Decimal | None, Promotion | None]:
        """Extract price and detect promotions.

        BullionStar rows show either:
        - Tiered pricing: "1-9 S$830.47 / 10-29 S$827.98 / ..." → take first (qty 1)
        - Promo: "Limited Time Offer ... Regular Price S$830.47 Any Quantity S$751.97"

        "Any Quantity" alone is a bulk discount, NOT a promotion.
        Only treat as promotion when "Limited Time Offer" is also present.

        Returns (selling_price, promotion_or_None).
        """
        prices = re.findall(r"S\$([\d,]+\.\d{2})", text)
        if not prices:
            return None, None

        valid = []
        for p in prices:
            try:
                val = Decimal(p.replace(",", ""))
                if val > 50:
                    valid.append(val)
            except Exception:
                pass

        if not valid:
            return None, None

        is_promo = (
            "limited time offer" in text.lower()
            and "any quantity" in text.lower()
            and len(valid) >= 2
        )

        if is_promo:
            regular = max(valid)
            offer = min(valid)
            promotion = Promotion(
                regular_price=regular,
                offer_price=offer,
                label="Limited Time Offer",
            )
            return offer, promotion

        # Take the first (highest tier / qty 1) price
        return valid[0], None
