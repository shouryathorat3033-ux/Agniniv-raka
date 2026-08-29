"""
HEATWATCH — OSM Pipeline
==========================
Orchestrates the OSM ETL: READ → VALIDATE → CLASSIFY → TRANSFORM → LOAD.

Routing:
  Industrial candidates → industrial_facilities table
  General context       → NOT loaded (osm_context requires thermal_object_id FK)
                          General context features saved to processed/ as GeoJSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from common.logging_config import get_logger
from common.provenance import IngestionResult
from config import settings
from osm.loader import load_industrial_facilities_batch
from osm.normalizer import classify_osm_features
from osm.reader import read_osm_file, list_osm_files
from osm.transformer import filter_industrial_records
from osm.validator import validate_osm_dataframe

log = get_logger(__name__)


def run_osm_pipeline(
    source_path: Path | None = None,
    rejected_dir: Path | None = None,
    processed_dir: Path | None = None,
) -> IngestionResult:
    """
    Run OSM ingestion for all files in source_path directory.
    """
    source_path   = source_path   or settings.OSM_RAW_PATH
    rejected_dir  = rejected_dir  or (settings.REJECTED_DATA_ROOT / "osm")
    processed_dir = processed_dir or (settings.PROCESSED_DATA_ROOT / "osm")

    result = IngestionResult(
        dataset_name="OSM",
        source_reference=str(source_path),
    )

    files = list_osm_files(source_path)
    if not files:
        log.warning("osm.pipeline.no_files", directory=str(source_path))
        return result.finish(success=True)

    for osm_file in files:
        log.info("osm.pipeline.file_start", path=str(osm_file))

        try:
            gdf = read_osm_file(osm_file)
            result.records_read += len(gdf)

            valid_gdf, rejected_gdf = validate_osm_dataframe(gdf)
            result.records_valid    += len(valid_gdf)
            result.records_rejected += len(rejected_gdf)

            # Write rejected geometries
            if not rejected_gdf.empty:
                rejected_dir.mkdir(parents=True, exist_ok=True)
                rejected_gdf.to_file(
                    rejected_dir / f"{osm_file.stem}_rejected.geojson",
                    driver="GeoJSON",
                )

            if valid_gdf.empty:
                continue

            industrial_recs, context_recs = classify_osm_features(valid_gdf)

            # Filter industrial records
            industrial_recs, n_rej = filter_industrial_records(
                industrial_recs, rejected_dir=rejected_dir
            )
            result.records_rejected += n_rej

            # Load industrial facilities
            inserted, skipped = load_industrial_facilities_batch(industrial_recs)
            result.records_inserted += inserted
            result.records_skipped  += skipped

            # Save context records to processed/ as GeoJSON (not yet loadable without thermal_object_id)
            if context_recs:
                processed_dir.mkdir(parents=True, exist_ok=True)
                ctx_out = processed_dir / f"{osm_file.stem}_context_features.json"
                ctx_out.write_text(
                    json.dumps(context_recs, default=str, indent=2),
                    encoding="utf-8",
                )
                result.add_warning(
                    f"{len(context_recs)} general context features saved to {ctx_out} "
                    "(not loaded — osm_context table requires thermal_object_id)"
                )

        except Exception as exc:
            log.error("osm.pipeline.file_failed", path=str(osm_file), error=str(exc), exc_info=True)
            result.add_error(f"{osm_file.name}: {exc}")

    result.finish(success=True)
    result.write_manifest(processed_dir)
    log.info("osm.pipeline.done", summary=result.summary_line())
    return result
