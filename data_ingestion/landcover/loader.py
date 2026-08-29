"""
HEATWATCH — Land Cover Database Loader
========================================
Inserts land_context rows for thermal objects.

IMPORTANT: This loader requires valid thermal_object_ids.
land_context has a NOT NULL FK to thermal_objects(id).
Callers must supply a mapping: thermal_object_id → land-cover scores.

Target table (migration 003):
  land_context(thermal_object_id, land_cover_class, land_cover_source,
               resolution_meters, built_up_score, cropland_score,
               tree_cover_score, shrubland_score, grassland_score,
               water_score, bare_land_score, metadata)
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from common.db import transaction
from common.logging_config import get_logger
from config import settings

log = get_logger(__name__)

_INSERT_LAND_CONTEXT = """
INSERT INTO land_context (
    thermal_object_id,
    land_cover_class,
    land_cover_source,
    resolution_meters,
    built_up_score,
    cropland_score,
    tree_cover_score,
    shrubland_score,
    grassland_score,
    water_score,
    bare_land_score,
    metadata
) VALUES (
    %(thermal_object_id)s,
    %(land_cover_class)s,
    %(land_cover_source)s,
    %(resolution_meters)s,
    %(built_up_score)s,
    %(cropland_score)s,
    %(tree_cover_score)s,
    %(shrubland_score)s,
    %(grassland_score)s,
    %(water_score)s,
    %(bare_land_score)s,
    %(metadata)s::jsonb
)
ON CONFLICT ON CONSTRAINT uq_land_context_source DO NOTHING;
"""


def load_land_context_records(
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Insert land_context records.

    Each record must include:
      thermal_object_id : UUID str
      land_cover_source : str (e.g. 'ESA_WorldCover_2021')
      + optional score fields and metadata

    Returns (inserted, skipped).
    """
    if not records:
        return 0, 0

    total_inserted = 0
    total_skipped  = 0

    with transaction() as conn:
        for r in records:
            meta = r.get("metadata", {})
            if isinstance(meta, dict):
                meta = json.dumps(meta)

            result = conn.execute(
                _INSERT_LAND_CONTEXT,
                {
                    "thermal_object_id": r["thermal_object_id"],
                    "land_cover_class":  r.get("land_cover_class"),
                    "land_cover_source": r.get("land_cover_source", settings.LANDCOVER_DATASET_ID),
                    "resolution_meters": r.get("resolution_meters", settings.LANDCOVER_RESOLUTION_M),
                    "built_up_score":    r.get("built_up_score"),
                    "cropland_score":    r.get("cropland_score"),
                    "tree_cover_score":  r.get("tree_cover_score"),
                    "shrubland_score":   r.get("shrubland_score"),
                    "grassland_score":   r.get("grassland_score"),
                    "water_score":       r.get("water_score"),
                    "bare_land_score":   r.get("bare_land_score"),
                    "metadata":          meta,
                },
            )
            if result.rowcount > 0:
                total_inserted += 1
            else:
                total_skipped += 1

    log.info("landcover.loader.done", inserted=total_inserted, skipped=total_skipped)
    return total_inserted, total_skipped
