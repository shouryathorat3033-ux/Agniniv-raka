"""
HEATWATCH — OSM Database Loader
=================================
Loads classified OSM features into:
  - industrial_facilities  (industrial candidates)
  - osm_context           (general context — requires thermal_object_id)

Note on osm_context:
  The osm_context table has a NOT NULL FK to thermal_objects.
  This loader can only insert into osm_context when a valid
  thermal_object_id is supplied. Without one, OSM general features
  are stored only in the processed/ manifest files.

  industrial_facilities can be inserted without a thermal_object_id.

Deduplication:
  industrial_facilities: no unique constraint defined; we check
  source + source_reference at application level before insert.
  osm_context: UNIQUE(thermal_object_id, osm_type, osm_id)
"""
from __future__ import annotations

import json
from typing import Any

from common.db import transaction
from common.logging_config import get_logger

log = get_logger(__name__)

_INSERT_INDUSTRIAL = """
INSERT INTO industrial_facilities (
    name, facility_type, source, source_reference,
    location, boundary, confidence, metadata
) VALUES (
    %(name)s,
    %(facility_type)s::facility_type,
    %(source)s,
    %(source_reference)s,
    ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
    CASE
        WHEN %(boundary_wkt)s IS NOT NULL
        THEN ST_SetSRID(ST_GeomFromText(%(boundary_wkt)s), 4326)
        ELSE NULL
    END,
    %(confidence)s,
    %(metadata)s::jsonb
)
ON CONFLICT DO NOTHING;
"""

_CHECK_INDUSTRIAL_EXISTS = """
SELECT id FROM industrial_facilities
WHERE source = %(source)s
  AND source_reference = %(source_reference)s
LIMIT 1;
"""


def _dedup_industrial(
    records: list[dict[str, Any]],
    conn: Any,
) -> tuple[list[dict[str, Any]], int]:
    """Remove records that already exist by source+source_reference."""
    to_insert: list[dict] = []
    skipped = 0
    for r in records:
        if r.get("source_reference"):
            existing = conn.execute(
                _CHECK_INDUSTRIAL_EXISTS,
                {"source": r["source"], "source_reference": r["source_reference"]},
            ).fetchone()
            if existing:
                skipped += 1
                continue
        to_insert.append(r)
    return to_insert, skipped


def load_industrial_facilities_batch(
    records: list[dict[str, Any]],
    batch_size: int = 500,
) -> tuple[int, int]:
    """
    Insert OSM-derived industrial facility records.
    Returns (inserted, skipped).
    """
    if not records:
        return 0, 0

    total_inserted = 0
    total_skipped  = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        with transaction() as conn:
            to_insert, skipped = _dedup_industrial(batch, conn)
            total_skipped += skipped

            for r in to_insert:
                conn.execute(
                    _INSERT_INDUSTRIAL,
                    {
                        "name":             r["name"],
                        "facility_type":    r["facility_type"],
                        "source":           r["source"],
                        "source_reference": r.get("source_reference"),
                        "lon":              r.get("_lon"),
                        "lat":              r.get("_lat"),
                        "boundary_wkt":     r.get("boundary_wkt"),
                        "confidence":       r.get("confidence"),
                        "metadata":         r.get("metadata"),
                    },
                )
                total_inserted += 1

        log.info(
            "osm.loader.industrial_batch",
            batch_start=i,
            inserted=total_inserted,
            skipped=total_skipped,
        )

    return total_inserted, total_skipped
