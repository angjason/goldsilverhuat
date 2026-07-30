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
    scraper_module: str
    enabled: bool = True


DEALERS: list[DealerConfig] = [
    DealerConfig(name="BullionStar", scraper_module="scrapers.bullionstar"),
    DealerConfig(name="GoldSilver Central", scraper_module="scrapers.goldsilvercentral"),
    DealerConfig(name="Silver Bullion", scraper_module="scrapers.silverbullion"),
    DealerConfig(name="UOB", scraper_module="scrapers.uob"),
    DealerConfig(name="LPM", scraper_module="scrapers.lpm"),
    DealerConfig(name="Indigo Precious Metals", scraper_module="scrapers.indigo"),
    DealerConfig(name="BullionKing", scraper_module="scrapers.bullionking"),
]


def get_enabled_dealers() -> list[DealerConfig]:
    return [d for d in DEALERS if d.enabled]
