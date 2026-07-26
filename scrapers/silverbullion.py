"""Scraper for Silver Bullion (silverbullion.com.sg).

Prices are server-rendered with tier-based pricing.
We use Tier 1 (standard retail) price.
Product URLs: /Product/Detail/{slug}
Product names are derived from section headers + URL slugs.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class SilverBullionScraper(BaseScraper):
    dealer_name = "Silver Bullion"
    base_url = "https://www.silverbullion.com.sg"

    CATEGORY_URLS = [
        "/Shop/Buy/Gold_Bars",
        "/Shop/Buy/Gold_Coins",
        "/Shop/Buy/Silver_Bars",
    ]

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        for category_path in self.CATEGORY_URLS:
            try:
                url = f"{self.base_url}{category_path}"
                html = await self.fetch(url)
                category_products = self._parse_product_list(html)
                products.extend(category_products)
            except Exception as e:
                logger.error(
                    "%s: failed to scrape %s: %s",
                    self.dealer_name,
                    category_path,
                    e,
                )

        if not products:
            logger.warning(
                "%s: no products found — possible layout change",
                self.dealer_name,
            )

        return products

    def _parse_product_list(self, html: str) -> list[ScrapedProduct]:
        """Parse the Silver Bullion product listing page."""
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []

        links = soup.select("a[href*='/Product/Detail/']")
        seen_hrefs: set[str] = set()

        for link in links:
            href = link.get("href", "")
            if href in seen_hrefs:
                continue

            row = link.find_parent("tr")
            if not row:
                continue

            row_text = row.get_text()
            prices = re.findall(r"([\d,]+\.\d{2})", row_text)
            real_prices = [p for p in prices if float(p.replace(",", "")) > 100]

            if not real_prices:
                continue

            seen_hrefs.add(href)

            product_name = self._build_product_name(link, row)
            if not product_name:
                continue

            try:
                price = Decimal(real_prices[0].replace(",", ""))
            except Exception:
                continue

            url = href if href.startswith("http") else f"{self.base_url}{href}"

            in_stock = "in-stock" in row_text.lower() or "in stock" in row_text.lower()

            products.append(
                ScrapedProduct(
                    dealer=self.dealer_name,
                    name=product_name,
                    price=price,
                    currency="SGD",
                    url=url,
                    in_stock=in_stock,
                )
            )

        return products

    def _build_product_name(self, link, row) -> str:
        """Build a descriptive product name from section header and URL slug.

        Silver Bullion's listing uses section headers like
        'Perth Mint Minted Gold Bars' and links containing the weight.
        We combine these into: 'Perth Mint Minted Gold Bar 1oz'
        """
        href = link.get("href", "")
        slug = href.split("/")[-1] if "/" in href else href

        name = slug.replace("_", " ")

        for sibling in row.find_all_previous(["tr", "a"]):
            text = sibling.get_text(strip=True)
            if any(kw in text for kw in ["Gold Bars", "Gold Coins", "Silver Bars", "Silver Coins"]):
                weight = self._extract_weight(slug)
                if weight:
                    section_name = text.rstrip("s")
                    return f"{section_name} {weight}"
                break

        return name

    @staticmethod
    def _extract_weight(slug: str) -> str:
        """Extract weight from URL slug like 'Gold_Minted_Bar_Perth_Mint_1oz'."""
        match = re.search(r"(\d+(?:oz|kg|g))", slug, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""
