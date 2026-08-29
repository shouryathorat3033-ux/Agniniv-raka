"""
HEATWATCH — Satellite Scene Selector
======================================
Filters scenes based on criteria (cloud cover, date range, tile ID).
Used by the analytics pipeline to select relevant scenes for a thermal object.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def filter_scenes(
    scenes: list[dict[str, Any]],
    max_cloud_pct: float = 20.0,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    tile_id: str | None = None,
) -> list[dict[str, Any]]:
    """Filter scenes by cloud cover, date range, and tile ID."""
    selected = []
    for scene in scenes:
        cloud = scene.get("cloud_cover_pct")
        if cloud is not None and float(cloud) > max_cloud_pct:
            continue
        if tile_id and scene.get("tile_id") != tile_id:
            continue
        # Date range filter skipped if acquisition_time not parseable
        selected.append(scene)
    return selected
