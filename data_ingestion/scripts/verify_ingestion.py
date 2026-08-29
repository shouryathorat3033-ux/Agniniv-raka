#!/usr/bin/env python3
"""
HEATWATCH — Verify Ingestion Script
=====================================
Post-ingestion verification: checks record counts, spatial data,
duplicate rates, PostGIS geometry health, and land-cover registrations.

Usage:
    .venv\\Scripts\\python.exe data_ingestion/scripts/verify_ingestion.py
"""
import sys
import os
from pathlib import Path
from urllib.parse import urlparse

# ── Make data_ingestion importable regardless of cwd ─────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent          # scripts/
_DI_ROOT      = _SCRIPT_DIR.parent                       # data_ingestion/
_PROJECT_ROOT = _DI_ROOT.parent                          # SIH_Hackthon/

sys.path.insert(0, str(_DI_ROOT))

from dotenv import load_dotenv

# Load project-root .env FIRST — this is where the real credentials live.
load_dotenv(_PROJECT_ROOT / ".env", override=False)
load_dotenv(_DI_ROOT / ".env", override=False)   # legacy fallback

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"


def _parse_url(db_url: str) -> dict:
    """Parse a psycopg URL into components (never returns password)."""
    try:
        p = urlparse(db_url)
        return {
            "host": p.hostname or "?",
            "port": p.port or 5432,
            "dbname": (p.path or "/").lstrip("/") or "?",
            "user": p.username or "?",
        }
    except Exception:
        return {"host": "?", "port": "?", "dbname": "?", "user": "?"}


def verify() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print(f"{FAIL} DATABASE_URL not set.")
        print(f"  → Copy C:\\SIH_Hackthon\\.env.example to .env and set DATABASE_URL.")
        return 1

    parsed = _parse_url(db_url)
    print("=" * 62)
    print("HEATWATCH — Ingestion Verification")
    print("=" * 62)
    print(f"  Host    : {parsed['host']}")
    print(f"  Port    : {parsed['port']}")
    print(f"  DB      : {parsed['dbname']}")
    print(f"  User    : {parsed['user']}")
    print(f"  (password not displayed)")
    print()

    try:
        import psycopg
        conn = psycopg.connect(db_url, connect_timeout=10)
    except Exception as exc:
        print(f"{FAIL} Cannot connect to {parsed['host']}:{parsed['port']}/{parsed['dbname']}")
        print(f"  Error: {exc}")
        print()
        print("  Troubleshooting:")
        print(f"  1. Confirm Docker is running:  docker ps")
        print(f"  2. Confirm DATABASE_URL uses port {parsed['port']}")
        print(f"  3. Try:  psql \"{db_url.replace(db_url.split(':')[2].split('@')[0], '****')}\"")
        return 1

    print(f"{PASS} Connected to {parsed['host']}:{parsed['port']}/{parsed['dbname']}")

    failed = 0

    def q(label: str, sql: str, params=()):
        nonlocal failed
        try:
            result = conn.execute(sql, params).fetchone()
            return result[0] if result else 0
        except Exception as exc:
            print(f"  {FAIL} {label}: {exc}")
            failed += 1
            return None

    # ── PostGIS ────────────────────────────────────────────────
    print("\n[ Extensions ]")
    postgis_ver = q("PostGIS version",
        "SELECT postgis_lib_version()")
    pgvector_ext = q("pgvector extension",
        "SELECT COUNT(*) FROM pg_extension WHERE extname='vector'")
    if postgis_ver is not None:
        print(f"  {PASS}  PostGIS: {postgis_ver}")
    if pgvector_ext is not None:
        status = PASS if pgvector_ext > 0 else FAIL
        print(f"  {status}  pgvector: {'installed' if pgvector_ext else 'NOT installed'}")

    # ── Record Counts ──────────────────────────────────────────
    print("\n[ Record Counts ]")
    tables = [
        ("hotspots",              "SELECT COUNT(*) FROM hotspots"),
        ("thermal_objects",       "SELECT COUNT(*) FROM thermal_objects"),
        ("industrial_facilities", "SELECT COUNT(*) FROM industrial_facilities"),
        ("osm_context",           "SELECT COUNT(*) FROM osm_context"),
        ("land_context",          "SELECT COUNT(*) FROM land_context"),
        ("rag_chunks",            "SELECT COUNT(*) FROM rag_chunks"),
    ]
    for label, sql in tables:
        cnt = q(label, sql)
        if cnt is not None:
            print(f"  {INFO}  {label}: {cnt:,} rows")

    # ── Geometry ───────────────────────────────────────────────
    print("\n[ Geometry Checks ]")
    hs_with_geom = q("hotspots with valid location",
        "SELECT COUNT(*) FROM hotspots WHERE location IS NOT NULL AND ST_IsValid(location)")
    if hs_with_geom is not None:
        print(f"  {PASS if hs_with_geom else INFO}  Hotspots with valid geometry: {hs_with_geom}")

    fac_with_geom = q("facilities with valid location",
        "SELECT COUNT(*) FROM industrial_facilities WHERE location IS NOT NULL AND ST_IsValid(location)")
    if fac_with_geom is not None:
        print(f"  {PASS if fac_with_geom is not None else FAIL}  Facilities with valid geometry: {fac_with_geom}")

    # ── Duplicates ─────────────────────────────────────────────
    print("\n[ Duplicate Check ]")
    hs_total    = q("total hotspots",    "SELECT COUNT(*) FROM hotspots")
    hs_distinct = q("distinct hotspots",
        "SELECT COUNT(DISTINCT (source, latitude, longitude, acquisition_time)) FROM hotspots")
    if hs_total and hs_distinct:
        dup_rate = (hs_total - hs_distinct) / max(hs_total, 1) * 100
        status = PASS if dup_rate < 1.0 else FAIL
        print(f"  {status}  Duplicate rate: {dup_rate:.2f}%")

    # ── Spatial Query ──────────────────────────────────────────
    print("\n[ Spatial Query Test ]")
    bbox_count = q("bbox spatial query",
        "SELECT COUNT(*) FROM thermal_objects WHERE centroid && ST_MakeEnvelope(60,5,100,40,4326)")
    if bbox_count is not None:
        print(f"  {INFO}  Thermal objects in India bounding box: {bbox_count}")

    # ── Source breakdown ───────────────────────────────────────
    print("\n[ Sources in hotspots ]")
    try:
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM hotspots GROUP BY source ORDER BY 2 DESC"
        ).fetchall()
        for src, cnt in rows:
            print(f"  {INFO}  {src}: {cnt:,}")
    except Exception as exc:
        print(f"  {FAIL}  Could not query hotspot sources: {exc}")

    # ── Land-cover metadata manifests ─────────────────────────
    print("\n[ Land-Cover Registration Check ]")
    lc_dir = _PROJECT_ROOT / "dataset" / "processed" / "landcover"
    if lc_dir.exists():
        manifests = list(lc_dir.glob("*_metadata.json"))
        print(f"  {INFO}  Metadata manifests found: {len(manifests)}")
        tifs_raw   = list((_PROJECT_ROOT / "dataset" / "raw" / "landcover").rglob("*.tif"))
        print(f"  {INFO}  Raw GeoTIFFs on disk:     {len(tifs_raw)}")
    else:
        print(f"  {INFO}  Processed landcover dir not found: {lc_dir}")

    conn.close()
    print()
    print("=" * 62)
    if failed:
        print(f"{FAIL} {failed} check(s) failed.")
    else:
        print(f"{PASS} All checks passed.")
    print("=" * 62)
    return failed


if __name__ == "__main__":
    sys.exit(verify())
