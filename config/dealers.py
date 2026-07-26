"""Dealer registry — maps dealer names to their scraper classes.

To add a new dealer:
1. Create a new scraper in scrapers/
2. Add it to DEALER_SCRAPERS below.
"""

from dataclasses import dataclass


@dataclass
class DealerConfig:
    """Configuration for a single dealer."""

    name: str
    base_url: str
    scraper_module: str
    requires_js: bool = False
    enabled: bool = True


DEALERS: list[DealerConfig] = [
    DealerConfig(
        name="BullionStar",
        base_url="https://www.bullionstar.com",
        scraper_module="scrapers.bullionstar",
        requires_js=True,
    ),
    DealerConfig(
        name="GoldSilver Central",
        base_url="https://www.goldsilvercentral.com.sg",
        scraper_module="scrapers.goldsilvercentral",
    ),
    DealerConfig(
        name="Silver Bullion",
        base_url="https://www.silverbullion.com.sg",
        scraper_module="scrapers.silverbullion",
    ),
    DealerConfig(
        name="UOB",
        base_url="https://www.uobgroup.com",
        scraper_module="scrapers.uob",
        requires_js=True,
    ),
    DealerConfig(
        name="LPM",
        base_url="https://www.lpm.sg",
        scraper_module="scrapers.lpm",
        requires_js=True,
    ),
    DealerConfig(
        name="Indigo Precious Metals",
        base_url="https://www.indigopreciousmetals.com",
        scraper_module="scrapers.indigo",
    ),
    DealerConfig(
        name="BullionKing",
        base_url="https://www.bullionking.sg",
        scraper_module="scrapers.bullionking",
        requires_js=True,
        enabled=False,  # Requires Playwright — enable after: playwright install chromium
    ),
]


def get_enabled_dealers() -> list[DealerConfig]:
    return [d for d in DEALERS if d.enabled]
