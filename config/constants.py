"""Shared constants used across scrapers and services."""

from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

TIMEZONE = "Asia/Singapore"

CHROME_PATH = (
    Path.home()
    / "Library/Caches/ms-playwright/chromium-1228"
    / "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
)
