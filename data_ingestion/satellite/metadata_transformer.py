"""
HEATWATCH — Satellite Metadata Transformer
==========================================
Prepares satellite scene metadata for manifest files.
No database insertion — existing DB has no satellite_scenes table.

IMPORTANT LIMITATION:
  The current database schema (migrations 000–009) does NOT include
  a satellite_scenes table. Scene metadata is stored as JSON manifests
  in dataset/processed/satellite/.

  Recommendation for future migration:
    CREATE TABLE satellite_scenes (
        id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        scene_id        TEXT NOT NULL UNIQUE,
        source          TEXT NOT NULL,
        acquisition_time TIMESTAMPTZ NOT NULL,
        cloud_cover_pct  NUMERIC(5,2),
        tile_id         TEXT,
        safe_path       TEXT,
        metadata        JSONB,
        created_at      TIMESTAMPTZ DEFAULT NOW()
    );

  Until that migration is added, this module saves metadata to disk only.
"""
from __future__ import annotations

from typing import Any

from common.timestamps import parse_iso_timestamp, now_utc
from common.logging_config import get_logger

log = get_logger(__name__)


def transform_scene_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a scene metadata dict for manifest output.
    Adds ingestion_timestamp.
    """
    out = dict(raw)
    out["ingestion_timestamp"] = now_utc().isoformat()

    # Normalize acquisition_time to ISO UTC
    if out.get("acquisition_time"):
        try:
            dt = parse_iso_timestamp(str(out["acquisition_time"]))
            out["acquisition_time"] = dt.isoformat()
        except Exception:
            pass  # keep original if parse fails

    return out
