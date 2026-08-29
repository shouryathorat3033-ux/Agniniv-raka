"""
HEATWATCH — FIRMS API Downloader
===================================
Downloads FIRMS CSV data from the NASA API and saves it locally.

File naming convention:
  dataset/raw/firms/{YYYY-MM-DD}/firms_{source}_{country}_{YYYY-MM-DD}_d{days}.csv

If the file already exists (same source/country/days for today), it is reused
to avoid redundant API calls. Use --force-download to override.

API date semantics:
  The FIRMS API returns data for the last N *days* relative to today (UTC).
  There is no arbitrary start/end date parameter on the country endpoint.
  For historical data, use the area API or the FIRMS archived CSV products.

  Maximum: 10 days per request (API hard limit).
  For > 10 days, we chunk into multiple requests.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from common.logging_config import get_logger
from firms.client import (
    FIRMSAuthError,
    FIRMSAPIError,
    fetch_firms_csv,
    make_area_csv_url,
)
from firms.config import INDIA_BBOX

log = get_logger(__name__)

# FIRMS API maximum days per request
FIRMS_MAX_DAYS_PER_REQUEST = 10


def _today_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _build_filename(source: str, country: str, days: int, date_str: str) -> str:
    return f"firms_{source}_{country}_{date_str}_d{days}.csv"


def download_firms_csv(
    base_url: str,
    api_key: str,
    source: str,
    country: str,
    days: int,
    dest_dir: Path,
    force: bool = False,
) -> Path:
    """
    Download a FIRMS country CSV and save it locally.

    Parameters
    ----------
    base_url   : FIRMS API base URL
    api_key    : NASA FIRMS map key (never logged)
    source     : FIRMS product (e.g. VIIRS_NOAA20_NRT)
    country    : ISO 3166-1 alpha-3 (e.g. IND)
    days       : Number of days (1-10)
    dest_dir   : Directory to save the CSV
    force      : If True, re-download even if file exists

    Returns the path to the saved CSV file.
    """
    days = max(1, min(days, FIRMS_MAX_DAYS_PER_REQUEST))
    today = _today_utc_str()
    filename = _build_filename(source, country, days, today)
    date_dir = dest_dir / today
    date_dir.mkdir(parents=True, exist_ok=True)
    dest_path = date_dir / filename

    # Reuse if already downloaded today (and not forced)
    if dest_path.exists() and dest_path.stat().st_size > 0 and not force:
        log.info(
            "firms.download.skipped",
            path=str(dest_path),
            reason="already downloaded today",
        )
        print(f"  [OK] FIRMS CSV already exists ({dest_path.stat().st_size/1024:.1f} KB): {dest_path.name}")
        return dest_path

    url = make_area_csv_url(
        base_url=base_url,
        api_key=api_key,
        source=source,
        bbox=INDIA_BBOX,
        days=days,
    )
    log.info("firms.download.start", source=source, country=country, days=days)
    print(f"  Requesting FIRMS data: source={source}, country={country}, days={days}")

    csv_text = fetch_firms_csv(url)

    # Validate we got CSV (not empty, has header)
    if not csv_text or not csv_text.strip():
        log.warning("firms.download.empty_response")
        raise FIRMSAPIError(
            "FIRMS API returned an empty response.\n"
            f"  source={source}, country={country}, days={days}\n"
            "  This may mean no fire activity in that region/period."
        )

    lines = csv_text.strip().splitlines()
    if len(lines) < 1:
        raise FIRMSAPIError("FIRMS response has no content")

    # Write raw CSV
    dest_path.write_text(csv_text, encoding="utf-8")
    size_kb = dest_path.stat().st_size / 1024

    row_count = len(lines) - 1  # subtract header
    log.info(
        "firms.download.complete",
        path=str(dest_path),
        rows=row_count,
        size_kb=round(size_kb, 1),
    )
    print(f"  [OK] Downloaded: {dest_path.name} ({row_count} records, {size_kb:.1f} KB)")
    return dest_path


def download_firms_chunked(
    base_url: str,
    api_key: str,
    source: str,
    country: str,
    total_days: int,
    dest_dir: Path,
    force: bool = False,
) -> list[Path]:
    """
    Download FIRMS data for more than 10 days by chunking into multiple requests.

    Returns list of downloaded CSV paths (one per chunk).
    """
    paths: list[Path] = []
    remaining = total_days

    while remaining > 0:
        chunk_days = min(remaining, FIRMS_MAX_DAYS_PER_REQUEST)
        path = download_firms_csv(
            base_url=base_url,
            api_key=api_key,
            source=source,
            country=country,
            days=chunk_days,
            dest_dir=dest_dir,
            force=force,
        )
        paths.append(path)
        remaining -= chunk_days

    return paths
