"""
HEATWATCH — FIRMS Pipeline Orchestrator
=========================================
Orchestrates the full FIRMS ETL flow:
  READ → VALIDATE → NORMALIZE → TRANSFORM → LOAD → RECORD

Does NOT perform ST-DBSCAN clustering.
Does NOT create thermal_objects.
Does NOT run ML classification.
"""
from __future__ import annotations

from pathlib import Path

from common.logging_config import get_logger
from common.provenance import IngestionResult
from config import settings
from firms.loader import load_hotspots_batch
from firms.normalizer import normalize_firms_dataframe
from firms.reader import read_firms_csv, list_firms_files
from firms.transformer import filter_invalid_sources
from firms.validator import validate_firms_dataframe

log = get_logger(__name__)


def run_firms_pipeline(
    csv_path: Path,
    batch_size: int | None = None,
    rejected_dir: Path | None = None,
    processed_dir: Path | None = None,
) -> IngestionResult:
    """
    Run the complete FIRMS ingestion pipeline for a single CSV file.

    Parameters
    ----------
    csv_path      : Path to the FIRMS CSV file.
    batch_size    : Records per DB transaction (default from settings).
    rejected_dir  : Directory to write rejected records (default from settings).
    processed_dir : Directory for processed output manifests.

    Returns
    -------
    IngestionResult with full metrics.
    """
    batch_size    = batch_size    or settings.FIRMS_BATCH_SIZE
    rejected_dir  = rejected_dir  or (settings.REJECTED_DATA_ROOT / "firms")
    processed_dir = processed_dir or (settings.PROCESSED_DATA_ROOT / "firms")

    result = IngestionResult(
        dataset_name="NASA_FIRMS",
        source_reference=str(csv_path),
    )

    log.info("firms.pipeline.start", path=str(csv_path))

    try:
        # ── 1. READ ───────────────────────────────────────────
        df = read_firms_csv(csv_path)
        result.records_read = len(df)

        if df.empty:
            log.warning("firms.pipeline.empty_file", path=str(csv_path))
            return result.finish(success=True)

        # ── 2. VALIDATE ───────────────────────────────────────
        valid_df, rejected_df = validate_firms_dataframe(df)
        result.records_valid    = len(valid_df)
        result.records_rejected = len(rejected_df)

        # Write rejected rows
        if not rejected_df.empty:
            rejected_dir.mkdir(parents=True, exist_ok=True)
            rejected_path = rejected_dir / f"{csv_path.stem}_rejected.csv"
            rejected_df.to_csv(rejected_path, index=False)
            log.warning("firms.pipeline.rejected_written", path=str(rejected_path))

        if valid_df.empty:
            log.warning("firms.pipeline.no_valid_rows")
            return result.finish(success=True)

        # ── 3. NORMALIZE ──────────────────────────────────────
        records = normalize_firms_dataframe(valid_df, source_file=csv_path.name)

        # ── 4. TRANSFORM (source filter) ──────────────────────
        records, n_source_rejected = filter_invalid_sources(
            records,
            rejected_dir=rejected_dir,
            source_file_name=csv_path.stem,
        )
        result.records_rejected += n_source_rejected

        # ── 5. LOAD ───────────────────────────────────────────
        inserted, skipped = load_hotspots_batch(records, batch_size=batch_size)
        result.records_inserted = inserted
        result.records_skipped  = skipped

        # ── 6. WRITE RESULT MANIFEST ─────────────────────────
        result.finish(success=True)
        result.write_manifest(processed_dir)
        log.info("firms.pipeline.done", **result.to_dict())

    except Exception as exc:
        log.error("firms.pipeline.failed", error=str(exc), exc_info=True)
        result.add_error(str(exc))
        result.finish(success=False)
        raise

    return result
