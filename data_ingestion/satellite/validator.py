"""
HEATWATCH — Satellite Scene Validator
========================================
Validates scene metadata dicts before use.
"""
from __future__ import annotations

from typing import Any

from common.logging_config import get_logger
from common.timestamps import parse_iso_timestamp
from common.exceptions import InvalidTimestampError

log = get_logger(__name__)


def validate_scene_metadata(meta: dict[str, Any]) -> list[str]:
    """
    Validate a scene metadata dict.
    Returns list of error strings. Empty = valid.
    """
    errors: list[str] = []

    if not meta.get("scene_id"):
        errors.append("scene_id is missing")

    if not meta.get("source"):
        errors.append("source is missing")

    acq = meta.get("acquisition_time")
    if not acq:
        errors.append("acquisition_time is missing")
    else:
        try:
            parse_iso_timestamp(str(acq))
        except InvalidTimestampError as exc:
            errors.append(f"acquisition_time invalid: {exc}")

    cloud = meta.get("cloud_cover_pct")
    if cloud is not None:
        try:
            f = float(cloud)
            if not (0.0 <= f <= 100.0):
                errors.append(f"cloud_cover_pct={f} is outside [0, 100]")
        except (TypeError, ValueError):
            errors.append(f"cloud_cover_pct={cloud!r} is not numeric")

    return errors
