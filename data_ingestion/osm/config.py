"""
HEATWATCH — OSM Ingestion Configuration
==========================================
All settings are read from the project-root .env file.
No credentials or secrets are stored here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Locate project root and load .env ─────────────────────────
_HERE         = Path(__file__).resolve().parent          # osm/
_DI_ROOT      = _HERE.parent                             # data_ingestion/
PROJECT_ROOT  = _DI_ROOT.parent                          # SIH_Hackthon/

load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(_DI_ROOT / ".env", override=False)

# ── Dataset paths ──────────────────────────────────────────────
OSM_DATASET_ROOT: Path = Path(
    os.getenv("OSM_DATASET_ROOT", str(PROJECT_ROOT / "dataset" / "raw" / "osm" / "india"))
).resolve()

OSM_PROCESSED_ROOT: Path = Path(
    os.getenv("OSM_PROCESSED_ROOT", str(PROJECT_ROOT / "dataset" / "processed" / "osm"))
).resolve()

# ── Download configuration ─────────────────────────────────────
OSM_PBF_URL: str = os.getenv(
    "OSM_PBF_URL",
    "https://download.geofabrik.de/asia/india-latest.osm.pbf",
)

OSM_PBF_FILENAME: str = os.getenv("OSM_PBF_FILENAME", "india-latest.osm.pbf")

OSM_REQUEST_TIMEOUT: int = int(os.getenv("OSM_REQUEST_TIMEOUT", "120"))

OSM_MAX_RETRIES: int = int(os.getenv("OSM_MAX_RETRIES", "3"))

# ── Processing ─────────────────────────────────────────────────
OSM_BATCH_SIZE: int = int(os.getenv("OSM_BATCH_SIZE", "5000"))

# ── Derived paths ──────────────────────────────────────────────
OSM_PBF_PATH:       Path = OSM_DATASET_ROOT   / OSM_PBF_FILENAME
OSM_MANIFEST_PATH:  Path = OSM_PROCESSED_ROOT / "manifest.json"
OSM_CHECKPOINT_PATH: Path = OSM_PROCESSED_ROOT / "checkpoint.json"
OSM_REPORT_PATH:    Path = OSM_PROCESSED_ROOT / "ingestion_report.json"

# ── Feature categories ─────────────────────────────────────────
FEATURE_TYPES = {
    "road", "hospital", "fire_station", "school",
    "park", "water", "building", "transport",
}

# ── Highway tags to extract ────────────────────────────────────
ROAD_HIGHWAY_CLASSES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "service", "unclassified", "living_street",
    "pedestrian", "cycleway", "footway", "path",
    "motorway_link", "trunk_link", "primary_link",
    "secondary_link", "tertiary_link",
}
