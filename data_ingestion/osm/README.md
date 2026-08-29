# HEATWATCH — OSM India Ingestion Module

Downloads and ingests the India OpenStreetMap dataset from **Geofabrik** into PostgreSQL.

**Parser**: `osmium` 4.x (native Python 3.14 wheel — no Overpass API dependency)

---

## Architecture

```
Geofabrik
  └── india-latest.osm.pbf  (~800 MB)
       │
       ├── osm/downloader.py     Streaming download with retry + .part file
       ├── osm/pbf_validator.py  PBF file validation (size, magic bytes, osmium)
       ├── osm/parser.py         osmium.SimpleHandler streaming parser
       ├── osm/database.py       osm_features table + batch upsert
       └── osm/pbf_pipeline.py   Orchestrator → checkpoint → manifest
            │
            └── PostgreSQL: osm_features table (EPSG:4326)
```

## Quickstart

```powershell
# Step 1 — Download + ingest (first run):
.venv\Scripts\python.exe data_ingestion\scripts\ingest_osm.py --download

# Step 2 — Verify:
.venv\Scripts\python.exe data_ingestion\scripts\verify_osm.py

# Re-run (idempotent — uses ON CONFLICT DO UPDATE):
.venv\Scripts\python.exe data_ingestion\scripts\ingest_osm.py --path "dataset\raw\osm\india\india-latest.osm.pbf"
```

## Feature Categories

| Feature type | OSM tags |
|---|---|
| `road` | `highway=motorway/trunk/primary/secondary/...` |
| `hospital` | `amenity=hospital/clinic`, `healthcare=hospital/clinic` |
| `fire_station` | `amenity=fire_station` |
| `school` | `amenity=school/college/university` |
| `park` | `leisure=park/garden`, `landuse=grass/forest/meadow`, `natural=wood/scrub` |
| `water` | `natural=water`, `waterway=river/stream/canal` |
| `building` | `building=*` |
| `transport` | `public_transport=*`, `railway=station/halt`, `highway=bus_stop` |

## Database Table

```sql
osm_features (
    id            BIGSERIAL PRIMARY KEY,
    osm_id        BIGINT NOT NULL,
    feature_type  TEXT NOT NULL,
    name          TEXT,
    subtype       TEXT,
    tags          JSONB,
    source        TEXT DEFAULT 'OpenStreetMap',
    geometry      GEOMETRY(Geometry, 4326),
    created_at    TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ,
    UNIQUE (osm_id, feature_type)    -- idempotency key
)
```

Indexes: spatial GIST, `feature_type`, `osm_id`.

## CLI Reference

```
--download          Download PBF from configured OSM_PBF_URL
--path PATH         Use existing PBF file
--batch-size INT    DB batch size (default: OSM_BATCH_SIZE from .env)
--skip-ingest       Download only, skip DB ingestion
--skip-validation   Skip PBF file validation
```

## Environment Variables

All set in `C:\SIH_Hackthon\.env`:

```env
OSM_PBF_URL=https://download.geofabrik.de/asia/india-latest.osm.pbf
OSM_PBF_FILENAME=india-latest.osm.pbf
OSM_DATASET_ROOT=...dataset\raw\osm\india
OSM_PROCESSED_ROOT=...dataset\processed\osm
OSM_REQUEST_TIMEOUT=120
OSM_MAX_RETRIES=3
OSM_BATCH_SIZE=5000
```

## Notes

- The India PBF (~800 MB) is gitignored.
- Pipeline is **idempotent**: re-running does not duplicate rows.
- **No Overpass API dependency** — all data comes from the Geofabrik PBF.
- `osmium.NodeLocationsForWays` resolves way node coordinates in-memory.
- Relations are stored as metadata-only (no geometry) due to multipolygon complexity.
