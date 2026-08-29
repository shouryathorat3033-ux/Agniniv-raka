"""
HEATWATCH — OSM PBF Ingestion Pipeline (new PBF-based)
=========================================================
Replaces the old Overpass-based approach with direct PBF parsing
using osmium. See osm/parser.py for the streaming handler.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.logging_config import get_logger
from osm.config import (
    OSM_BATCH_SIZE,
    OSM_CHECKPOINT_PATH,
    OSM_MANIFEST_PATH,
    OSM_PROCESSED_ROOT,
)
from osm.database import ensure_schema, get_feature_counts, get_total_count, insert_batch
from osm.parser import parse_pbf_batches
from osm.pbf_validator import validate_pbf

log = get_logger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_checkpoint(pbf_path: Path, status: str, features_processed: int, counts: dict) -> None:
    OSM_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OSM_CHECKPOINT_PATH.write_text(json.dumps({
        "source":             pbf_path.name,
        "status":             status,
        "features_processed": features_processed,
        "counts":             counts,
        "last_update":        _now_utc(),
    }, indent=2), encoding="utf-8")


def _write_manifest(pbf_path: Path, db_total: int, db_counts: dict, elapsed: float) -> None:
    OSM_PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset":            "OpenStreetMap",
        "region":             "India",
        "source":             "Geofabrik",
        "format":             "osm.pbf",
        "pbf_file":           pbf_path.name,
        "pbf_size_bytes":     pbf_path.stat().st_size if pbf_path.exists() else 0,
        "status":             "success",
        "parser":             "osmium 4.x (Python 3.14 native wheel)",
        "features_processed": db_total,
        "feature_counts":     db_counts,
        "elapsed_seconds":    round(elapsed, 1),
        "generated_at":       _now_utc(),
    }
    OSM_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("osm.pbf_pipeline.manifest_written", path=str(OSM_MANIFEST_PATH))


def run_pbf_pipeline(
    pbf_path: Path,
    batch_size: int = OSM_BATCH_SIZE,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """
    Run the full OSM PBF ingestion pipeline.

    Steps:
      1. Validate PBF
      2. Ensure osm_features schema
      3. Stream-parse PBF, insert in batches (idempotent upserts)
      4. Write checkpoint + manifest

    Returns summary dict. Raises RuntimeError on fatal failure.
    """
    t_start = time.monotonic()
    log.info("osm.pbf_pipeline.start", pbf=str(pbf_path))

    print()
    print("=" * 70)
    print("HEATWATCH — OSM INDIA PBF INGESTION")
    print("=" * 70)
    print(f"  PBF    : {pbf_path}")
    print(f"  Batch  : {batch_size:,}")
    print()

    # Step 1: Validate
    if not skip_validation:
        print("[1/4] Validating PBF ...")
        report = validate_pbf(pbf_path)
        report.print_summary()
        if not report.valid:
            _write_checkpoint(pbf_path, "validation_failed", 0, {})
            raise RuntimeError(f"PBF validation failed: {report.errors}")
        print()

    # Step 2: Schema
    print("[2/4] Ensuring database schema ...")
    ensure_schema()
    print("  [OK] osm_features table and indexes ready")
    print()

    # Step 3: Parse + insert
    print("[3/4] Parsing PBF and inserting into database ...")
    _write_checkpoint(pbf_path, "running", 0, {})

    total_features  = 0
    total_inserted  = 0
    batch_num       = 0
    running_counts: dict[str, int] = {}
    last_log_time   = time.monotonic()

    try:
        for batch in parse_pbf_batches(pbf_path, batch_size):
            batch_num += 1
            inserted, _ = insert_batch(batch)
            total_inserted += inserted
            total_features += len(batch)

            for row in batch:
                ft = row["feature_type"]
                running_counts[ft] = running_counts.get(ft, 0) + 1

            now = time.monotonic()
            if now - last_log_time >= 30:
                last_log_time = now
                print(f"    Batch {batch_num:>4d} | parsed={total_features:>9,} | inserted={total_inserted:>9,}")
                _write_checkpoint(pbf_path, "running", total_features, running_counts)

    except Exception as exc:
        log.error("osm.pbf_pipeline.failed", error=str(exc), exc_info=True)
        _write_checkpoint(pbf_path, "failed", total_features, running_counts)
        raise

    # Step 4: Manifest
    db_counts = get_feature_counts()
    db_total  = get_total_count()
    _write_checkpoint(pbf_path, "complete", total_features, db_counts)

    print()
    print("[4/4] Writing manifest ...")
    elapsed = time.monotonic() - t_start
    _write_manifest(pbf_path, db_total, db_counts, elapsed)
    print(f"  [OK] {OSM_MANIFEST_PATH}")

    print()
    print("=" * 70)
    print("OSM INGESTION COMPLETE")
    print("=" * 70)
    print(f"  Elapsed         : {elapsed:.0f}s")
    print(f"  Features parsed : {total_features:,}")
    print(f"  Rows in DB      : {db_total:,}")
    print()
    for ft, cnt in sorted(db_counts.items()):
        print(f"    {ft:<20}: {cnt:>10,}")
    print("=" * 70)

    log.info("osm.pbf_pipeline.complete",
             elapsed_s=round(elapsed, 1), db_total=db_total, counts=db_counts)

    return {
        "status":          "success",
        "pbf":             str(pbf_path),
        "features_parsed": total_features,
        "db_total":        db_total,
        "counts":          db_counts,
        "elapsed_seconds": round(elapsed, 1),
    }
