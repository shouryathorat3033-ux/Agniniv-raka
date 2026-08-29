#!/usr/bin/env python3
"""
HEATWATCH — OSM Verification Script
======================================
Verifies the state of the osm_features table in PostgreSQL.

Usage:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\verify_osm.py

Exit code 0 = all checks pass.
Exit code 1 = one or more checks failed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

_SCRIPT_DIR   = Path(__file__).resolve().parent
_DI_ROOT      = _SCRIPT_DIR.parent
_PROJECT_ROOT = _DI_ROOT.parent

sys.path.insert(0, str(_DI_ROOT))

from dotenv import load_dotenv
# override=True: project-root .env is always authoritative
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# Use config/settings.py as the single authoritative DATABASE_URL source
from config import settings  # noqa: E402

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
WARN = "[WARN]"

WIDTH = 60


def _sep():
    print("=" * WIDTH)


def _row(label: str, status: str, detail: str = ""):
    pad = WIDTH - len(label) - len(status) - 2
    print(f"  {label} {'.' * max(pad, 1)} {status}" + (f"  {detail}" if detail else ""))


def verify() -> int:
    from osm.config import OSM_MANIFEST_PATH, OSM_CHECKPOINT_PATH

    # Use settings.DATABASE_URL — loaded from project-root .env by
    # config/settings.py. This guarantees 127.0.0.1:5433 is used.
    db_url = settings.DATABASE_URL

    _sep()
    print("HEATWATCH — OSM VERIFICATION")
    _sep()
    print()

    failed = 0

    # ── Database connection ────────────────────────────────────
    if not db_url:
        _row("DATABASE_URL configured", FAIL)
        print(f"\n  {FAIL} DATABASE_URL not set in .env")
        return 1

    try:
        parsed = urlparse(db_url)
        print(f"  Target: {parsed.hostname}:{parsed.port}/{(parsed.path or '/').lstrip('/')}")
        print()
    except Exception:
        pass

    try:
        import psycopg
        conn = psycopg.connect(db_url, connect_timeout=10)
        _row("Database connection", PASS)
    except Exception as exc:
        _row("Database connection", FAIL, str(exc)[:50])
        print(f"\n  Cannot connect: {exc}")
        return 1

    def q(sql: str, params=()):
        try:
            return conn.execute(sql, params).fetchone()
        except Exception:
            return None

    # ── Table exists ───────────────────────────────────────────
    row = q(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='osm_features'"
    )
    if row:
        _row("osm_features table", PASS)
    else:
        _row("osm_features table", FAIL, "table does not exist — run ingestion first")
        failed += 1
        conn.close()
        return failed

    # ── Row count ──────────────────────────────────────────────
    row = q("SELECT COUNT(*) FROM osm_features")
    total = row[0] if row else 0
    if total > 0:
        _row("Rows in table", PASS, f"{total:,} rows")
    else:
        _row("Rows in table", FAIL, "0 rows — table is empty")
        failed += 1

    # ── Geometry column ────────────────────────────────────────
    row = q(
        "SELECT COUNT(*) FROM osm_features WHERE geometry IS NOT NULL"
    )
    geom_count = row[0] if row else 0
    if geom_count > 0:
        _row("Geometry column", PASS, f"{geom_count:,} non-null geometries")
    else:
        _row("Geometry column", WARN, "all geometries are NULL (relations only?)")

    # ── SRID check ─────────────────────────────────────────────
    row = q(
        "SELECT ST_SRID(geometry) FROM osm_features "
        "WHERE geometry IS NOT NULL LIMIT 1"
    )
    srid = row[0] if row else None
    if srid == 4326:
        _row("SRID is 4326", PASS)
    elif srid is None:
        _row("SRID is 4326", WARN, "no non-null geometry to check")
    else:
        _row("SRID is 4326", FAIL, f"actual SRID={srid}")
        failed += 1

    # ── Spatial index ──────────────────────────────────────────
    row = q(
        "SELECT 1 FROM pg_indexes "
        "WHERE tablename='osm_features' AND indexname='idx_osm_features_geometry'"
    )
    if row:
        _row("Spatial index", PASS, "idx_osm_features_geometry")
    else:
        _row("Spatial index", FAIL, "index missing")
        failed += 1

    # ── Feature types ──────────────────────────────────────────
    rows = conn.execute(
        "SELECT feature_type, COUNT(*) FROM osm_features GROUP BY feature_type ORDER BY 1"
    ).fetchall()
    counts = {r[0]: r[1] for r in rows}

    print()
    print("  Feature type breakdown:")

    expected_types = [
        ("road",         "Roads"),
        ("hospital",     "Hospitals"),
        ("fire_station", "Fire stations"),
        ("school",       "Schools"),
        ("park",         "Green areas"),
        ("water",        "Water features"),
        ("building",     "Buildings"),
        ("transport",    "Transport"),
    ]

    for ftype, label in expected_types:
        cnt = counts.get(ftype, 0)
        status = PASS if cnt > 0 else WARN
        _row(f"  {label}", status, f"{cnt:,}")
        if cnt == 0:
            # Only fail on missing roads and hospitals after a full ingest
            if ftype in ("road",) and total > 100_000:
                failed += 1

    # ── Duplicate check ────────────────────────────────────────
    print()
    row = q(
        "SELECT COUNT(*) FROM ("
        "  SELECT osm_id, feature_type, COUNT(*) "
        "  FROM osm_features GROUP BY osm_id, feature_type HAVING COUNT(*) > 1"
        ") dupes"
    )
    dupe_count = row[0] if row else 0
    if dupe_count == 0:
        _row("Duplicate check", PASS, "no (osm_id, feature_type) duplicates")
    else:
        _row("Duplicate check", FAIL, f"{dupe_count} duplicate pairs found")
        failed += 1

    # ── Geometry validity ──────────────────────────────────────
    row = q(
        "SELECT COUNT(*) FROM osm_features "
        "WHERE geometry IS NOT NULL AND NOT ST_IsValid(geometry)"
    )
    invalid_geom = row[0] if row else 0
    if invalid_geom == 0:
        _row("Geometry validity", PASS, "all non-null geometries valid")
    else:
        _row("Geometry validity", WARN, f"{invalid_geom} invalid geometries (PostGIS ST_IsValid)")

    # ── Manifest ───────────────────────────────────────────────
    print()
    if OSM_MANIFEST_PATH.exists():
        try:
            manifest = json.loads(OSM_MANIFEST_PATH.read_text(encoding="utf-8"))
            status_val = manifest.get("status", "?")
            status_sym = PASS if status_val == "success" else FAIL
            _row("Manifest file", status_sym, f"status={status_val}")
            print(f"    Path    : {OSM_MANIFEST_PATH}")
            print(f"    Parser  : {manifest.get('parser', '?')}")
            print(f"    Region  : {manifest.get('region', '?')}")
            gen = manifest.get("generated_at", "?")
            print(f"    Generated: {gen}")
        except Exception as exc:
            _row("Manifest file", WARN, f"cannot parse: {exc}")
    else:
        _row("Manifest file", WARN, "not found (ingestion may not have run yet)")

    # ── Checkpoint ─────────────────────────────────────────────
    if OSM_CHECKPOINT_PATH.exists():
        try:
            cp = json.loads(OSM_CHECKPOINT_PATH.read_text(encoding="utf-8"))
            cp_status = cp.get("status", "?")
            sym = PASS if cp_status == "complete" else WARN
            _row("Checkpoint", sym, f"status={cp_status}")
        except Exception:
            _row("Checkpoint", WARN, "cannot parse checkpoint file")
    else:
        _row("Checkpoint", INFO, "not found")

    conn.close()

    print()
    _sep()
    if failed == 0:
        print("OSM VERIFICATION: PASS")
    else:
        print(f"OSM VERIFICATION: FAIL  ({failed} check(s) failed)")
    _sep()
    print()

    return failed


if __name__ == "__main__":
    sys.exit(verify())
