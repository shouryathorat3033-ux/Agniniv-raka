"""
HEATWATCH — FIRMS Normalizer
=============================
Normalizes validated FIRMS rows into the exact column format
required by the hotspots table.

hotspots schema (from migration 002):
  source                TEXT NOT NULL (CHECK constraint — see HOTSPOT_SOURCES)
  external_detection_id TEXT nullable
  latitude              DOUBLE PRECISION
  longitude             DOUBLE PRECISION
  location              GEOMETRY(Point,4326)  ← built in transformer
  acquisition_time      TIMESTAMPTZ NOT NULL
  satellite             TEXT nullable
  instrument            TEXT nullable
  confidence            TEXT nullable
  brightness            NUMERIC(10,4) nullable  ← Band 21 / bright_ti4
  brightness_2          NUMERIC(10,4) nullable  ← Band 31 / bright_ti5
  frp                   NUMERIC(14,4) nullable
  daynight              CHAR(1) nullable (D or N)
  raw_payload           JSONB nullable
  normalized_at         TIMESTAMPTZ
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from common.logging_config import get_logger
from common.timestamps import parse_firms_datetime, now_utc
from config.datasets import (
    FIRMS_SATELLITE_MAP,
    FIRMS_INSTRUMENT_MAP,
    HOTSPOT_SOURCES,
)

log = get_logger(__name__)

# ── Confidence normalization ──────────────────────────────────
# FIRMS text confidence: 'l'/'low', 'n'/'nominal', 'h'/'high'
# VIIRS: integer 0-100
_CONFIDENCE_TEXT_MAP = {
    "l": "low", "low": "low",
    "n": "nominal", "nominal": "nominal",
    "h": "high", "high": "high",
}


def _normalize_confidence(raw: Any) -> str | None:
    if raw is None or str(raw).strip() in ("", "nan"):
        return None
    s = str(raw).strip().lower()
    if s in _CONFIDENCE_TEXT_MAP:
        return _CONFIDENCE_TEXT_MAP[s]
    # VIIRS numeric (0–100): return as-is string
    try:
        n = int(float(s))
        if 0 <= n <= 100:
            return str(n)
    except (ValueError, TypeError):
        pass
    return s  # preserve unknown formats


def _normalize_satellite(raw: Any) -> str:
    """Map FIRMS satellite string to hotspots.source allowed value."""
    s = str(raw).strip() if raw else ""
    mapped = FIRMS_SATELLITE_MAP.get(s) or FIRMS_SATELLITE_MAP.get(s.upper()) or FIRMS_SATELLITE_MAP.get(s.lower())
    return mapped or "OTHER"


def _normalize_instrument(raw: Any) -> str | None:
    if not raw or str(raw).strip() in ("", "nan"):
        return None
    s = str(raw).strip().upper()
    return FIRMS_INSTRUMENT_MAP.get(s, s)


def _safe_numeric(val: Any) -> float | None:
    if val is None or str(val).strip() in ("", "nan"):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _normalize_daynight(val: Any) -> str | None:
    if not val or str(val).strip() in ("", "nan"):
        return None
    s = str(val).strip().upper()[0]
    return s if s in ("D", "N") else None


def normalize_firms_row(row: pd.Series, source_file: str) -> dict[str, Any]:
    """
    Normalize a single valid FIRMS row into a hotspots insert dict.

    Parameters
    ----------
    row         : pandas Series (validated FIRMS row)
    source_file : str — source CSV filename for provenance

    Returns
    -------
    dict matching hotspots column names.
    The 'location' key contains a WKT string for PostGIS insertion.
    raw_payload contains the original row as JSON for audit.
    """
    lat = float(row["latitude"])
    lon = float(row["longitude"])

    acquisition_time: datetime = parse_firms_datetime(
        row["acq_date"], row["acq_time"]
    )

    # Satellite → source (hotspots.source CHECK constraint)
    sat_raw = row.get("satellite", "")
    source = _normalize_satellite(sat_raw)

    # satellite field stores the human-readable satellite name
    satellite_name = str(sat_raw).strip() if sat_raw else None

    instrument = _normalize_instrument(row.get("instrument"))
    confidence  = _normalize_confidence(row.get("confidence"))
    brightness  = _safe_numeric(row.get("brightness"))
    brightness_2 = _safe_numeric(row.get("brightness_2"))
    frp         = _safe_numeric(row.get("frp"))
    daynight    = _normalize_daynight(row.get("daynight"))

    # Preserve full original row as JSONB raw_payload
    raw_payload = json.dumps(row.to_dict(), default=str)

    return {
        "source":               source,
        "external_detection_id": None,   # FIRMS CSV products do not supply a row-level ID
        "latitude":             lat,
        "longitude":            lon,
        "location_wkt":         f"POINT({lon} {lat})",
        "acquisition_time":     acquisition_time,
        "satellite":            satellite_name,
        "instrument":           instrument,
        "confidence":           confidence,
        "brightness":           brightness,
        "brightness_2":         brightness_2,
        "frp":                  frp,
        "daynight":             daynight,
        "raw_payload":          raw_payload,
        "normalized_at":        now_utc(),
    }


def normalize_firms_dataframe(df: pd.DataFrame, source_file: str) -> list[dict[str, Any]]:
    """
    Normalize an entire validated FIRMS DataFrame.
    Skips rows that raise exceptions during normalization and logs them.
    Returns a list of hotspot dicts ready for database insertion.
    """
    records: list[dict[str, Any]] = []
    skipped = 0
    for _, row in df.iterrows():
        try:
            records.append(normalize_firms_row(row, source_file))
        except Exception as exc:
            log.warning("firms.normalizer.row_skipped", error=str(exc))
            skipped += 1

    if skipped:
        log.warning("firms.normalizer.rows_skipped", count=skipped)

    log.info("firms.normalizer.done", output_records=len(records))
    return records
