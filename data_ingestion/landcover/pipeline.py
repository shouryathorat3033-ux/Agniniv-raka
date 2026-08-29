"""
HEATWATCH — Land Cover Pipeline
==================================
Orchestrates land-cover raster registration and (optionally)
batch lookup for a supplied list of thermal objects.

TWO MODES:
  1. REGISTRATION-ONLY (default):
     Validates the raster, reads metadata, writes a manifest.
     Does NOT insert into the database.
     Use this to confirm the raster is usable.

  2. BATCH-LOOKUP (when thermal_objects provided):
     Performs buffer-window lookup for each supplied thermal object,
     transforms results, and inserts into land_context.
     Requires: thermal_object_id, lon, lat per record.

Example thermal_objects input:
  [
    {"thermal_object_id": "uuid-str", "lon": 72.8, "lat": 21.2},
    ...
  ]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.logging_config import get_logger
from common.provenance import IngestionResult
from config import settings
from landcover.loader import load_land_context_records
from landcover.lookup import lookup_buffer_window
from landcover.reader import read_raster_metadata, validate_raster
from landcover.transformer import transform_landcover_result

log = get_logger(__name__)


def run_landcover_pipeline(
    raster_path: Path,
    thermal_objects: list[dict[str, Any]] | None = None,
    buffer_degrees: float = 0.01,
    rejected_dir: Path | None = None,
    processed_dir: Path | None = None,
) -> IngestionResult:
    """
    Run land-cover pipeline.

    Parameters
    ----------
    raster_path      : Path to GeoTIFF land-cover raster.
    thermal_objects  : Optional list of {thermal_object_id, lon, lat} dicts.
                       If None, only registration/validation is performed.
    buffer_degrees   : Buffer radius for window sampling (~0.01° ≈ 1 km).
    """
    rejected_dir  = rejected_dir  or (settings.REJECTED_DATA_ROOT / "landcover")
    processed_dir = processed_dir or (settings.PROCESSED_DATA_ROOT / "landcover")

    result = IngestionResult(
        dataset_name="LANDCOVER",
        source_reference=str(raster_path),
    )
    log.info("landcover.pipeline.start", path=str(raster_path))

    try:
        # ── 1. VALIDATE RASTER ────────────────────────────────
        errors = validate_raster(raster_path)
        if errors:
            for err in errors:
                result.add_warning(err)
            log.warning("landcover.pipeline.raster_warnings", warnings=errors)

        # ── 2. READ METADATA ──────────────────────────────────
        meta = read_raster_metadata(raster_path)
        result.metadata["raster"] = meta
        log.info("landcover.pipeline.metadata", **{k: str(v) for k, v in meta.items()})

        # Write metadata manifest
        processed_dir.mkdir(parents=True, exist_ok=True)
        meta_out = processed_dir / f"{raster_path.stem}_metadata.json"
        meta_out.write_text(json.dumps(meta, default=str, indent=2), encoding="utf-8")
        log.info("landcover.pipeline.manifest_written", path=str(meta_out))

        if not thermal_objects:
            log.info("landcover.pipeline.registration_only")
            result.records_read = 0
            return result.finish(success=True)

        # ── 3. BATCH LOOKUP ───────────────────────────────────
        result.records_read = len(thermal_objects)
        to_insert: list[dict] = []

        for obj in thermal_objects:
            tid = obj.get("thermal_object_id")
            lon = obj.get("lon")
            lat = obj.get("lat")
            if not tid or lon is None or lat is None:
                result.records_rejected += 1
                result.add_error(f"Invalid thermal_object entry: {obj}")
                continue
            try:
                scores = lookup_buffer_window(raster_path, lon, lat, buffer_degrees=buffer_degrees)
                record = transform_landcover_result(
                    scores,
                    thermal_object_id=str(tid),
                    land_cover_source=settings.LANDCOVER_DATASET_ID,
                    resolution_meters=settings.LANDCOVER_RESOLUTION_M,
                )
                to_insert.append(record)
                result.records_valid += 1
            except Exception as exc:
                log.warning("landcover.pipeline.lookup_failed", tid=str(tid), error=str(exc))
                result.records_rejected += 1
                result.add_error(str(exc))

        # ── 4. LOAD ───────────────────────────────────────────
        inserted, skipped = load_land_context_records(to_insert)
        result.records_inserted = inserted
        result.records_skipped  = skipped

    except Exception as exc:
        log.error("landcover.pipeline.failed", error=str(exc), exc_info=True)
        result.add_error(str(exc))
        result.finish(success=False)
        raise

    result.finish(success=True)
    result.write_manifest(processed_dir)
    log.info("landcover.pipeline.done", summary=result.summary_line())
    return result
