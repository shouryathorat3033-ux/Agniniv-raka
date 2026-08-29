#!/usr/bin/env python3
"""
HEATWATCH — Verify Ingestion Script
=====================================
Post-ingestion verification: checks record counts, spatial data,
duplicate rates, and PostGIS geometry health.

Usage:
    python scripts/verify_ingestion.py
"""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

PASS = "✔"
FAIL = "✘"
INFO = "ℹ"


def verify() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print(f"{FAIL} DATABASE_URL not set")
        return 1

    try:
        import psycopg
        conn = psycopg.connect(db_url, connect_timeout=5)
    except Exception as exc:
        print(f"{FAIL} Cannot connect: {exc}")
        return 1

    failed = 0

    def q(label: str, sql: str, params=()) -> any:
        nonlocal failed
        try:
            result = conn.execute(sql, params).fetchone()
            return result[0] if result else 0
        except Exception as exc:
            print(f"  {FAIL} {label}: {exc}")
            failed += 1
            return None

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

    print("\n[ Geometry Checks ]")
    hs_with_geom = q("hotspots with valid location",
        "SELECT COUNT(*) FROM hotspots WHERE location IS NOT NULL AND ST_IsValid(location)")
    print(f"  {PASS if hs_with_geom else FAIL}  Hotspots with valid geometry: {hs_with_geom}")

    fac_with_geom = q("facilities with valid location",
        "SELECT COUNT(*) FROM industrial_facilities WHERE location IS NOT NULL AND ST_IsValid(location)")
    print(f"  {PASS if fac_with_geom is not None else FAIL}  Facilities with valid geometry: {fac_with_geom}")

    print("\n[ Duplicate Check ]")
    hs_total = q("total hotspots", "SELECT COUNT(*) FROM hotspots")
    hs_distinct = q("distinct hotspots", "SELECT COUNT(DISTINCT (source, latitude, longitude, acquisition_time)) FROM hotspots")
    if hs_total and hs_distinct:
        dup_rate = (hs_total - hs_distinct) / max(hs_total, 1) * 100
        status = PASS if dup_rate < 1.0 else FAIL
        print(f"  {status}  Duplicate rate: {dup_rate:.2f}%")

    print("\n[ Spatial Query Test ]")
    bbox_count = q("bbox spatial query",
        "SELECT COUNT(*) FROM thermal_objects WHERE centroid && ST_MakeEnvelope(60,5,100,40,4326)")
    print(f"  {INFO}  Thermal objects in India bounding box: {bbox_count}")

    print("\n[ Sources in hotspots ]")
    rows = conn.execute("SELECT source, COUNT(*) FROM hotspots GROUP BY source ORDER BY 2 DESC").fetchall()
    for src, cnt in rows:
        print(f"  {INFO}  {src}: {cnt:,}")

    conn.close()
    print(f"\n{'All checks passed.' if not failed else f'{failed} check(s) failed.'}")
    return failed


if __name__ == "__main__":
    sys.exit(verify())
