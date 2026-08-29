"""
HEATWATCH Data Ingestion — Deduplication Utilities
==================================================
Implements deterministic fingerprinting for records that
lack a provider-assigned external ID.

STRATEGY (matches database/docs/deduplication_strategy.md):

For FIRMS hotspots:
  1. Prefer external_detection_id (source + external_id → UNIQUE in DB)
  2. Fallback: deterministic fingerprint from
       source + latitude(rounded 4dp) + longitude(rounded 4dp) + acquisition_time

For OSM:
  osm_type + osm_id (globally unique within OSM data model)

For industrial facilities:
  source + source_reference (preferred)
  Fallback: name + rounded lat/lon — flagged as "uncertain"
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def firms_fingerprint(
    source: str,
    latitude: float,
    longitude: float,
    acquisition_time: datetime,
    frp: float | None = None,
) -> str:
    """
    Deterministic fingerprint for a FIRMS hotspot row when no
    external_detection_id is available.

    Coordinates are rounded to 4 decimal places (~11 m precision).
    acquisition_time is expressed as ISO UTC string.
    FRP is included as a secondary discriminator when available.

    Returns an 8-character hex digest (not a UUID — used for
    application-level duplicate checking only).
    """
    parts: dict[str, Any] = {
        "source": source,
        "lat": round(float(latitude), 4),
        "lon": round(float(longitude), 4),
        "time": acquisition_time.isoformat(),
    }
    if frp is not None:
        parts["frp"] = round(float(frp), 2)

    raw = json.dumps(parts, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def osm_dedup_key(osm_type: str, osm_id: int) -> str:
    """Return a unique key for an OSM feature."""
    return f"{osm_type}:{osm_id}"


def industrial_dedup_key(source: str, source_reference: str | None) -> str | None:
    """
    Return a dedup key for an industrial facility.
    Returns None if source_reference is not available
    (caller must fallback to spatial/name matching).
    """
    if source_reference:
        return f"{source}::{source_reference}"
    return None


def name_location_fingerprint(
    name: str,
    latitude: float,
    longitude: float,
    facility_type: str,
) -> str:
    """
    Uncertain fallback fingerprint for industrial facilities
    without a source_reference.
    Coordinates rounded to 2 decimal places (~1 km).
    """
    parts = {
        "name": (name or "").strip().lower(),
        "lat": round(float(latitude), 2),
        "lon": round(float(longitude), 2),
        "type": facility_type,
    }
    raw = json.dumps(parts, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:12]
