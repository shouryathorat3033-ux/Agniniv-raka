"""
HEATWATCH — Satellite Loader
================================
No-op loader: the current database schema has no satellite_scenes table.
Scene metadata is stored as JSON manifests only.
This module documents the limitation and provides a stub.
"""
from __future__ import annotations

from typing import Any

from common.logging_config import get_logger

log = get_logger(__name__)


def load_scene_metadata(records: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Stub loader.
    Returns (0, 0) — no database insertion until satellite_scenes migration is added.
    """
    log.warning(
        "satellite.loader.no_table",
        count=len(records),
        message=(
            "No satellite_scenes table in current schema. "
            "Scene metadata stored as manifest files only. "
            "Add a future migration to enable DB persistence."
        ),
    )
    return 0, 0
