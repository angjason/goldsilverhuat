"""Product normalization — matches scraped products to canonical product definitions."""

from __future__ import annotations

import logging

from config.products import PRODUCTS, CanonicalProduct
from models.product import NormalizedPrice, ScrapedProduct

logger = logging.getLogger(__name__)


def normalize(
    scraped: list[ScrapedProduct],
    products: list[CanonicalProduct] | None = None,
) -> list[NormalizedPrice]:
    """Match scraped products against canonical product definitions.

    A scraped product can match multiple canonical products (e.g. both
    '1oz PAMP Gold Bar' and '1oz Gold Bar (any brand)'). Returns one
    NormalizedPrice per (canonical_name, dealer) pair, keeping the
    cheapest in-stock option per dealer.
    """
    if products is None:
        products = PRODUCTS

    best: dict[tuple[str, str], NormalizedPrice] = {}

    for item in scraped:
        matched_any = False
        for canonical in products:
            if canonical.matches(item.name) and item.price >= canonical.min_price:
                matched_any = True
                key = (canonical.name, item.dealer)
                candidate = NormalizedPrice(
                    canonical_name=canonical.name,
                    dealer=item.dealer,
                    price=item.price,
                    currency=item.currency,
                    url=item.url,
                    in_stock=item.in_stock,
                )

                existing = best.get(key)
                if existing is None:
                    best[key] = candidate
                elif candidate.in_stock and (not existing.in_stock or candidate.price < existing.price):
                    best[key] = candidate
                elif not existing.in_stock and candidate.price < existing.price:
                    best[key] = candidate

        if not matched_any:
            logger.debug("No match for '%s' (%s)", item.name, item.dealer)

    return list(best.values())
