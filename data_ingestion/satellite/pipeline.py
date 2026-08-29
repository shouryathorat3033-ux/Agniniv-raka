"""
HEATWATCH — Satellite Pipeline
================================
Validates and catalogues satellite scene metadata.
Writes processed manifests to dataset/processed/satellite/.
No database insertion (no satellite_scenes table in current schema).
"""
from __future__ import annotations

import json
from pathlib import Path

from common.logging_config import get_logger
from common.provenance import IngestionResult
from config import settings
from satellite.metadata_transformer import transform_scene_metadata
from satellite.scene_reader import list_scene_sources, read_sentinel2_metadata, read_scene_json
from satellite.validator import validate_scene_metadata

log = get_logger(__name__)


def run_satellite_pipeline(
    source_dir: Path | None = None,
    processed_dir: Path | None = None,
    rejected_dir: Path | None = None,
) -> IngestionResult:
    source_dir    = source_dir    or settings.SATELLITE_RAW_PATH
    processed_dir = processed_dir or (settings.PROCESSED_DATA_ROOT / "satellite")
    rejected_dir  = rejected_dir  or (settings.REJECTED_DATA_ROOT / "satellite")

    result = IngestionResult(
        dataset_name="SATELLITE_METADATA",
        source_reference=str(source_dir),
    )

    sources = list_scene_sources(source_dir)
    if not sources:
        log.warning("satellite.pipeline.no_sources", directory=str(source_dir))
        return result.finish(success=True)

    result.records_read = len(sources)
    processed_dir.mkdir(parents=True, exist_ok=True)

    all_metadata: list[dict] = []

    for source in sources:
        try:
            if source.is_dir() and source.suffix == ".SAFE":
                raw_meta = read_sentinel2_metadata(source)
            elif source.suffix == ".json":
                raw_meta = read_scene_json(source)
            else:
                log.warning("satellite.pipeline.unsupported", path=str(source))
                result.records_rejected += 1
                continue

            errors = validate_scene_metadata(raw_meta)
            if errors:
                result.records_rejected += 1
                for e in errors:
                    result.add_error(e)
                rejected_dir.mkdir(parents=True, exist_ok=True)
                (rejected_dir / f"{source.stem}_rejected.json").write_text(
                    json.dumps({"errors": errors, "metadata": raw_meta}, indent=2),
                    encoding="utf-8",
                )
                continue

            normalized = transform_scene_metadata(raw_meta)
            all_metadata.append(normalized)
            result.records_valid += 1

        except Exception as exc:
            log.error("satellite.pipeline.scene_failed", source=str(source), error=str(exc))
            result.records_rejected += 1
            result.add_error(str(exc))

    # Write all valid metadata as a catalogue
    if all_metadata:
        catalogue_path = processed_dir / "scene_catalogue.json"
        catalogue_path.write_text(
            json.dumps(all_metadata, default=str, indent=2),
            encoding="utf-8",
        )
        log.info("satellite.pipeline.catalogue_written", path=str(catalogue_path), scenes=len(all_metadata))

    result.finish(success=True)
    result.write_manifest(processed_dir)
    log.info("satellite.pipeline.done", summary=result.summary_line())
    return result
