"""
HEATWATCH Data Ingestion — Settings
=====================================
Reads all configuration from environment variables.
Load your .env file before importing this module:

    from dotenv import load_dotenv
    load_dotenv()

All path defaults assume the scripts are run from the
data_ingestion/ directory.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from project root (one level above data_ingestion/) ─
_HERE         = Path(__file__).resolve().parent.parent  # data_ingestion/
_PROJECT_ROOT = _HERE.parent                            # SIH_Hackthon/

# IMPORTANT: override=True so the project-root .env ALWAYS wins.
# Without this, a pre-existing DATABASE_URL in the shell environment
# (e.g. from Docker Compose or a previous session) silently takes
# precedence, causing connections to wrong hosts/ports.
load_dotenv(_PROJECT_ROOT / ".env", override=True)
load_dotenv(_HERE / ".env", override=False)  # legacy fallback only (never overrides root)


# ── Database ──────────────────────────────────────────────────
DATABASE_URL: str = os.environ["DATABASE_URL"]

# ── Dataset root paths ────────────────────────────────────────
# Default: resolve relative to project root, NOT the cwd.
_DATASET_ROOT = Path(os.getenv("DATASET_ROOT", str(_PROJECT_ROOT / "dataset"))).resolve()

FIRMS_RAW_PATH            = Path(os.getenv("FIRMS_RAW_PATH",            str(_DATASET_ROOT / "raw/firms"))).resolve()
HISTORICAL_FIRMS_RAW_PATH = Path(os.getenv("HISTORICAL_FIRMS_RAW_PATH", str(_DATASET_ROOT / "raw/historical_firms"))).resolve()
OSM_RAW_PATH              = Path(os.getenv("OSM_RAW_PATH",              str(_DATASET_ROOT / "raw/osm"))).resolve()
LANDCOVER_RAW_PATH        = Path(os.getenv("LANDCOVER_RAW_PATH",        str(_DATASET_ROOT / "raw/landcover"))).resolve()
INDUSTRIAL_RAW_PATH       = Path(os.getenv("INDUSTRIAL_RAW_PATH",       str(_DATASET_ROOT / "raw/industrial"))).resolve()
SATELLITE_RAW_PATH        = Path(os.getenv("SATELLITE_RAW_PATH",        str(_DATASET_ROOT / "raw/satellite"))).resolve()

PROCESSED_DATA_ROOT = Path(os.getenv("PROCESSED_DATA_ROOT", str(_DATASET_ROOT / "processed"))).resolve()
REJECTED_DATA_ROOT  = Path(os.getenv("REJECTED_DATA_ROOT",  str(_DATASET_ROOT / "rejected"))).resolve()

# ── Logging ───────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE:  str | None = os.getenv("LOG_FILE")

# ── CRS ───────────────────────────────────────────────────────
DEFAULT_CRS: str = os.getenv("DEFAULT_CRS", "EPSG:4326")

# ── Batch sizes ───────────────────────────────────────────────
FIRMS_BATCH_SIZE:            int = int(os.getenv("FIRMS_BATCH_SIZE",            "1000"))
HISTORICAL_FIRMS_CHUNK_SIZE: int = int(os.getenv("HISTORICAL_FIRMS_CHUNK_SIZE", "50000"))
INDUSTRIAL_BATCH_SIZE:       int = int(os.getenv("INDUSTRIAL_BATCH_SIZE",       "500"))

# ── Deduplication ─────────────────────────────────────────────
DEDUP_STRATEGY: str = os.getenv("DEDUP_STRATEGY", "STRICT").upper()

# ── Land-cover ────────────────────────────────────────────────
LANDCOVER_DATASET_ID:   str = os.getenv("LANDCOVER_DATASET_ID",   "ESA_WorldCover_2021")
LANDCOVER_RESOLUTION_M: int = int(os.getenv("LANDCOVER_RESOLUTION_M", "10"))

# ── FIRMS API (optional) ──────────────────────────────────────
FIRMS_MAP_KEY: str | None = os.getenv("FIRMS_MAP_KEY") or None


def validate_settings() -> list[str]:
    """Return list of configuration problems. Empty = all OK."""
    problems: list[str] = []
    if not DATABASE_URL:
        problems.append("DATABASE_URL is not set")
    if not FIRMS_RAW_PATH.parent.exists():
        problems.append(f"DATASET_ROOT parent does not exist: {FIRMS_RAW_PATH.parent}")
    return problems
