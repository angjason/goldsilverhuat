"""Precious Metals Price Comparison Tool.

Run: python main.py
"""

import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

# Ensure TMPDIR is writable (needed for Playwright on macOS)
_tmp = Path(__file__).parent / ".tmp"
_tmp.mkdir(exist_ok=True)
os.environ.setdefault("TMPDIR", str(_tmp))

from config.dealers import get_enabled_dealers
from models.product import ScrapedProduct
from output.console import print_results
from output.csv_export import export
from output.html_report import export_html
from services.comparator import compare
from services.normalizer import normalize
from services.spot_price import fetch_spot_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_scraper(dealer_config) -> list[ScrapedProduct]:
    """Run a single dealer's scraper with error isolation."""
    try:
        module = importlib.import_module(dealer_config.scraper_module)
        scraper_class = None

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and hasattr(attr, "scrape")
                and attr_name != "BaseScraper"
                and hasattr(attr, "dealer_name")
            ):
                scraper_class = attr
                break

        if scraper_class is None:
            logger.error("No scraper class found in %s", dealer_config.scraper_module)
            return []

        async with scraper_class() as scraper:
            products = await scraper.scrape()
            logger.info(
                "%s: scraped %d products",
                dealer_config.name,
                len(products),
            )
            return products

    except Exception as e:
        logger.error("%s: scraper failed — %s", dealer_config.name, e)
        return []


async def main() -> None:
    dealers = get_enabled_dealers()
    logger.info("Running scrapers for %d dealers...", len(dealers))

    scraper_tasks = [run_scraper(dealer) for dealer in dealers]
    spot_task = fetch_spot_prices()

    results = await asyncio.gather(*scraper_tasks, spot_task)

    spot = results[-1]
    scraper_results = results[:-1]

    all_products: list[ScrapedProduct] = []
    for product_list in scraper_results:
        all_products.extend(product_list)

    logger.info("Total products scraped: %d", len(all_products))

    normalized = normalize(all_products)
    logger.info("Matched products: %d", len(normalized))

    if not normalized:
        logger.warning("No products matched canonical definitions. Check scraper output.")
        sys.exit(1)

    comparisons = compare(normalized)

    print_results(comparisons, spot)

    csv_path = export(comparisons)
    html_path = export_html(comparisons, spot)
    logger.info("Results exported to %s", csv_path)
    logger.info("HTML report: %s", html_path)


if __name__ == "__main__":
    asyncio.run(main())
