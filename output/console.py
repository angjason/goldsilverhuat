"""Console output — formatted price comparison tables with premium spreads."""

from __future__ import annotations

from decimal import Decimal

from models.product import ComparisonResult
from services.spot_helper import get_spot_for_product
from services.spot_price import SpotPrices


def print_results(results: list[ComparisonResult], spot: SpotPrices | None = None) -> None:
    """Print formatted comparison results to the terminal."""
    if not results:
        print("No results to display.")
        return

    if spot:
        _print_spot(spot)

    for result in results:
        _print_product(result, spot)


def _print_spot(spot: SpotPrices) -> None:
    separator = "=" * 56
    print(f"\n{separator}")
    print("SPOT PRICES (per troy oz)\n")
    if spot.gold_oz:
        print(f"  Gold:    SGD {spot.gold_oz:>10,.2f}")
    if spot.silver_oz:
        print(f"  Silver:  SGD {spot.silver_oz:>10,.2f}")
    if spot.source:
        print(f"\n  Source: {spot.source}")
    print(separator)


def _print_product(result: ComparisonResult, spot: SpotPrices | None) -> None:
    separator = "=" * 56
    print(f"\n{separator}")
    print(f"{result.canonical_name}\n")

    spot_price = get_spot_for_product(result.canonical_name, spot)

    in_stock = [p for p in result.prices if p.in_stock]
    out_of_stock = [p for p in result.prices if not p.in_stock]

    if not in_stock:
        print("  No dealers have this product in stock.\n")
        if out_of_stock:
            for p in out_of_stock:
                print(f"  {p.dealer:<28} {p.currency} {p.price:>10,.2f}  [OUT OF STOCK]")
            print()
        print(separator)
        return

    for p in in_stock:
        premium_str = ""
        if spot_price and spot_price > 0:
            premium_pct = ((p.price - spot_price) / spot_price) * 100
            premium_str = f"  ({premium_pct:>+.1f}%)"
        print(f"  {p.dealer:<28} {p.currency} {p.price:>10,.2f}{premium_str}")

    if out_of_stock:
        print()
        for p in out_of_stock:
            print(f"  {p.dealer:<28} {p.currency} {p.price:>10,.2f}  [OUT OF STOCK]")

    cheapest = result.cheapest
    if cheapest and len(in_stock) > 1:
        print(f"\n  Cheapest: {cheapest.dealer}")
        print(f"  {cheapest.currency} {cheapest.price:,.2f}")

        if spot_price and spot_price > 0:
            premium = cheapest.price - spot_price
            premium_pct = (premium / spot_price) * 100
            print(f"  Premium over spot: {cheapest.currency} {premium:,.2f} ({premium_pct:.1f}%)")

        most_expensive = in_stock[-1]
        diff = most_expensive.price - cheapest.price
        print(f"\n  Savings: {cheapest.currency} {diff:,.2f} vs most expensive ({most_expensive.dealer})")

    print(f"{separator}")


