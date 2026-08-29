#!/usr/bin/env python3
"""
HEATWATCH — NASA FIRMS Ingestion CLI
=======================================
Downloads and ingests NASA FIRMS active fire / thermal anomaly data
for India into the HEATWATCH PostgreSQL database.

Usage examples:

    # Ingest last 1 day (default):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py

    # Ingest last 7 days:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py --days 7

    # Dry run (download + parse, no DB insert):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py --dry-run

    # Use a specific source product:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py \\
        --source VIIRS_SNPP_NRT --days 3

    # Ingest from an existing local CSV (skip download):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py \\
        --path "dataset\\raw\\firms\\2026-08-29\\firms_VIIRS_NOAA20_NRT_IND_2026-08-29_d1.csv"

    # Force re-download even if today's file exists:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py --force-download

    # Help:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_firms.py --help

Requirements:
    NASA_FIRMS_API_KEY (or FIRMS_MAP_KEY) must be set in C:\\SIH_Hackthon\\.env
    Get a free key at: https://firms.modaps.eosdis.nasa.gov/api/
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_DI_ROOT      = _SCRIPT_DIR.parent
_PROJECT_ROOT = _DI_ROOT.parent

sys.path.insert(0, str(_DI_ROOT))

from dotenv import load_dotenv
# override=True: project-root .env is always authoritative
load_dotenv(_PROJECT_ROOT / ".env", override=True)
load_dotenv(_DI_ROOT / ".env", override=False)

import click
from common.logging_config import configure_logging
from config import settings


@click.command()
@click.option(
    "--days",
    default=None,
    type=click.IntRange(1, 10),
    help="Days of data to request (1-10, default: FIRMS_DAYS from .env or 1).",
)
@click.option(
    "--source",
    default=None,
    type=str,
    help="FIRMS product source (default: FIRMS_SOURCE from .env or VIIRS_NOAA20_NRT).",
)
@click.option(
    "--country",
    default=None,
    type=str,
    help="ISO-3 country code (default: IND = India).",
)
@click.option(
    "--path",
    "csv_path_str",
    default=None,
    type=str,
    help="Path to an existing FIRMS CSV file. Skips API download.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Download + parse but do NOT insert into the database.",
)
@click.option(
    "--force-download",
    is_flag=True,
    default=False,
    help="Re-download even if today's CSV already exists.",
)
@click.option(
    "--batch-size",
    default=None,
    type=int,
    help="Records per database transaction (default: FIRMS_BATCH_SIZE from .env).",
)
def main(
    days: int | None,
    source: str | None,
    country: str | None,
    csv_path_str: str | None,
    dry_run: bool,
    force_download: bool,
    batch_size: int | None,
) -> None:
    """Run HEATWATCH NASA FIRMS India ingestion."""
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)

    from firms.config import (
        FIRMS_MAP_KEY,
        FIRMS_BASE_URL,
        FIRMS_SOURCE,
        FIRMS_COUNTRY,
        FIRMS_DAYS,
        FIRMS_RAW_ROOT,
        SUPPORTED_SOURCES,
    )

    # ── Resolve effective values ───────────────────────────────
    effective_source  = source  or FIRMS_SOURCE
    effective_country = country or FIRMS_COUNTRY
    effective_days    = days    or FIRMS_DAYS
    effective_batch   = batch_size or settings.FIRMS_BATCH_SIZE

    # ── Source from local CSV (no API needed) ──────────────────
    if csv_path_str:
        csv_path = Path(csv_path_str)
        if not csv_path.exists():
            click.echo(f"\n[FAIL] CSV not found: {csv_path}", err=True)
            raise click.exceptions.Exit(1)

        from firms.pipeline import run_firms_pipeline
        from firms.config import FIRMS_PROCESSED_ROOT

        print(f"\nIngesting local CSV: {csv_path}")
        result = run_firms_pipeline(
            csv_path=csv_path,
            batch_size=effective_batch,
            processed_dir=FIRMS_PROCESSED_ROOT,
        )
        click.echo(result.summary_line())
        raise click.exceptions.Exit(0 if result.success else 1)

    # ── API-based ingestion ────────────────────────────────────
    if not FIRMS_MAP_KEY:
        click.echo(
            "\n[FAIL] FIRMS API key not configured.\n"
            "  Set NASA_FIRMS_API_KEY or FIRMS_MAP_KEY in C:\\SIH_Hackthon\\.env\n"
            "  Get a free key at: https://firms.modaps.eosdis.nasa.gov/api/",
            err=True,
        )
        raise click.exceptions.Exit(1)

    if effective_source not in SUPPORTED_SOURCES:
        click.echo(
            f"\n[WARN] Source '{effective_source}' is not in the known list: "
            f"{sorted(SUPPORTED_SOURCES)}\n  Proceeding anyway.",
        )

    from firms.api_pipeline import run_api_pipeline

    result = run_api_pipeline(
        base_url       = FIRMS_BASE_URL,
        api_key        = FIRMS_MAP_KEY,
        source         = effective_source,
        country        = effective_country,
        days           = effective_days,
        raw_dir        = FIRMS_RAW_ROOT,
        dry_run        = dry_run,
        force_download = force_download,
        batch_size     = effective_batch,
    )

    click.echo(result.summary_line())
    raise click.exceptions.Exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
