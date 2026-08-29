"""
HEATWATCH — FIRMS API Configuration
======================================
All FIRMS API settings loaded from the project-root .env.
No secrets or credentials stored here.

NASA FIRMS API Docs:
  https://firms.modaps.eosdis.nasa.gov/api/

Selected product: VIIRS_NOAA20_NRT (VIIRS NOAA-20, Near Real-Time)
Reason:
  - Highest resolution (375m pixels, vs 1km for MODIS)
  - Near-real-time (NRT) — data available within 3 hours
  - NOAA-20 (J1) is the most reliable currently operational VIIRS platform
  - Maps to hotspots.source = 'VIIRS_NOAA20' (DB CHECK constraint)

API endpoint:
  https://firms.modaps.eosdis.nasa.gov/api/country/csv/{key}/{source}/{country}/{days}

Supported sources:
  VIIRS_NOAA20_NRT    — VIIRS NOAA-20 Near Real-Time
  VIIRS_SNPP_NRT      — VIIRS Suomi NPP Near Real-Time
  MODIS_NRT           — MODIS Near Real-Time
  VIIRS_NOAA20_SP     — VIIRS NOAA-20 Standard Processing
  VIIRS_SNPP_SP       — VIIRS Suomi NPP Standard Processing
  MODIS_SP            — MODIS Standard Processing

API limits:
  - Maximum 10 days per request
  - Country-level filtering supported (IND = India)
  - No pagination needed (country + 10 days is manageable)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Locate project root ────────────────────────────────────────
_HERE         = Path(__file__).resolve().parent       # firms/
_DI_ROOT      = _HERE.parent                          # data_ingestion/
PROJECT_ROOT  = _DI_ROOT.parent                       # SIH_Hackthon/

load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(_DI_ROOT / ".env", override=False)

# ── FIRMS API ──────────────────────────────────────────────────
FIRMS_MAP_KEY: str | None = os.getenv("FIRMS_MAP_KEY") or os.getenv("NASA_FIRMS_API_KEY") or None

FIRMS_BASE_URL: str = os.getenv(
    "FIRMS_BASE_URL",
    "https://firms.modaps.eosdis.nasa.gov/api",
)

# Default product: VIIRS NOAA-20 Near Real-Time
FIRMS_SOURCE: str = os.getenv("FIRMS_SOURCE", "VIIRS_NOAA20_NRT")

# Country code: IND = India (ISO 3166-1 alpha-3)
FIRMS_COUNTRY: str = os.getenv("FIRMS_COUNTRY", "IND")

# Default number of days to fetch per API request (max=10 per API rules)
FIRMS_DAYS: int = int(os.getenv("FIRMS_DAYS", "1"))

# HTTP settings
FIRMS_REQUEST_TIMEOUT: int = int(os.getenv("FIRMS_REQUEST_TIMEOUT", "120"))
FIRMS_MAX_RETRIES: int = int(os.getenv("FIRMS_MAX_RETRIES", "3"))

# ── Raw data storage ───────────────────────────────────────────
_DATASET_ROOT = Path(os.getenv(
    "DATASET_ROOT",
    str(PROJECT_ROOT / "dataset")
)).resolve()

FIRMS_RAW_ROOT: Path = Path(os.getenv(
    "FIRMS_RAW_PATH",
    str(_DATASET_ROOT / "raw" / "firms")
)).resolve()

FIRMS_PROCESSED_ROOT: Path = Path(os.getenv(
    "PROCESSED_DATA_ROOT",
    str(_DATASET_ROOT / "processed")
)).resolve() / "firms"

# ── India bounding box (fallback for non-country-API filtering) ─
INDIA_BBOX = {
    "min_lon": 68.0,
    "max_lon": 98.0,
    "min_lat":  6.0,
    "max_lat": 37.5,
}

# ── Supported FIRMS products (for validation) ──────────────────
SUPPORTED_SOURCES = frozenset({
    "VIIRS_NOAA20_NRT",
    "VIIRS_SNPP_NRT",
    "MODIS_NRT",
    "VIIRS_NOAA20_SP",
    "VIIRS_SNPP_SP",
    "MODIS_SP",
})
