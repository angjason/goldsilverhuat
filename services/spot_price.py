"""Spot price fetcher — gets current gold/silver spot prices in SGD.

Primary source: XE.com (XAU-SGD, XAG-SGD) — true interbank spot.
Fallback: Indigo Precious Metals homepage (has ~0.25% markup over spot).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from decimal import Decimal

import httpx

from config.constants import USER_AGENT

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}


@dataclass
class SpotPrices:
    gold_oz: Decimal | None = None
    silver_oz: Decimal | None = None
    source: str = ""


async def fetch_spot_prices() -> SpotPrices:
    """Fetch current spot prices in SGD. Tries XE first, falls back to Indigo."""
    spot = await _fetch_from_xe()
    if spot.gold_oz:
        return spot

    logger.info("XE unavailable, falling back to Indigo (includes ~0.25%% markup)")
    return await _fetch_from_indigo()


async def _fetch_from_xe() -> SpotPrices:
    """Fetch XAU-SGD and XAG-SGD from XE.com (mid-market rate)."""
    spot = SpotPrices()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            gold_req = client.get(
                "https://www.xe.com/currencyconverter/convert/?Amount=1&From=XAU&To=SGD",
                headers=_HEADERS,
            )
            silver_req = client.get(
                "https://www.xe.com/currencyconverter/convert/?Amount=1&From=XAG&To=SGD",
                headers=_HEADERS,
            )

            resp, resp2 = await asyncio.gather(gold_req, silver_req)

            resp.raise_for_status()
            gold_match = re.search(r"1\s*XAU\s*=\s*([\d,]+\.\d+)\s*SGD", resp.text)
            if gold_match:
                spot.gold_oz = Decimal(gold_match.group(1).replace(",", ""))

            resp2.raise_for_status()
            silver_match = re.search(r"1\s*XAG\s*=\s*([\d,]+\.\d+)\s*SGD", resp2.text)
            if silver_match:
                spot.silver_oz = Decimal(silver_match.group(1).replace(",", ""))

            spot.source = "XE.com (mid-market rate)"

    except Exception as e:
        logger.debug("XE fetch failed: %s", e)

    if spot.gold_oz:
        logger.info("Spot gold: SGD %s/oz (XE)", spot.gold_oz)
    if spot.silver_oz:
        logger.info("Spot silver: SGD %s/oz (XE)", spot.silver_oz)

    return spot


async def _fetch_from_indigo() -> SpotPrices:
    """Fetch spot from Indigo homepage (bid price, closest to true spot)."""
    spot = SpotPrices()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.indigopreciousmetals.com",
                headers=_HEADERS,
            )
            resp.raise_for_status()

            all_sgd = re.findall(r"SGD\s*([\d,]+\.\d{2})", resp.text)

            if len(all_sgd) >= 2:
                spot.gold_oz = Decimal(all_sgd[0].replace(",", ""))
            if len(all_sgd) >= 4:
                spot.silver_oz = Decimal(all_sgd[2].replace(",", ""))

            spot.source = "Indigo Precious Metals (bid)"

    except Exception as e:
        logger.error("Indigo spot fetch failed: %s", e)

    if spot.gold_oz:
        logger.info("Spot gold: SGD %s/oz (Indigo bid)", spot.gold_oz)
    if spot.silver_oz:
        logger.info("Spot silver: SGD %s/oz (Indigo bid)", spot.silver_oz)

    return spot
