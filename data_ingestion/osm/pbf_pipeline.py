"""
HEATWATCH - OSM PBF Ingestion Pipeline
========================================
Key improvements over previous version:
  - Uses parse_pbf_streaming() so DB insertion starts immediately (no waiting
    for the entire 1.7 GB file to be read before the first batch is yielded).
  - Checkpoint is updated after EVERY batch (not every 30 s) so progress is
    always visible.
  - Supports --sample mode (node-only, fast, no location index) for quick
    end-to-end tests before committing to a multi-hour full run.
  - Progress is printed after every batch with elapsed time + cumulative counts.
"""
from __future__ import annotations

import json
import sys
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
from osm.parser import parse_pbf_dry_run, parse_pbf_sample, parse_pbf_streaming
from osm.pbf_validator import validate_pbf

log = get_logger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_checkpoint(
    pbf_path: Path,
    status: str,
    features_processed: int,
    counts: dict,
    error: str | None = None,
) -> None:
    OSM_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "source":             pbf_path.name,
        "status":             status,
        "features_processed": features_processed,
        "counts":             counts,
        "last_update":        _now_utc(),
    }
    if error:
        data["error"] = error
    OSM_CHECKPOINT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_manifest(
    pbf_path: Path,
    db_total: int,
    db_counts: dict,
    elapsed: float,
    mode: str = "full",
) -> None:
    OSM_PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset":           "OpenStreetMap",
        "region":            "India",
        "source":            "Geofabrik",
        "source_url":        "https://download.geofabrik.de/asia/india-latest.osm.pbf",
        "country":           "India",
        "input_file":        pbf_path.name,
        "file_size_bytes":   pbf_path.stat().st_size if pbf_path.exists() else 0,
        "status":            "success",
        "mode":              mode,
        "parser":            "osmium (pyosmium) - streaming",
        "features_inserted": db_total,
        "feature_counts":    db_counts,
        "elapsed_seconds":   round(elapsed, 1),
        "generated_at":      _now_utc(),
    }
    OSM_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("osm.pipeline.manifest_written", path=str(OSM_MANIFEST_PATH))


