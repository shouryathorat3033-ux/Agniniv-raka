#!/usr/bin/env python3
"""
HEATWATCH — Environment Check
==============================
Verifies all prerequisites before running any ingestion pipeline.

Usage:
    python scripts/check_environment.py
"""
import sys
import os
from pathlib import Path

# ── Bootstrap path so we can import from data_ingestion/ ──────
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import importlib

REQUIRED_PACKAGES = [
    "psycopg", "pandas", "geopandas", "shapely",
    "rasterio", "pyproj", "structlog", "dotenv",
    "click", "pydantic", "requests",
]

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "FIRMS_RAW_PATH",
    "HISTORICAL_FIRMS_RAW_PATH",
    "OSM_RAW_PATH",
    "LANDCOVER_RAW_PATH",
    "INDUSTRIAL_RAW_PATH",
    "SATELLITE_RAW_PATH",
]

REQUIRED_TABLES = [
    "hotspots", "thermal_objects", "thermal_object_observations",
    "industrial_facilities", "osm_context", "land_context",
    "historical_profiles", "feature_vectors",
]

PASS = "✔"
FAIL = "✘"
WARN = "⚠"


def check_packages() -> bool:
    print("\n[ Python Packages ]")
    ok = True
    for pkg in REQUIRED_PACKAGES:
        import_name = pkg if pkg != "dotenv" else "dotenv"
        try:
            importlib.import_module(import_name)
            print(f"  {PASS}  {pkg}")
        except ImportError:
            print(f"  {FAIL}  {pkg}  — NOT INSTALLED")
            ok = False
    return ok


def check_env_vars() -> bool:
    print("\n[ Environment Variables ]")
    ok = True
    for var in REQUIRED_ENV_VARS:
        val = os.environ.get(var, "")
        if val:
            print(f"  {PASS}  {var} = {val[:60]}")
        else:
            if var == "DATABASE_URL":
                print(f"  {FAIL}  {var}  — NOT SET (required)")
                ok = False
            else:
                print(f"  {WARN}  {var}  — not set (using default)")
    return ok


def check_database() -> bool:
    print("\n[ Database Connection ]")
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print(f"  {FAIL}  DATABASE_URL not set — skipping DB checks")
        return False

    try:
        import psycopg
        conn = psycopg.connect(db_url, connect_timeout=5)
        print(f"  {PASS}  PostgreSQL connection successful")
    except Exception as exc:
        print(f"  {FAIL}  Cannot connect to PostgreSQL: {exc}")
        return False

    # PostGIS
    try:
        ver = conn.execute("SELECT postgis_full_version()").fetchone()[0]
        print(f"  {PASS}  PostGIS: {ver[:60]}")
    except Exception:
        print(f"  {FAIL}  PostGIS is NOT installed on this server")
        conn.close()
        return False

    # Tables
    print("\n[ Required Tables ]")
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%s)
        """,
        (REQUIRED_TABLES,),
    ).fetchall()
    found = {r[0] for r in rows}
    all_found = True
    for tbl in REQUIRED_TABLES:
        if tbl in found:
            print(f"  {PASS}  {tbl}")
        else:
            print(f"  {FAIL}  {tbl}  — MISSING (run database migrations)")
            all_found = False

    conn.close()
    return all_found


def main() -> int:
    print("=" * 60)
    print("  HEATWATCH — Environment Check")
    print("=" * 60)

    pkg_ok = check_packages()
    env_ok = check_env_vars()
    db_ok  = check_database()

    print("\n" + "=" * 60)
    if pkg_ok and env_ok and db_ok:
        print(f"  {PASS}  All checks passed. Ready to ingest data.")
        return 0
    else:
        print(f"  {FAIL}  One or more checks failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
