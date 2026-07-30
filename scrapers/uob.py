"""Scraper for UOB (uobgroup.com).

UOB lists all gold and silver prices on a single page in a simple HTML table.
Columns: DESCRIPTION | UNIT | BANK SELLS (SGD) | BANK BUYS (SGD)
'BANK SELLS' is the retail buy price (what you pay).
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.playwright_base import PlaywrightScraper

logger = logging.getLogger(__name__)


class UOBScraper(PlaywrightScraper):
    dealer_name = "UOB"
    base_url = "https://www.uobgroup.com"

    PRICE_URL = "/online-rates/gold-and-silver-prices.page"

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        try:
            url = f"{self.base_url}{self.PRICE_URL}"
            html = await self._get_page_content(url, wait_selector="table td")
            products = self._parse_price_table(html)
        except Exception as e:
            logger.error("%s: failed to scrape: %s", self.dealer_name, e)

        if not products:
            logger.warning(
                "%s: no products found — possible layout change",
                self.dealer_name,
            )

        return products

    def _parse_price_table(self, html: str) -> list[ScrapedProduct]:
        soup = BeautifulSoup(html, "lxml")
        products: list[ScrapedProduct] = []

        tables = soup.select("table")
        if not tables:
            return []

        table = tables[0]
        rows = table.select("tr")

        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            description = cells[0].get_text(strip=True)
            unit = cells[1].get_text(strip=True)
            sell_price_text = cells[2].get_text(strip=True)

            if not description or not sell_price_text:
                continue

            price = self._parse_price(sell_price_text)
            if price is None:
                continue

            name = f"{description} {unit}"

            products.append(
                ScrapedProduct(
                    dealer=self.dealer_name,
                    name=name,
                    price=price,
                    currency="SGD",
                    url=f"{self.base_url}{self.PRICE_URL}",
                    in_stock=True,
                )
            )

        return products

    @staticmethod
    def _parse_price(text: str) -> Decimal | None:
        match = re.search(r"([\d,]+\.\d{2})", text)
        if not match:
            return None
        cleaned = match.group(1).replace(",", "")
        try:
            return Decimal(cleaned)
        except Exception:
            return None

Scraper = UOBScraper
