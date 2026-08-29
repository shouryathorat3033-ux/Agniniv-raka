"""
HEATWATCH — OSM Database Operations
======================================
Creates the osm_features table, indexes, and handles batch insertion.
Reuses existing db.py connection pool and transaction helper.
"""
from __future__ import annotations

import json
from typing import Any

import psycopg

from common.db import get_pool, transaction
from common.logging_config import get_logger

log = get_logger(__name__)

# ── DDL ────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS osm_features (
    id            BIGSERIAL PRIMARY KEY,
    osm_id        BIGINT    NOT NULL,
    feature_type  TEXT      NOT NULL,
    name          TEXT,
    subtype       TEXT,
    tags          JSONB,
    source        TEXT      NOT NULL DEFAULT 'OpenStreetMap',
    geometry      GEOMETRY(Geometry, 4326),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_osm_features_id_type UNIQUE (osm_id, feature_type)
);
"""

_CREATE_SPATIAL_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_osm_features_geometry
    ON osm_features USING GIST (geometry);
"""

_CREATE_TYPE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_osm_features_type
    ON osm_features (feature_type);
"""

_CREATE_OSMID_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_osm_features_osm_id
    ON osm_features (osm_id);
"""

_UPSERT_SQL = """
INSERT INTO osm_features (
    osm_id, feature_type, name, subtype, tags, source, geometry
)
VALUES (
    %(osm_id)s,
    %(feature_type)s,
    %(name)s,
    %(subtype)s,
    %(tags)s::jsonb,
    %(source)s,
    CASE
        WHEN %(geometry_wkt)s IS NULL THEN NULL
        ELSE ST_SetSRID(ST_GeomFromText(%(geometry_wkt)s), 4326)
    END
)
ON CONFLICT ON CONSTRAINT uq_osm_features_id_type
DO UPDATE SET
    name        = EXCLUDED.name,
    subtype     = EXCLUDED.subtype,
    tags        = EXCLUDED.tags,
    geometry    = EXCLUDED.geometry,
    updated_at  = NOW()
"""


def ensure_schema() -> None:
    """Create osm_features table and indexes if they do not exist."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = True
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_SPATIAL_INDEX_SQL)
        conn.execute(_CREATE_TYPE_INDEX_SQL)
        conn.execute(_CREATE_OSMID_INDEX_SQL)
        log.info("osm.database.schema_ready")
    finally:
        pool.putconn(conn)


def insert_batch(
    batch: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Upsert a batch of feature dicts into osm_features.

    Returns (inserted_count, upserted_count).
    Uses ON CONFLICT DO UPDATE so re-runs are safe.
    """
    if not batch:
        return 0, 0

    inserted = 0
    updated  = 0

    with transaction() as conn:
        for row in batch:
            result = conn.execute(_UPSERT_SQL, {
                "osm_id":       row["osm_id"],
                "feature_type": row["feature_type"],
                "name":         row.get("name"),
                "subtype":      row.get("subtype"),
                "tags":         row.get("tags") or "{}",
                "source":       row.get("source", "OpenStreetMap"),
                "geometry_wkt": row.get("geometry_wkt"),
            })
            # rowcount=1 for INSERT, 0 for DO NOTHING (but we use DO UPDATE)
            if result.rowcount > 0:
                inserted += 1

    return inserted, updated


def get_feature_counts() -> dict[str, int]:
    """Return per-feature-type row counts from osm_features."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        rows = conn.execute(
            "SELECT feature_type, COUNT(*) FROM osm_features GROUP BY feature_type ORDER BY 1"
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        pool.putconn(conn)


def get_total_count() -> int:
    pool = get_pool()
    conn = pool.getconn()
    try:
        row = conn.execute("SELECT COUNT(*) FROM osm_features").fetchone()
        return row[0] if row else 0
    finally:
        pool.putconn(conn)


def table_exists() -> bool:
    pool = get_pool()
    conn = pool.getconn()
    try:
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='osm_features'"
        ).fetchone()
        return row is not None
    finally:
        pool.putconn(conn)
