"""Scraper for BullionStar (bullionstar.com).

Prices are extracted from JSON-LD structured data on each product page.
Product URLs are collected from category listing pages (static HTML).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import Promotion, ScrapedProduct
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class BullionStarScraper(BaseScraper):
    dealer_name = "BullionStar"
    base_url = "https://www.bullionstar.com"

    CATEGORY_URLS = [
        "/buy/gold-bars",
        "/buy/gold-coins",
        "/buy/silver-bars",
    ]

    BRAND_FILTERS = re.compile(
        r"pamp|perth|argor|heraeus|nadir|maple|kangaroo", re.IGNORECASE
    )
    EXCLUDE_FILTERS = re.compile(
        r"400.oz|100.?oz|1000.oz|5.?oz|15.?kg|5.?kg|3.?oz|1.?20.?oz|2.?5g|2g|"
        r"coca.cola|maradona|lucky.cat|blessing|dragon|phoenix|"
        r"tiger|rabbit|horse|lunar|numismatic|collectible|circulated|"
        r"quarter.oz|tenth.oz|half.oz|1-4|1-2|1-10|1-20|"
        r"quarter.vy|half.vy|various.designs|various.years",
        re.IGNORECASE,
    )

    async def scrape(self) -> list[ScrapedProduct]:
        product_urls: set[str] = set()

        for path in self.CATEGORY_URLS:
            try:
                url = f"{self.base_url}{path}"
                html = await self.fetch(url)
                urls = self._extract_product_urls(html)
                product_urls.update(urls)
            except Exception as e:
                logger.error("%s: failed to get product list from %s: %s", self.dealer_name, path, e)

        logger.info("%s: found %d product URLs, fetching prices...", self.dealer_name, len(product_urls))

        products = []
        for url in sorted(product_urls):
            await asyncio.sleep(1)
            try:
                product = await self._fetch_product(url)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("%s: failed to fetch %s: %s", self.dealer_name, url, e)

        if not products:
            logger.warning("%s: no products found — possible layout change", self.dealer_name)

        return products

    def _extract_product_urls(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links = soup.select('a[href*="/buy/product/"]')
        urls = set()
        for link in links:
            href = link.get("href", "")
            if not self.BRAND_FILTERS.search(href):
                continue
            if self.EXCLUDE_FILTERS.search(href):
                continue
            if href.startswith("/"):
                href = f"{self.base_url}{href}"
            urls.add(href)
        return list(urls)

    async def _fetch_product(self, url: str) -> ScrapedProduct | None:
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "lxml")

        ld_scripts = soup.select('script[type="application/ld+json"]')
        for script in ld_scripts:
            try:
                data = json.loads(script.get_text())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict) or "offers" not in item:
                        continue

                    name = item.get("name", "").replace("Buy ", "")
                    offers = item["offers"]
                    if not offers:
                        continue

                    offer = offers[0]
                    price_str = offer.get("price")
                    if not price_str:
                        continue

                    price = Decimal(price_str)
                    if price < 10:
                        continue

                    in_stock = "InStock" in str(offer.get("availability", ""))

                    promotion = self._detect_promotion(soup, price)

                    return ScrapedProduct(
                        dealer=self.dealer_name,
                        name=name,
                        price=price,
                        currency="SGD",
                        url=url,
                        in_stock=in_stock,
                        promotion=promotion,
                    )
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        return None

    @staticmethod
    def _detect_promotion(soup: BeautifulSoup, current_price: Decimal) -> Promotion | None:
        """Detect if the product page shows a Limited Time Offer."""
        text = soup.get_text()
        if "limited time offer" not in text.lower():
            return None

        prices = re.findall(r"S\$([\d,]+\.\d{2})", text)
        valid = []
        for p in prices:
            try:
                val = Decimal(p.replace(",", ""))
                if val > 50:
                    valid.append(val)
            except Exception:
                pass

        if len(valid) >= 2:
            regular = max(valid)
            if regular > current_price:
                return Promotion(
                    regular_price=regular,
                    offer_price=current_price,
                    label="Limited Time Offer",
                )

        return None
