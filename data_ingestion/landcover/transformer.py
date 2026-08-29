"""
HEATWATCH — Land Cover Transformer
=====================================
Prepares land-cover lookup results for database insertion.
Clamps scores to [0.0, 1.0] and adds dataset provenance metadata.
"""
from __future__ import annotations

from typing import Any

from common.logging_config import get_logger

log = get_logger(__name__)

_SCORE_FIELDS = [
    "built_up_score", "cropland_score", "tree_cover_score",
    "shrubland_score", "grassland_score", "water_score", "bare_land_score",
]


def transform_landcover_result(
    raw: dict[str, Any],
    thermal_object_id: str,
    land_cover_source: str,
    resolution_meters: int,
    dataset_id: str | None = None,
) -> dict[str, Any]:
    """
    Transform a raw lookup result dict into a land_context insert dict.
    Clamps all score values to [0.0, 1.0].
    """
    record: dict[str, Any] = {
        "thermal_object_id": thermal_object_id,
        "land_cover_class":  raw.get("land_cover_class"),
        "land_cover_source": land_cover_source,
        "resolution_meters": resolution_meters,
    }

    for field in _SCORE_FIELDS:
        val = raw.get(field)
        if val is not None:
            try:
                clamped = min(1.0, max(0.0, float(val)))
                record[field] = round(clamped, 4)
            except (TypeError, ValueError):
                record[field] = None
        else:
            record[field] = None

    # metadata
    meta: dict[str, Any] = {}
    if dataset_id:
        meta["dataset_id"] = dataset_id
    if raw.get("pixel_count") is not None:
        meta["pixel_count"] = raw["pixel_count"]
    if raw.get("buffer_degrees") is not None:
        meta["buffer_degrees"] = raw["buffer_degrees"]
    record["metadata"] = meta

    return record
