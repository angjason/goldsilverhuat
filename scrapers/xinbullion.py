"""Scraper for Xin Bullion (xinbullion.com).

WooCommerce-based with server-rendered prices in SGD.
Categories: /product-category/gold/ and /product-category/silver/.
Uses tiered pricing — we take the single-unit (highest) price.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from bs4 import BeautifulSoup

from models.product import ScrapedProduct
from scrapers.base import BaseScraper
from scrapers.utils import parse_sgd_price, resolve_url

logger = logging.getLogger(__name__)


class XinBullionScraper(BaseScraper):
    dealer_name = "Xin Bullion"
    base_url = "https://xinbullion.com"

    CATEGORY_URLS = [
        "/product-category/gold/",
        "/product-category/silver/",
    ]

    async def scrape(self) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []

        for path in self.CATEGORY_URLS:
            try:
                url = f"{self.base_url}{path}"
                html = await self.fetch(url)
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

        items = soup.select("li.product")
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
        name_el = item.select_one("h2, h3, .woocommerce-loop-product__title")
        if not name_el:
            return None

        name = name_el.get_text(strip=True)
        if not name or len(name) < 5:
            return None

        price_el = item.select_one(".woocommerce-Price-amount, .price .amount, .price")
        if not price_el:
            return None

        price = parse_sgd_price(price_el.get_text(strip=True))
        if price is None:
            return None

        link_el = item.select_one("a[href]")
        url = resolve_url(link_el["href"], self.base_url) if link_el else ""

        in_stock = "outofstock" not in item.get("class", [])

        return ScrapedProduct(
            dealer=self.dealer_name,
            name=name,
            price=price,
            currency="SGD",
            url=url,
            in_stock=in_stock,
        )


Scraper = XinBullionScraper
