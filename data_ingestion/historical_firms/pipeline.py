"""
HEATWATCH — Historical FIRMS Pipeline
======================================
Processes historical FIRMS archives by:
  - Iterating over multiple CSV files in the historical directory
  - Reading each file in chunks (to handle multi-GB files)
  - Reusing FIRMS validate / normalize / transform / load logic
  - Loading into the same hotspots table as current FIRMS

Historical profiles are NOT computed here.
Thermal object clustering is NOT performed here.
"""
from __future__ import annotations

from pathlib import Path

from common.logging_config import get_logger
from common.provenance import IngestionResult
from config import settings
from firms.loader import load_hotspots_batch
from firms.normalizer import normalize_firms_dataframe
from firms.transformer import filter_invalid_sources
from firms.validator import validate_firms_dataframe
from historical_firms.reader import list_historical_files, read_historical_firms_chunks

log = get_logger(__name__)


def run_historical_firms_pipeline(
    source_dir: Path | None = None,
    chunk_size: int | None = None,
    batch_size: int | None = None,
    rejected_dir: Path | None = None,
    processed_dir: Path | None = None,
) -> list[IngestionResult]:
    """
    Process all historical FIRMS CSV files in source_dir.

    Returns
    -------
    List of IngestionResult (one per file).
    """
    source_dir    = source_dir    or settings.HISTORICAL_FIRMS_RAW_PATH
    chunk_size    = chunk_size    or settings.HISTORICAL_FIRMS_CHUNK_SIZE
    batch_size    = batch_size    or settings.FIRMS_BATCH_SIZE
    rejected_dir  = rejected_dir  or (settings.REJECTED_DATA_ROOT / "historical_firms")
    processed_dir = processed_dir or (settings.PROCESSED_DATA_ROOT / "historical_firms")

    csv_files = list_historical_files(source_dir)
    if not csv_files:
        log.warning("historical_firms.pipeline.no_files", directory=str(source_dir))
        return []

    all_results: list[IngestionResult] = []

    for csv_path in csv_files:
        result = IngestionResult(
            dataset_name="NASA_FIRMS_HISTORICAL",
            source_reference=str(csv_path),
        )
        log.info("historical_firms.pipeline.file_start", path=str(csv_path))

        try:
            for chunk in read_historical_firms_chunks(csv_path, chunk_size=chunk_size):
                result.records_read += len(chunk)

                valid_df, rejected_df = validate_firms_dataframe(chunk)
                result.records_valid    += len(valid_df)
                result.records_rejected += len(rejected_df)

                if not rejected_df.empty:
                    rejected_dir.mkdir(parents=True, exist_ok=True)
                    r_path = rejected_dir / f"{csv_path.stem}_rejected_chunk.csv"
                    # Append to rejected file
                    rejected_df.to_csv(
                        r_path, mode="a",
                        header=not r_path.exists(),
                        index=False,
                    )

                if valid_df.empty:
                    continue

                records = normalize_firms_dataframe(valid_df, source_file=csv_path.name)
                records, n_src_rej = filter_invalid_sources(
                    records,
                    rejected_dir=rejected_dir,
                    source_file_name=csv_path.stem,
                )
                result.records_rejected += n_src_rej

                inserted, skipped = load_hotspots_batch(records, batch_size=batch_size)
                result.records_inserted += inserted
                result.records_skipped  += skipped

            result.finish(success=True)
            result.write_manifest(processed_dir)
            log.info("historical_firms.pipeline.file_done", summary=result.summary_line())

        except Exception as exc:
            log.error("historical_firms.pipeline.file_failed", path=str(csv_path), error=str(exc), exc_info=True)
            result.add_error(str(exc))
            result.finish(success=False)

        all_results.append(result)

    return all_results
