# HEATWATCH — Data Ingestion Architecture

## Overview

```
External Datasets (6 sources)
          ↓
    data_ingestion/
    ├── config/           ← settings + dataset constants
    ├── common/           ← shared db, geometry, timestamps, validators
    ├── firms/            ← NASA FIRMS current observations
    ├── historical_firms/ ← NASA FIRMS multi-year archives
    ├── osm/              ← OpenStreetMap extracts
    ├── landcover/        ← ESA WorldCover raster
    ├── industrial/       ← Industrial facility databases
    └── satellite/        ← Sentinel-2 scene metadata
          ↓
    PostgreSQL / PostGIS
    (existing heatwatch database)
```

---

## Pipeline Pattern

Every data source follows the same 6-step pattern:

```
1. READ       — Open and parse the source file (no validation)
2. VALIDATE   — Row-level checks; split valid/rejected DataFrames
3. NORMALIZE  — Map raw fields to DB column names and types
4. TRANSFORM  — Post-normalization filters (source whitelist, type enums)
5. LOAD       — Bulk parameterized INSERT with ON CONFLICT DO NOTHING
6. RECORD     — Write IngestionResult manifest to dataset/processed/
```

Each step is implemented in its own module file:

```
<source>/
  reader.py       → Step 1: READ
  validator.py    → Step 2: VALIDATE
  normalizer.py   → Step 3: NORMALIZE
  transformer.py  → Step 4: TRANSFORM
  loader.py       → Step 5: LOAD
  pipeline.py     → Orchestrator (calls steps 1–6)
```

---

## Common Library (`common/`)

| Module | Purpose |
|---|---|
| `db.py` | psycopg3 connection pool, `transaction()` context manager |
| `geometry.py` | WKT helpers, coordinate validation (X=lon, Y=lat) |
| `timestamps.py` | FIRMS datetime parsing, UTC normalization |
| `validators.py` | Row-level field validators, returns error lists |
| `deduplication.py` | Fingerprint functions for FIRMS, OSM, industrial |
| `provenance.py` | `IngestionResult` dataclass, manifest output |
| `exceptions.py` | Typed exception hierarchy |
| `logging_config.py` | structlog JSON logging setup |

---

## Database Rules

1. **Never creates or modifies schema** — all tables pre-exist
2. **Parameterized queries only** — no string interpolation
3. **Explicit transactions** — all inserts go through `with transaction() as conn:`
4. **ON CONFLICT DO NOTHING** — idempotent inserts
5. **PostGIS geometry** — `ST_SetSRID(ST_MakePoint(lon, lat), 4326)` — X first

---

## Dataset Dependency Graph

```
No dependencies
  ├── industrial_facilities
  └── OSM → industrial_facilities

Produce hotspots rows
  ├── Historical FIRMS
  └── Current FIRMS

Requires thermal_object_id (from analytics pipeline)
  ├── land_context
  └── osm_context

No DB write (no table yet)
  └── satellite scene metadata
```

---

## Rejected Record Traceability

| Rejection Stage | Storage Location |
|---|---|
| FIRMS validation | `dataset/rejected/firms/<file>_rejected.csv` |
| FIRMS source mapping | `dataset/rejected/firms/firms_invalid_source_*.jsonl` |
| Historical FIRMS | `dataset/rejected/historical_firms/*.csv` |
| OSM geometry | `dataset/rejected/osm/<file>_rejected.geojson` |
| OSM industrial filter | `dataset/rejected/osm/industrial_rejected.jsonl` |
| Industrial geometry | `dataset/rejected/industrial/<file>_rejected.geojson` |
| Industrial filter | `dataset/rejected/industrial/industrial_rejected.jsonl` |
| Satellite metadata | `dataset/rejected/satellite/<file>_rejected.json` |

Every rejected record retains its original raw data plus a `rejection_reason` field.

---

## Idempotency

Re-running any pipeline on the same source file is safe:

- **FIRMS**: `ON CONFLICT ON CONSTRAINT uq_hotspot_pixel_time DO NOTHING`
- **Industrial**: App-level dedup → `source + source_reference` checked before insert
- **Land context**: `ON CONFLICT ON CONSTRAINT uq_land_context_source DO NOTHING`
- **OSM context**: `UNIQUE(thermal_object_id, osm_type, osm_id)` → DO NOTHING

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✔ | — | PostgreSQL connection string |
| `FIRMS_RAW_PATH` | — | `../dataset/raw/firms` | FIRMS CSV directory |
| `HISTORICAL_FIRMS_RAW_PATH` | — | `../dataset/raw/historical_firms` | Historical FIRMS directory |
| `OSM_RAW_PATH` | — | `../dataset/raw/osm` | OSM extract directory |
| `LANDCOVER_RAW_PATH` | — | `../dataset/raw/landcover` | GeoTIFF directory |
| `INDUSTRIAL_RAW_PATH` | — | `../dataset/raw/industrial` | Industrial facility files |
| `SATELLITE_RAW_PATH` | — | `../dataset/raw/satellite` | Satellite SAFE/JSON files |
| `FIRMS_BATCH_SIZE` | — | `1000` | DB rows per transaction |
| `HISTORICAL_FIRMS_CHUNK_SIZE` | — | `50000` | Rows per pandas chunk |
| `LANDCOVER_DATASET_ID` | — | `ESA_WorldCover_2021` | Source name for land_context |
| `LANDCOVER_RESOLUTION_M` | — | `10` | Resolution in metres |
| `DEDUP_STRATEGY` | — | `STRICT` | STRICT (skip) or UPDATE |
| `LOG_LEVEL` | — | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `LOG_FILE` | — | None | Path to log file (optional) |

---

## File Flow Diagram

```
dataset/raw/<source>/*.csv (or .geojson, .tif, .SAFE)
          ↓ READ
          ↓ VALIDATE ─────────────→ dataset/rejected/<source>/
          ↓ NORMALIZE
          ↓ TRANSFORM
          ↓ LOAD ─────────────────→ PostgreSQL tables
          ↓ RECORD
dataset/processed/<source>/ingestion_*.json  (manifest)
```

---

## Extending the Module

### Adding a new dataset source

1. Create `data_ingestion/<new_source>/` directory
2. Add `__init__.py`, `reader.py`, `validator.py`, `normalizer.py`, `transformer.py`, `loader.py`, `pipeline.py`
3. Add raw/processed/rejected directories: `dataset/raw/<new_source>/` etc.
4. Add a CLI script: `scripts/ingest_<new_source>.py`
5. Register in `scripts/ingest_all.py`
6. Write unit tests in `tests/test_<new_source>.py`
7. Document column mapping in `docs/data_mapping.md`

### Adding a new satellite_scenes DB table

See: `satellite/metadata_transformer.py` — contains the recommended `CREATE TABLE` migration template.
After adding the migration, update `satellite/loader.py` to perform real inserts.
