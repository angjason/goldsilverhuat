"""Shared utilities for scraper implementations."""

from __future__ import annotations

import re
from decimal import Decimal


def parse_sgd_price(text: str, min_value: Decimal = Decimal("10")) -> Decimal | None:
    """Parse an SGD price from text like 'S$5,530.21', 'SGD 5,240.38', or bare '5,530.21'."""
    patterns = [
        r"S\$\s*([\d,]+\.\d{2})",
        r"SGD\s*([\d,]+\.\d{2})",
        r"([\d,]+\.\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                price = Decimal(match.group(1).replace(",", ""))
                if price >= min_value:
                    return price
            except Exception:
                continue
    return None


def resolve_url(href: str, base_url: str) -> str:
    """Resolve a relative URL against a base URL."""
    if href.startswith("http"):
        return href
    return f"{base_url}{href}"
