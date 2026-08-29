"""
HEATWATCH Data Ingestion — Field Validators
============================================
Row-level validators used by all six pipelines.
Each validator returns a list of error strings (empty = valid).
Never raises — callers accumulate errors and decide what to do.
"""
from __future__ import annotations

from typing import Any


# ── Coordinate validators ─────────────────────────────────────

def validate_latitude(value: Any) -> list[str]:
    try:
        f = float(value)
        if not (-90.0 <= f <= 90.0):
            return [f"Latitude {f} is outside valid range [-90, 90]"]
        return []
    except (TypeError, ValueError):
        return [f"Latitude {value!r} is not a valid number"]


def validate_longitude(value: Any) -> list[str]:
    try:
        f = float(value)
        if not (-180.0 <= f <= 180.0):
            return [f"Longitude {f} is outside valid range [-180, 180]"]
        return []
    except (TypeError, ValueError):
        return [f"Longitude {value!r} is not a valid number"]


def validate_coordinates(lat: Any, lon: Any) -> list[str]:
    return validate_latitude(lat) + validate_longitude(lon)


# ── Numeric validators ────────────────────────────────────────

def validate_positive_float(value: Any, field_name: str) -> list[str]:
    if value is None or value == "":
        return []  # optional numeric fields are allowed to be missing
    try:
        f = float(value)
        if f < 0:
            return [f"{field_name}={f!r} must be >= 0"]
        return []
    except (TypeError, ValueError):
        return [f"{field_name}={value!r} is not a valid number"]


def validate_confidence_range(value: Any, field_name: str = "confidence") -> list[str]:
    """Validate a 0.0–1.0 confidence score."""
    if value is None or value == "":
        return []
    try:
        f = float(value)
        if not (0.0 <= f <= 1.0):
            return [f"{field_name}={f!r} must be between 0.0 and 1.0"]
        return []
    except (TypeError, ValueError):
        return [f"{field_name}={value!r} is not a valid number"]


# ── String validators ─────────────────────────────────────────

def validate_not_empty(value: Any, field_name: str) -> list[str]:
    if value is None or str(value).strip() == "":
        return [f"{field_name} must not be empty"]
    return []


def validate_in_set(value: Any, allowed: frozenset, field_name: str) -> list[str]:
    if value not in allowed:
        return [f"{field_name}={value!r} is not in allowed set: {sorted(allowed)}"]
    return []


# ── Schema validators ─────────────────────────────────────────

def check_required_columns(
    actual_columns: set[str],
    required: frozenset[str],
    dataset_name: str,
) -> list[str]:
    """Return errors for any required columns that are missing."""
    missing = required - actual_columns
    if missing:
        return [
            f"[{dataset_name}] Required columns missing: {sorted(missing)}. "
            f"Available columns: {sorted(actual_columns)}"
        ]
    return []


# ── Geometry validators ───────────────────────────────────────

def validate_geometry_wkt(wkt_str: str | None, field_name: str = "geometry") -> list[str]:
    if not wkt_str:
        return []  # optional geometry
    try:
        from shapely import wkt
        geom = wkt.loads(wkt_str)
        if not geom.is_valid:
            return [f"{field_name} WKT is not a valid geometry: {geom.is_valid_reason}"]
        return []
    except Exception as exc:
        return [f"{field_name} WKT parse failed: {exc}"]
