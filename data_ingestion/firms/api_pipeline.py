"""
HEATWATCH — FIRMS API Pipeline
================================
Orchestrates API-based FIRMS ingestion:
  1. Download from NASA FIRMS API
  2. Parse CSV using existing firms/reader.py
  3. Validate using existing firms/validator.py
  4. Normalize using existing firms/normalizer.py
  5. Filter for India coordinates
  6. Insert into hotspots table using existing firms/loader.py
  7. Write manifest

This module WRAPS the existing file-based pipeline (firms/pipeline.py).
It does NOT replace it.

Reuses all existing: reader, validator, normalizer, loader — unchanged.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.logging_config import get_logger
from common.provenance import IngestionResult
from common.timestamps import now_utc
from config import settings
from firms.client import FIRMSAuthError, FIRMSAPIError
from firms.config import FIRMS_RAW_ROOT, FIRMS_PROCESSED_ROOT, INDIA_BBOX
from firms.downloader import download_firms_csv
from firms.pipeline import run_firms_pipeline  # existing file-based pipeline

log = get_logger(__name__)


def _filter_india(csv_path: Path) -> Path:
    """
    Post-download filter: ensure coordinates are within India's bounding box.
    Overwrites the CSV in-place with India-only rows.
    Returns the (possibly modified) path.
    """
    import pandas as pd

    try:
        df = pd.read_csv(csv_path, dtype=str, encoding="utf-8")
    except Exception:
        return csv_path  # let the reader handle errors

    if df.empty:
        return csv_path

    # Normalize columns
    df.columns = [c.strip().lower() for c in df.columns]

    if "latitude" not in df.columns or "longitude" not in df.columns:
        return csv_path

    original_count = len(df)

    try:
        lat = pd.to_numeric(df["latitude"], errors="coerce")
        lon = pd.to_numeric(df["longitude"], errors="coerce")

        india_mask = (
            lat.between(INDIA_BBOX["min_lat"], INDIA_BBOX["max_lat"]) &
            lon.between(INDIA_BBOX["min_lon"], INDIA_BBOX["max_lon"])
        )
        df_india = df[india_mask]
    except Exception:
        return csv_path

    filtered_count = len(df_india)
    removed = original_count - filtered_count

    if removed > 0:
        df_india.to_csv(csv_path, index=False, encoding="utf-8")
        log.info(
            "firms.api_pipeline.india_filter",
            original=original_count,
            retained=filtered_count,
            removed=removed,
        )
        print(f"  India filter: {original_count} -> {filtered_count} records "
              f"({removed} outside India bbox removed)")

    return csv_path


def run_api_pipeline(
    base_url: str,
    api_key: str,
    source: str,
    country: str,
    days: int,
    raw_dir: Path | None = None,
    dry_run: bool = False,
    force_download: bool = False,
    batch_size: int | None = None,
) -> IngestionResult:
    """
    Full FIRMS API ingestion pipeline.

    Parameters
    ----------
    base_url        : FIRMS API base URL
    api_key         : NASA FIRMS map key
    source          : FIRMS product source (e.g. VIIRS_NOAA20_NRT)
    country         : ISO-3 country code (IND = India)
    days            : Days of data to request (1-10)
    raw_dir         : Local directory for raw CSV files
    dry_run         : If True, download + parse but do NOT insert into DB
    force_download  : If True, re-download even if today's file exists
    batch_size      : Records per DB transaction

    Returns IngestionResult with full metrics.
    """
    raw_dir = raw_dir or FIRMS_RAW_ROOT
    batch_size = batch_size or settings.FIRMS_BATCH_SIZE

    result = IngestionResult(
        dataset_name="NASA_FIRMS_API",
        source_reference=f"FIRMS/{source}/{country}/{days}d",
    )

    log.info("firms.api_pipeline.start",
             source=source, country=country, days=days, dry_run=dry_run)

    print()
    print("=" * 65)
    print("HEATWATCH — NASA FIRMS API INGESTION")
    print("=" * 65)
    print(f"  Source   : {source}")
    print(f"  Country  : {country}")
    print(f"  Days     : {days}")
    print(f"  Dry run  : {'yes (no DB insert)' if dry_run else 'no'}")
    print()

    # ── Step 1: Download from API ──────────────────────────────
    try:
        print("[1/4] Downloading from FIRMS API ...")
        csv_path = download_firms_csv(
            base_url=base_url,
            api_key=api_key,
            source=source,
            country=country,
            days=days,
            dest_dir=raw_dir,
            force=force_download,
        )
        result.metadata["csv_path"] = str(csv_path)

    except FIRMSAuthError as exc:
        msg = str(exc)
        log.error("firms.api_pipeline.auth_failed", error=msg)
        print(f"\n[FAIL] Authentication failed:\n  {msg}")
        result.add_error(msg)
        return result.finish(success=False)

    except FIRMSAPIError as exc:
        msg = str(exc)
        log.error("firms.api_pipeline.download_failed", error=msg)
        print(f"\n[FAIL] Download failed:\n  {msg}")
        result.add_error(msg)
        return result.finish(success=False)

    # ── Step 2: Apply India bounding-box filter ────────────────
    print("[2/4] Applying India coordinate filter ...")
    csv_path = _filter_india(csv_path)

    # ── Step 3: Dry-run exit point ─────────────────────────────
    if dry_run:
        print("\n[3/4] Dry-run mode: parsing + validating (no DB insert) ...")
        # Use the existing pipeline's reader + validator only
        from firms.reader import read_firms_csv
        from firms.validator import validate_firms_dataframe
        from firms.normalizer import normalize_firms_dataframe

        try:
            df = read_firms_csv(csv_path)
            result.records_read = len(df)
            valid_df, rejected_df = validate_firms_dataframe(df)
            result.records_valid = len(valid_df)
            result.records_rejected = len(rejected_df)
            records = normalize_firms_dataframe(valid_df, source_file=csv_path.name)

            print(f"\n  DRY RUN RESULTS:")
            print(f"    Read      : {result.records_read}")
            print(f"    Valid     : {result.records_valid}")
            print(f"    Rejected  : {result.records_rejected}")
            print(f"    Normalized: {len(records)}")
            print(f"    DB insert : SKIPPED (--dry-run)")
        except Exception as exc:
            result.add_error(str(exc))
            return result.finish(success=False)

        return result.finish(success=True)

    # ── Step 4: Run existing file-based pipeline ───────────────
    print("[3/4] Inserting into PostgreSQL ...")
    try:
        file_result = run_firms_pipeline(
            csv_path=csv_path,
            batch_size=batch_size,
            processed_dir=FIRMS_PROCESSED_ROOT,
        )
        result.records_read     = file_result.records_read
        result.records_valid    = file_result.records_valid
        result.records_rejected = file_result.records_rejected
        result.records_inserted = file_result.records_inserted
        result.records_skipped  = file_result.records_skipped
        result.validation_errors.extend(file_result.validation_errors)

    except Exception as exc:
        log.error("firms.api_pipeline.db_failed", error=str(exc), exc_info=True)
        result.add_error(str(exc))
        return result.finish(success=False)

    print("[4/4] Done.")
    result.finish(success=file_result.success)

    print()
    print("=" * 65)
    print("FIRMS INGESTION COMPLETE")
    print("=" * 65)
    print(f"  Read      : {result.records_read:,}")
    print(f"  Valid     : {result.records_valid:,}")
    print(f"  Rejected  : {result.records_rejected:,}")
    print(f"  Inserted  : {result.records_inserted:,}")
    print(f"  Skipped   : {result.records_skipped:,} (duplicates)")
    print("=" * 65)

    log.info("firms.api_pipeline.complete",
             read=result.records_read,
             valid=result.records_valid,
             inserted=result.records_inserted,
             skipped=result.records_skipped)

    return result