def run_pbf_pipeline(
    pbf_path: Path,
    batch_size: int = OSM_BATCH_SIZE,
    skip_validation: bool = False,
    dry_run: bool = False,
    sample: bool = False,
    sample_limit: int = 50_000,
    with_way_geometry: bool = True,
) -> dict[str, Any]:
    """
    Run the full OSM PBF ingestion pipeline.

    Modes
    -----
    dry_run  : parse + geometry, NO DB writes, NO manifest/checkpoint update
    sample   : fast node-only parse (no location index), inserts sample_limit
               features into DB to prove the pipeline works end-to-end
    (normal) : full streaming parse + DB insertion + checkpoint + manifest

    Returns a summary dict.  Raises RuntimeError on fatal error.
    """
    t_start = time.monotonic()
    mode = "dry_run" if dry_run else ("sample" if sample else "full")
    log.info("osm.pipeline.start", pbf=str(pbf_path), mode=mode)

    print()
    print("=" * 72)
    print(f"HEATWATCH -- OSM INDIA PBF INGESTION  [{mode.upper()}]")
    print("=" * 72)
    print(f"  PBF   : {pbf_path}")
    print(f"  Batch : {batch_size:,}")
    print(f"  Mode  : {mode}")
    if sample:
        print(f"  Limit : first {sample_limit:,} features  (node-only, no location index)")
    print()
    sys.stdout.flush()

    # ------------------------------------------------------------------
    # Step 1: Validate PBF
    # ------------------------------------------------------------------
    if not skip_validation:
        print("[1/4] Validating PBF ...")
        report = validate_pbf(pbf_path)
        report.print_summary()
        if not report.valid:
            if not dry_run:
                _write_checkpoint(pbf_path, "validation_failed", 0, {},
                                  error=str(report.errors))
            raise RuntimeError(f"PBF validation failed: {report.errors}")
        print()
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Dry-run path: parse only
    # ------------------------------------------------------------------
    if dry_run:
        print("[DRY RUN] Parsing PBF (no DB writes) ...")
        result = parse_pbf_dry_run(
            pbf_path,
            batch_size=batch_size,
            with_way_geometry=with_way_geometry,
        )
        elapsed = time.monotonic() - t_start
        print()
        print("=" * 72)
        print("DRY RUN COMPLETE")
        print("=" * 72)
        print(f"  Elapsed   : {elapsed:.0f}s")
        print(f"  Features  : {result['features']:,}")
        print(f"  Geom ok   : {result['geom_ok']:,}")
        print(f"  Geom null : {result['geom_null']:,}")
        print()
        for ft, cnt in sorted(result["counts"].items()):
            print(f"    {ft:<20}: {cnt:>10,}")
        print("[DRY RUN] No data written.")
        sys.stdout.flush()
        return {"status": "dry_run", "elapsed_s": round(elapsed, 1), **result}

    # ------------------------------------------------------------------
    # Step 2: Ensure schema
    # ------------------------------------------------------------------
    print("[2/4] Ensuring database schema ...")
    ensure_schema()
    print("  [OK] osm_features table and indexes ready")
    print()
    sys.stdout.flush()

    # ------------------------------------------------------------------
    # Step 3: Parse + insert in batches
    # ------------------------------------------------------------------
    print("[3/4] Streaming PBF -> database ...")
    _write_checkpoint(pbf_path, "running", 0, {})

    total_features = 0
    total_inserted = 0
    batch_num      = 0
    running_counts: dict[str, int] = {}

    try:
        # Choose parser function based on mode
        if sample:
            batch_iter = parse_pbf_sample(
                pbf_path, batch_size=batch_size, max_features=sample_limit
            )
        else:
            batch_iter = parse_pbf_streaming(
                pbf_path,
                batch_size=batch_size,
                with_way_geometry=with_way_geometry,
            )

        for batch in batch_iter:
            batch_num      += 1
            inserted, _     = insert_batch(batch)
            total_inserted += inserted
            total_features += len(batch)

            for row in batch:
                ft = row["feature_type"]
                running_counts[ft] = running_counts.get(ft, 0) + 1

            elapsed_so_far = time.monotonic() - t_start
            print(
                f"  Batch {batch_num:>4d} | "
                f"parsed={total_features:>9,} | "
                f"inserted={total_inserted:>9,} | "
                f"elapsed={elapsed_so_far:5.0f}s"
            )
            sys.stdout.flush()

            # Update checkpoint after EVERY batch
            _write_checkpoint(pbf_path, "running", total_features, running_counts)

    except Exception as exc:
        log.error("osm.pipeline.failed", error=str(exc), exc_info=True)
        _write_checkpoint(pbf_path, "failed", total_features, running_counts,
                          error=str(exc))
        raise

    # ------------------------------------------------------------------
    # Step 4: Finalize
    # ------------------------------------------------------------------
    db_counts = get_feature_counts()
    db_total  = get_total_count()
    _write_checkpoint(pbf_path, "complete", total_features, db_counts)

    print()
    print("[4/4] Writing manifest ...")
    elapsed = time.monotonic() - t_start
    _write_manifest(pbf_path, db_total, db_counts, elapsed, mode=mode)
    print(f"  [OK] {OSM_MANIFEST_PATH}")

    print()
    print("=" * 72)
    print("OSM INGESTION COMPLETE")
    print("=" * 72)
    print(f"  Mode            : {mode}")
    print(f"  Elapsed         : {elapsed:.0f}s")
    print(f"  Features parsed : {total_features:,}")
    print(f"  Rows in DB      : {db_total:,}")
    print()
    for ft, cnt in sorted(db_counts.items()):
        print(f"    {ft:<20}: {cnt:>10,}")
    print("=" * 72)
    sys.stdout.flush()

    log.info("osm.pipeline.complete",
             elapsed_s=round(elapsed, 1), db_total=db_total, counts=db_counts)

    return {
        "status":          "success",
        "mode":            mode,
        "pbf":             str(pbf_path),
        "features_parsed": total_features,
        "db_total":        db_total,
        "counts":          db_counts,
        "elapsed_seconds": round(elapsed, 1),
    }