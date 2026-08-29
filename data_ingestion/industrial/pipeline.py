"""
HEATWATCH — Industrial Facility Pipeline
==========================================
Orchestrates: READ → VALIDATE → NORMALIZE → TRANSFORM → LOAD
for external industrial facility datasets (GEM, GPPD, EPA, etc.)

Target table: industrial_facilities
"""
from __future__ import annotations

from pathlib import Path

from common.logging_config import get_logger
from common.provenance import IngestionResult
from config import settings
from industrial.normalizer import normalize_industrial_dataframe
from industrial.reader import read_industrial_file
from industrial.transformer import filter_industrial_records
from industrial.validator import validate_industrial_dataframe
from osm.loader import load_industrial_facilities_batch

log = get_logger(__name__)


def run_industrial_pipeline(
    source_path: Path,
    source_name: str = "INDUSTRIAL_DB",
    dataset_id: str | None = None,
    rejected_dir: Path | None = None,
    processed_dir: Path | None = None,
) -> IngestionResult:
    rejected_dir  = rejected_dir  or (settings.REJECTED_DATA_ROOT / "industrial")
    processed_dir = processed_dir or (settings.PROCESSED_DATA_ROOT / "industrial")

    result = IngestionResult(
        dataset_name="INDUSTRIAL_DB",
        source_reference=str(source_path),
    )
    log.info("industrial.pipeline.start", path=str(source_path))

    try:
        gdf = read_industrial_file(source_path)
        result.records_read = len(gdf)

        valid_gdf, rejected_gdf = validate_industrial_dataframe(gdf)
        result.records_valid    = len(valid_gdf)
        result.records_rejected = len(rejected_gdf)

        if not rejected_gdf.empty:
            rejected_dir.mkdir(parents=True, exist_ok=True)
            rejected_gdf.to_file(
                rejected_dir / f"{source_path.stem}_rejected.geojson",
                driver="GeoJSON",
            )

        if valid_gdf.empty:
            return result.finish(success=True)

        records = normalize_industrial_dataframe(valid_gdf, source_name=source_name, dataset_id=dataset_id)
        records, n_rej = filter_industrial_records(records, rejected_dir=rejected_dir)
        result.records_rejected += n_rej

        inserted, skipped = load_industrial_facilities_batch(
            records, batch_size=settings.INDUSTRIAL_BATCH_SIZE
        )
        result.records_inserted = inserted
        result.records_skipped  = skipped

        result.finish(success=True)
        result.write_manifest(processed_dir)
        log.info("industrial.pipeline.done", summary=result.summary_line())

    except Exception as exc:
        log.error("industrial.pipeline.failed", error=str(exc), exc_info=True)
        result.add_error(str(exc))
        result.finish(success=False)
        raise

    return result
