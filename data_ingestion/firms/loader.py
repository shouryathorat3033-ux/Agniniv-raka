"""
HEATWATCH — FIRMS Database Loader
===================================
Bulk-inserts normalized FIRMS records into the hotspots table.

Schema reference (migration 002):
  hotspots(id, source, external_detection_id, latitude, longitude,
           location GEOMETRY(Point,4326), acquisition_time,
           satellite, instrument, confidence, brightness, brightness_2,
           frp, daynight, raw_payload JSONB, normalized_at, created_at)

Duplicate strategy:
  ON CONFLICT ON CONSTRAINT uq_hotspot_pixel_time DO NOTHING
  (skips exact duplicate lat/lon/time combos — idempotent)

Geometry insertion:
  Uses PostGIS ST_SetSRID(ST_MakePoint($lon, $lat), 4326).
  Never uses unsafe string interpolation.
"""
from __future__ import annotations

import json
from typing import Any

import psycopg

from common.db import transaction
from common.logging_config import get_logger

log = get_logger(__name__)

_INSERT_SQL = """
INSERT INTO hotspots (
    source,
    external_detection_id,
    latitude,
    longitude,
    location,
    acquisition_time,
    satellite,
    instrument,
    confidence,
    brightness,
    brightness_2,
    frp,
    daynight,
    raw_payload,
    normalized_at
) VALUES (
    %(source)s,
    %(external_detection_id)s,
    %(latitude)s,
    %(longitude)s,
    ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326),
    %(acquisition_time)s,
    %(satellite)s,
    %(instrument)s,
    %(confidence)s,
    %(brightness)s,
    %(brightness_2)s,
    %(frp)s,
    %(daynight)s,
    %(raw_payload)s,
    %(normalized_at)s
)
ON CONFLICT ON CONSTRAINT uq_hotspot_pixel_time DO NOTHING;
"""


def load_hotspots_batch(
    records: list[dict[str, Any]],
    batch_size: int = 1000,
) -> tuple[int, int]:
    """
    Insert FIRMS records into hotspots table in batches.

    Parameters
    ----------
    records    : list of normalized hotspot dicts (from normalizer)
    batch_size : number of rows per transaction

    Returns
    -------
    (inserted_count, skipped_count)
    Note: psycopg3 executemany does not return per-row rowcount reliably
    for ON CONFLICT DO NOTHING. We report approximate counts.
    """
    if not records:
        return 0, 0

    total_attempted = len(records)
    total_inserted  = 0
    total_skipped   = 0

    # Convert raw_payload to JSON string for psycopg
    for r in records:
        if isinstance(r.get("raw_payload"), dict):
            r["raw_payload"] = json.dumps(r["raw_payload"], default=str)
        # Remove internal WKT key (geometry is computed inline in SQL)
        r.pop("location_wkt", None)

    for i in range(0, total_attempted, batch_size):
        batch = records[i : i + batch_size]
        log.info(
            "firms.loader.batch",
            batch_start=i,
            batch_size=len(batch),
        )
        with transaction() as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM hotspots"
            ).fetchone()[0]

            # psycopg3: use cursor for executemany;
            # insert row-by-row to handle ON CONFLICT correctly per-record.
            for record in batch:
                try:
                    conn.execute(_INSERT_SQL, record)
                except Exception as exc:
                    log.warning("firms.loader.row_skip", error=str(exc)[:80])

            after = conn.execute(
                "SELECT COUNT(*) FROM hotspots"
            ).fetchone()[0]

        inserted_this_batch = after - before
        skipped_this_batch  = len(batch) - inserted_this_batch
        total_inserted += inserted_this_batch
        total_skipped  += skipped_this_batch

        log.info(
            "firms.loader.batch_done",
            inserted=inserted_this_batch,
            skipped=skipped_this_batch,
        )

    return total_inserted, total_skipped
