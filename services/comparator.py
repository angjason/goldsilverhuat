"""Price comparison — groups normalized prices by product and ranks them."""

from collections import defaultdict

from config.products import PRODUCTS
from models.product import ComparisonResult, NormalizedPrice


def compare(prices: list[NormalizedPrice]) -> list[ComparisonResult]:
    """Group prices by canonical product and build comparison results.

    Returns results in the same order as PRODUCTS config,
    skipping products with no prices found.
    """
    grouped: dict[str, list[NormalizedPrice]] = defaultdict(list)

    for price in prices:
        grouped[price.canonical_name].append(price)

    results: list[ComparisonResult] = []

    for product in PRODUCTS:
        if product.name in grouped:
            product_prices = sorted(grouped[product.name], key=lambda p: p.price)
            results.append(
                ComparisonResult(
                    canonical_name=product.name,
                    prices=product_prices,
                )
            )

    return results
