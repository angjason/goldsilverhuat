"""Precious Metals Price Comparison Tool.

Run: python main.py
     python main.py --output-dir docs --filename index
"""

import argparse
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
from services.spot_history import fetch_spot_history
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


async def main(output_dir: Path | None = None, filename: str | None = None) -> None:
    dealers = get_enabled_dealers()
    logger.info("Running scrapers for %d dealers...", len(dealers))

    scraper_tasks = [run_scraper(dealer) for dealer in dealers]
    spot_task = fetch_spot_prices()
    history_task = fetch_spot_history()

    results = await asyncio.gather(*scraper_tasks, spot_task, history_task)

    history = results[-1]
    spot = results[-2]
    scraper_results = results[:-2]

    all_products: list[ScrapedProduct] = []
    failed_dealers: list[str] = []
    for dealer, product_list in zip(dealers, scraper_results):
        if product_list:
            all_products.extend(product_list)
        else:
            failed_dealers.append(dealer.name)

    if failed_dealers:
        logger.warning("Dealers with no data: %s", ", ".join(failed_dealers))

    logger.info("Total products scraped: %d", len(all_products))

    normalized = normalize(all_products)
    logger.info("Matched products: %d", len(normalized))

    if not normalized:
        logger.warning("No products matched canonical definitions. Check scraper output.")
        sys.exit(1)

    comparisons = compare(normalized)

    print_results(comparisons, spot)

    csv_path = export(comparisons)
    html_path = export_html(
        comparisons, spot, history,
        output_dir=output_dir, filename=filename,
        failed_dealers=failed_dealers,
    )
    logger.info("Results exported to %s", csv_path)
    logger.info("HTML report: %s", html_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precious Metals Price Comparison")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for reports")
    parser.add_argument("--filename", type=str, default=None, help="HTML filename (e.g. 'index')")
    args = parser.parse_args()

    asyncio.run(main(output_dir=args.output_dir, filename=args.filename))
