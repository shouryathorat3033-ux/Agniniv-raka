# HEATWATCH — Data Ingestion Module

**ETL pipeline for loading external datasets into the HEATWATCH PostgreSQL/PostGIS database.**

---

## Purpose

This module extracts, validates, normalizes, transforms, and loads data from **six external sources** into the existing HEATWATCH database.

**This module ONLY:**
- Reads external dataset files
- Validates records
- Normalizes data formats
- Loads data into existing PostgreSQL tables

**This module does NOT:**
- Train ML models
- Classify fire sources
- Detect anomalies
- Create thermal clusters (ST-DBSCAN)
- Expose REST API endpoints
- Render frontend UI
- Create or modify database schema

---

## The Six Datasets

| # | Dataset | Target Table(s) | Format |
|---|---|---|---|
| 1 | NASA FIRMS Current | `hotspots` | CSV |
| 2 | NASA FIRMS Historical | `hotspots` | CSV (chunked) |
| 3 | OpenStreetMap | `industrial_facilities`, `osm_context` | GeoJSON, GeoPackage |
| 4 | Land Cover (ESA WorldCover) | `land_context` | GeoTIFF |
| 5 | Industrial Facility Database | `industrial_facilities` | CSV, GeoJSON, GeoPackage |
| 6 | Sentinel-2 Imagery | manifests only (no DB table yet) | SAFE, JSON |

---

## Raw Dataset Locations

Place downloaded datasets here:

```
dataset/
├── raw/
│   ├── firms/              ← FIRMS CSV files
│   ├── historical_firms/   ← Historical FIRMS CSV archives
│   ├── osm/                ← OSM GeoJSON/GeoPackage extracts
│   ├── landcover/          ← ESA WorldCover GeoTIFF tiles
│   ├── industrial/         ← GEM/GPPD/EPA facility datasets
│   └── satellite/          ← Sentinel-2 SAFE directories
```

Do NOT commit large dataset files to Git (see `.gitignore`).

---

## Environment Setup

### 1. Create the virtual environment

**Linux/macOS/WSL:**
```bash
cd data_ingestion
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows PowerShell:**
```powershell
cd data_ingestion
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL at minimum
```

### 3. Ensure the database is running

```bash
# Start the database container (from database/ directory)
cd ../database
docker compose --env-file .env up -d
# Run migrations
source .env
bash scripts/migrate.sh
```

---

## Check Environment

Before any ingestion:
```bash
python scripts/check_environment.py
```

This verifies Python packages, environment variables, database connectivity, PostGIS, and all required tables.

---

## Validate a Dataset (Without Loading)

```bash
python scripts/validate_dataset.py --dataset firms      --path ../dataset/raw/firms/file.csv
python scripts/validate_dataset.py --dataset osm        --path ../dataset/raw/osm/extract.geojson
python scripts/validate_dataset.py --dataset landcover  --path ../dataset/raw/landcover/file.tif
python scripts/validate_dataset.py --dataset industrial --path ../dataset/raw/industrial/gem.csv
python scripts/validate_dataset.py --dataset satellite  --path ../dataset/raw/satellite/
```

---

## Ingest Each Dataset

### 1. Current FIRMS
```bash
python scripts/ingest_firms.py --path ../dataset/raw/firms/DL_FIRE_J1V-C2_20240615.csv
```

### 2. Historical FIRMS
```bash
# Entire directory (chunked):
python scripts/ingest_historical_firms.py --path ../dataset/raw/historical_firms/

# Single file:
python scripts/ingest_historical_firms.py --path ../dataset/raw/historical_firms/archive_2020.csv
```

### 3. OSM
```bash
python scripts/ingest_osm.py --path ../dataset/raw/osm/
```

### 4. Land Cover (registration only)
```bash
python scripts/ingest_landcover.py --path ../dataset/raw/landcover/ESA_WorldCover_v200.tif
```

### 5. Industrial Facilities
```bash
python scripts/ingest_industrial.py --path ../dataset/raw/industrial/gem_2024.csv \
    --source GEM_2024 --dataset-id GEM_2024_Q1
```

### 6. Satellite Metadata
```bash
python scripts/ingest_satellite_metadata.py --path ../dataset/raw/satellite/
```

### All at once (recommended order)
```bash
python scripts/ingest_all.py
```

---

## Verify After Ingestion

```bash
python scripts/verify_ingestion.py
```

---

## Recommended Ingestion Order

1. **Industrial facilities** — no dependencies
2. **OSM** — no dependencies
3. **Historical FIRMS** → `hotspots`
4. **Current FIRMS** → `hotspots`
5. **Land cover registration** — validates raster for later use
6. **Satellite metadata** — catalogues scenes, no DB write

---

## Rejected Records

Records that fail validation are written to:
```
dataset/rejected/<dataset>/
```
Each file contains the original row + rejection reason. Raw data is never deleted.

---

## Duplicate Prevention

| Dataset | Strategy |
|---|---|
| FIRMS hotspots | ON CONFLICT ON CONSTRAINT `uq_hotspot_pixel_time` DO NOTHING |
| Industrial facilities | Application-level check: source + source_reference |
| OSM features | ON CONFLICT DO NOTHING; UNIQUE(thermal_object_id, osm_type, osm_id) |
| Land context | ON CONFLICT ON CONSTRAINT `uq_land_context_source` DO NOTHING |

All pipelines are **idempotent** — safe to re-run on the same data.

---

## Data That Is NOT Stored in PostgreSQL

| Data | Storage |
|---|---|
| Raw GeoTIFF rasters | Local filesystem only |
| Sentinel-2 imagery | Local filesystem only |
| Large OSM extracts | Local filesystem only |
| ML model binary weights | Object storage (S3/GCS) |

---

## Running Tests

```bash
# Unit tests only (no database required)
pytest tests/ -m "not integration" -v

# Integration tests (requires DATABASE_URL)
pytest tests/ -m integration -v

# All tests
pytest tests/ -v
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `DATABASE_URL not set` | Copy `.env.example` to `.env` and set credentials |
| `PostGIS not installed` | Run `database/scripts/migrate.sh` first |
| `Table missing` | Run all database migrations (000–009) |
| `FIRMS: missing required columns` | Check CSV format; FIRMS products vary by satellite |
| `OSM: CRS is None` | File will be assumed EPSG:4326; verify manually |
| `Landcover: CRS not geographic` | Reproject raster to EPSG:4326 before running lookup |
| `psycopg: SSL error on Windows` | Use `pip install psycopg[binary]` not `psycopg[c]` |
