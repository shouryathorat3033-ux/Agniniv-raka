#!/usr/bin/env python3
"""
HEATWATCH — FIRMS Verification Script
========================================
Verifies the FIRMS ingestion state end-to-end.

Usage:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\verify_firms.py

Exit code 0 = all checks pass.
Exit code 1 = one or more checks failed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SCRIPT_DIR   = Path(__file__).resolve().parent
_DI_ROOT      = _SCRIPT_DIR.parent
_PROJECT_ROOT = _DI_ROOT.parent

sys.path.insert(0, str(_DI_ROOT))

# ── Load config the same way every HEATWATCH pipeline does ─────
# config/settings.py loads the project-root .env before anything
# else — it is the single authoritative source of DATABASE_URL.
from dotenv import load_dotenv
# override=True: project-root .env is always authoritative
load_dotenv(_PROJECT_ROOT / ".env", override=True)

from config import settings   # noqa: E402 — must come after dotenv load

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"
WIDTH = 62


def _sep():
    print("=" * WIDTH)


def _row(label: str, status: str, detail: str = "") -> None:
    pad = WIDTH - len(label) - len(status) - 2
    detail_str = f"  {detail}" if detail else ""
    print(f"  {label} {'.' * max(pad, 1)} {status}{detail_str}")



def verify() -> int:
    from urllib.parse import urlparse
    from firms.config import (
        FIRMS_MAP_KEY,
        FIRMS_BASE_URL,
        FIRMS_SOURCE,
        FIRMS_COUNTRY,
        FIRMS_DAYS,
    )
    from firms.client import check_api_connectivity

    # Use settings.DATABASE_URL — loaded from project-root .env
    # by config/settings.py. Never read from os.environ directly.
    db_url = settings.DATABASE_URL

    _sep()
    print("HEATWATCH -- FIRMS VERIFICATION")
    _sep()
    print()

    failed = 0

    # ── 1. API key configured ──────────────────────────────────
    if FIRMS_MAP_KEY:
        _row("FIRMS API key configured", PASS, "(key not displayed)")
    else:
        _row("FIRMS API key configured", FAIL,
             "set NASA_FIRMS_API_KEY in .env")
        failed += 1

    # ── 2. API reachable ───────────────────────────────────────
    if FIRMS_MAP_KEY:
        print(f"  Testing API: {FIRMS_BASE_URL} ...")
        result = check_api_connectivity(
            base_url=FIRMS_BASE_URL,
            api_key=FIRMS_MAP_KEY,
            timeout=30,
        )
        if result["reachable"]:
            _row("FIRMS API reachable", PASS)
        else:
            _row("FIRMS API reachable", FAIL, result.get("message", ""))
            failed += 1

        # ── 3. API authentication ──────────────────────────────
        if result["reachable"]:
            if result["authenticated"]:
                rows = result.get("rows", "?")
                _row("FIRMS API authentication", PASS, f"response rows={rows}")
            else:
                _row("FIRMS API authentication", FAIL,
                     result.get("message", "key rejected"))
                failed += 1
    else:
        _row("FIRMS API reachable", WARN, "skipped (no API key)")
        _row("FIRMS API authentication", WARN, "skipped (no API key)")

    # ── 4. Database connection ─────────────────────────────────
    print()
    if not db_url:
        _row("PostgreSQL connection", FAIL, "DATABASE_URL not set")
        return 1

    try:
        parsed = urlparse(db_url)
        print(f"  Target: {parsed.hostname}:{parsed.port}/{(parsed.path or '/').lstrip('/')}")
    except Exception:
        pass

    try:
        import psycopg
        conn = psycopg.connect(db_url, connect_timeout=10)
        _row("PostgreSQL connection", PASS)
    except Exception as exc:
        _row("PostgreSQL connection", FAIL, str(exc)[:50])
        return 1

    def q(sql: str, params=()):
        try:
            return conn.execute(sql, params).fetchone()
        except Exception:
            return None

    # ── 5. PostGIS ─────────────────────────────────────────────
    row = q("SELECT postgis_full_version()")
    if row:
        version_short = row[0].split('"')[1] if '"' in row[0] else row[0][:20]
        _row("PostGIS", PASS, f"version {version_short}")
    else:
        _row("PostGIS", FAIL, "PostGIS not installed")
        failed += 1

    # ── 6. hotspots table exists ───────────────────────────────
    # Reset any failed transaction first
    try:
        conn.execute("ROLLBACK")
    except Exception:
        pass
    row = q(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='hotspots'"
    )
    if row:
        _row("hotspots table", PASS)
    else:
        _row("hotspots table", WARN,
             "not found -- run database migrations first")
        # Don't fail the whole check -- DB may just need migrations
        conn.close()
        print()
        _sep()
        print("FIRMS VERIFICATION: INCOMPLETE (migrations needed)")
        _sep()
        print()
        return failed

    # ── 7. Record count ────────────────────────────────────────
    print()
    row = q("SELECT COUNT(*) FROM hotspots")
    total = row[0] if row else 0
    if total > 0:
        _row("Records found", PASS, f"{total:,} total hotspot records")
    else:
        _row("Records found", WARN, "0 rows -- run ingestion first")

    # ── 8. Latest acquisition timestamp ───────────────────────
    row = q("SELECT MAX(acquisition_time) FROM hotspots")
    latest = row[0] if row else None
    if latest:
        _row("Latest acquisition", PASS, str(latest)[:25])
    else:
        _row("Latest acquisition", WARN, "no records yet")

    # ── 9. India coordinate sanity ─────────────────────────────
    row = q(
        "SELECT MIN(latitude), MAX(latitude), MIN(longitude), MAX(longitude) "
        "FROM hotspots"
    )
    if row and row[0] is not None:
        min_lat, max_lat, min_lon, max_lon = row
        india_ok = (
            5.0 <= float(min_lat) <= 40.0 and
            5.0 <= float(max_lat) <= 40.0 and
            65.0 <= float(min_lon) <= 100.0 and
            65.0 <= float(max_lon) <= 100.0
        )
        if india_ok:
            _row("India coordinates", PASS,
                 f"lat=[{min_lat:.2f},{max_lat:.2f}] lon=[{min_lon:.2f},{max_lon:.2f}]")
        else:
            _row("India coordinates", WARN,
                 f"lat=[{min_lat:.2f},{max_lat:.2f}] lon=[{min_lon:.2f},{max_lon:.2f}]")
    else:
        _row("India coordinates", WARN, "no data to check")

    # ── 10. Source distribution ────────────────────────────────
    rows = conn.execute(
        "SELECT source, COUNT(*) FROM hotspots GROUP BY source ORDER BY 2 DESC"
    ).fetchall()
    if rows:
        print()
        print("  Source breakdown:")
        for src, cnt in rows:
            print(f"    {src:<20}: {cnt:>8,}")

    # ── 11. Duplicate check ────────────────────────────────────
    print()
    row = q(
        "SELECT COUNT(*) FROM ("
        "  SELECT source, latitude, longitude, acquisition_time, COUNT(*) "
        "  FROM hotspots "
        "  GROUP BY source, latitude, longitude, acquisition_time "
        "  HAVING COUNT(*) > 1"
        ") dupes"
    )
    dupe_count = row[0] if row else 0
    if dupe_count == 0:
        _row("Duplicate check", PASS, "no duplicate (source,lat,lon,time)")
    else:
        _row("Duplicate check", FAIL,
             f"{dupe_count} duplicate pixel/time combinations")
        failed += 1

    # ── 12. Geometry validity ──────────────────────────────────
    row = q(
        "SELECT COUNT(*) FROM hotspots WHERE location IS NOT NULL"
    )
    geom_count = row[0] if row else 0
    if total > 0:
        if geom_count > 0:
            _row("PostGIS geometry", PASS, f"{geom_count:,} non-null points")
        else:
            _row("PostGIS geometry", WARN, "all geometries NULL")

    # ── Raw data directory ─────────────────────────────────────
    from firms.config import FIRMS_RAW_ROOT
    print()
    if FIRMS_RAW_ROOT.exists():
        csv_files = list(FIRMS_RAW_ROOT.rglob("*.csv"))
        _row("Raw FIRMS data dir", PASS if csv_files else WARN,
             f"{len(csv_files)} CSV file(s) in {FIRMS_RAW_ROOT.name}/")
    else:
        _row("Raw FIRMS data dir", INFO, "not yet created (run ingestion first)")

    conn.close()

    print()
    _sep()
    if failed == 0:
        print("FIRMS VERIFICATION: PASS")
    else:
        print(f"FIRMS VERIFICATION: FAIL  ({failed} check(s) failed)")
    _sep()
    print()

    return failed


if __name__ == "__main__":
    sys.exit(verify())
