"""Historical spot price fetcher — gets 12 months of gold/silver prices in SGD."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup

from config.constants import USER_AGENT

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": USER_AGENT}


@dataclass
class SpotDataPoint:
    date: str
    gold_sgd: Decimal | None = None
    silver_sgd: Decimal | None = None


async def fetch_spot_history(months: int = 12) -> list[SpotDataPoint]:
    """Fetch monthly gold and silver spot prices in SGD from XE.com."""
    today = date.today()
    dates = []
    for i in range(months, -1, -1):
        d = today - timedelta(days=i * 30)
        dates.append(d)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        sem = asyncio.Semaphore(3)

        async def limited_fetch(d):
            async with sem:
                await asyncio.sleep(0.5)
                return await _fetch_date(client, d)

        tasks = [limited_fetch(d) for d in dates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    data_points = []
    for result in results:
        if isinstance(result, SpotDataPoint):
            data_points.append(result)

    logger.info("Fetched %d/%d historical spot prices", len(data_points), len(dates))
    return data_points


async def _fetch_date(client: httpx.AsyncClient, d: date) -> SpotDataPoint:
    """Fetch gold and silver SGD prices for a specific date from XE."""
    point = SpotDataPoint(date=d.isoformat())

    try:
        gold_resp = await client.get(
            f"https://www.xe.com/currencytables/?from=XAU&date={d.isoformat()}",
            headers=_HEADERS,
        )
        gold_resp.raise_for_status()
        point.gold_sgd = _extract_sgd_rate(gold_resp.text)
    except Exception as e:
        logger.debug("Failed to fetch gold for %s: %s", d, e)

    try:
        silver_resp = await client.get(
            f"https://www.xe.com/currencytables/?from=XAG&date={d.isoformat()}",
            headers=_HEADERS,
        )
        silver_resp.raise_for_status()
        point.silver_sgd = _extract_sgd_rate(silver_resp.text)
    except Exception as e:
        logger.debug("Failed to fetch silver for %s: %s", d, e)

    return point


def _extract_sgd_rate(html: str) -> Decimal | None:
    """Extract the SGD exchange rate from an XE currency table page."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table tr")

    for row in rows:
        cells = row.select("td")
        if len(cells) >= 2 and "SGD" in row.get_text():
            text = cells[1].get_text(strip=True)
            match = re.match(r"([\d.]+)", text)
            if match:
                try:
                    return Decimal(match.group(1))
                except Exception:
                    pass

    return None
