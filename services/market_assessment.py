"""Market assessment generator using Google Gemini (free tier)."""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from services.spot_history import SpotDataPoint
from services.spot_price import SpotPrices

logger = logging.getLogger(__name__)


def generate_assessment(
    spot: SpotPrices | None,
    history: list[SpotDataPoint] | None,
    avg_premiums: dict[str, float] | None = None,
) -> str | None:
    """Generate a market assessment using Google Gemini.

    Returns None if the API key is missing or the call fails.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not set — skipping market assessment")
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        prompt = _build_prompt(spot, history, avg_premiums)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        return response.text.strip() if response.text else None

    except Exception as e:
        logger.warning("Market assessment failed: %s", e)
        return None


def _build_prompt(
    spot: SpotPrices | None,
    history: list[SpotDataPoint] | None,
    avg_premiums: dict[str, float] | None,
) -> str:
    parts = []
    parts.append(
        "You are a precious metals market analyst focused on the Singapore bullion market. "
        "Give a brief daily market assessment (4-6 sentences) covering: "
        "current price direction, key factors driving prices today, "
        "and a practical suggestion for Singapore retail bullion buyers (buy/wait/dollar-cost-average). "
        "Be specific with numbers. Do not use markdown formatting."
    )

    if spot:
        parts.append(f"\nCurrent spot prices (SGD per troy oz):")
        if spot.gold_oz:
            parts.append(f"  Gold: SGD {spot.gold_oz:,.2f}")
        if spot.silver_oz:
            parts.append(f"  Silver: SGD {spot.silver_oz:,.2f}")

    if history and len(history) >= 2:
        parts.append(f"\n12-month price history (SGD/oz):")
        for point in history:
            gold_str = f"Gold: {point.gold_sgd:,.2f}" if point.gold_sgd else "Gold: N/A"
            silver_str = f"Silver: {point.silver_sgd:,.2f}" if point.silver_sgd else "Silver: N/A"
            parts.append(f"  {point.date}: {gold_str}, {silver_str}")

    if avg_premiums:
        parts.append(f"\nAverage dealer premiums over spot:")
        for product, pct in avg_premiums.items():
            parts.append(f"  {product}: {pct:.1f}%")

    return "\n".join(parts)
