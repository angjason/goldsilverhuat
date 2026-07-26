"""CSV export — saves comparison results with timestamps for price history."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from models.product import ComparisonResult

OUTPUT_DIR = Path(__file__).parent.parent / "data"


def export(results: list[ComparisonResult], output_dir: Path | None = None) -> Path:
    """Export comparison results to a timestamped CSV file.

    Returns the path to the created file.
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()
    filename = f"prices_{timestamp:%Y%m%d_%H%M%S}.csv"
    filepath = output_dir / filename

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "product",
            "dealer",
            "price",
            "currency",
            "in_stock",
            "url",
        ])

        for result in results:
            for price in result.prices:
                writer.writerow([
                    timestamp.isoformat(),
                    result.canonical_name,
                    price.dealer,
                    f"{price.price:.2f}",
                    price.currency,
                    price.in_stock,
                    price.url,
                ])

    return filepath
