# HEATWATCH — NASA FIRMS Ingestion Module

Downloads and ingests NASA FIRMS active fire / thermal anomaly data for **India** from the FIRMS API into PostgreSQL/PostGIS.

---

## Selected Product

| Field | Value |
|---|---|
| **Product** | VIIRS NOAA-20 Near Real-Time (`VIIRS_NOAA20_NRT`) |
| **Satellite** | NOAA-20 (formerly JPSS-1) |
| **Instrument** | VIIRS (Visible Infrared Imaging Radiometer Suite) |
| **Spatial resolution** | 375 m |
| **Temporal latency** | ~3 hours (Near Real-Time) |
| **API source** | `VIIRS_NOAA20` → hotspots.source = `VIIRS_NOAA20` |

**Why VIIRS NOAA-20 NRT?**
- Highest resolution available from FIRMS (375m vs 1km MODIS)
- Near real-time: data available within ~3 hours of acquisition
- NOAA-20 is the primary operational VIIRS platform since 2018
- Maps cleanly to `hotspots.source = 'VIIRS_NOAA20'` (DB CHECK constraint)

---

## Architecture

```
NASA FIRMS API
  └── /api/country/csv/{key}/VIIRS_NOAA20_NRT/IND/{days}
       │
       ├── firms/client.py         HTTP client, auth, retry, error handling
       ├── firms/downloader.py     Save raw CSV to dataset/raw/firms/{date}/
       ├── firms/api_pipeline.py   Orchestrator (download → filter → ingest)
       │
       ├── firms/reader.py         Parse CSV, normalize column names
       ├── firms/validator.py      Validate coordinates, timestamps, FRP
       ├── firms/normalizer.py     Normalize to hotspots schema
       └── firms/loader.py         Batch INSERT to hotspots table
            │
            └── PostgreSQL: hotspots table (EPSG:4326)
```

---

## Quickstart

### Prerequisites

1. Get a free NASA FIRMS API key:  
   https://firms.modaps.eosdis.nasa.gov/api/

2. Add to `C:\SIH_Hackthon\.env`:
   ```env
   NASA_FIRMS_API_KEY=your_key_here
   ```

### Run

```powershell
# Ingest last 1 day (default):
.venv\Scripts\python.exe data_ingestion\scripts\ingest_firms.py

# Ingest last 7 days:
.venv\Scripts\python.exe data_ingestion\scripts\ingest_firms.py --days 7

# Dry run (download + parse, no DB insert):
.venv\Scripts\python.exe data_ingestion\scripts\ingest_firms.py --dry-run

# Use MODIS instead of VIIRS:
.venv\Scripts\python.exe data_ingestion\scripts\ingest_firms.py --source MODIS_NRT

# Ingest a local CSV (skip download):
.venv\Scripts\python.exe data_ingestion\scripts\ingest_firms.py `
    --path "dataset\raw\firms\2026-08-29\firms_VIIRS_NOAA20_NRT_IND_2026-08-29_d1.csv"

# Verify installation:
.venv\Scripts\python.exe data_ingestion\scripts\verify_firms.py
```

---

## API Endpoint

```
GET https://firms.modaps.eosdis.nasa.gov/api/country/csv/{key}/{source}/{country}/{days}
```

| Parameter | Example | Description |
|---|---|---|
| `key` | `MYAPIKEY` | NASA FIRMS API key (never committed) |
| `source` | `VIIRS_NOAA20_NRT` | Product source |
| `country` | `IND` | ISO 3166-1 alpha-3 (India) |
| `days` | `1` | Days relative to today (max 10) |

**API limits:**
- Maximum 10 days per single request
- Country-level filtering built-in (India = `IND`)
- No pagination needed for country + 10 days

---

## Environment Variables

Set in `C:\SIH_Hackthon\.env`:

```env
# Required
NASA_FIRMS_API_KEY=your_key_here   # NEVER commit to Git!

# Optional (have sensible defaults)
FIRMS_SOURCE=VIIRS_NOAA20_NRT      # Product source
FIRMS_COUNTRY=IND                  # Country (ISO-3)
FIRMS_DAYS=1                       # Days per request
FIRMS_REQUEST_TIMEOUT=120          # HTTP timeout (seconds)
FIRMS_MAX_RETRIES=3                # Retry attempts on failure
```

---

## Database Table: `hotspots`

Created by `database/migrations/002_create_core_tables.sql`.

```sql
hotspots (
    id                   BIGSERIAL PRIMARY KEY,
    source               TEXT NOT NULL,           -- 'VIIRS_NOAA20' etc.
    external_detection_id TEXT,
    latitude             DOUBLE PRECISION,
    longitude            DOUBLE PRECISION,
    location             GEOMETRY(Point, 4326),   -- PostGIS
    acquisition_time     TIMESTAMPTZ NOT NULL,
    satellite            TEXT,
    instrument           TEXT,
    confidence           TEXT,
    brightness           NUMERIC(10,4),
    brightness_2         NUMERIC(10,4),
    frp                  NUMERIC(14,4),           -- Fire Radiative Power (MW)
    daynight             CHAR(1),                 -- D or N
    raw_payload          JSONB,
    normalized_at        TIMESTAMPTZ,
    created_at           TIMESTAMPTZ
)
```

**Idempotency key:** `UNIQUE (source, latitude, longitude, acquisition_time)`  
→ `ON CONFLICT DO NOTHING` prevents duplicates.

---

## Raw Data

```
dataset/
└── raw/
    └── firms/
        └── YYYY-MM-DD/
            └── firms_{source}_{country}_{YYYY-MM-DD}_d{days}.csv
```

**Gitignored** — never committed.

---

## Supported Sources

| Source | Product | Resolution |
|---|---|---|
| `VIIRS_NOAA20_NRT` | VIIRS NOAA-20 Near RT | 375 m |
| `VIIRS_SNPP_NRT` | VIIRS Suomi NPP Near RT | 375 m |
| `MODIS_NRT` | MODIS Near RT | 1 km |
| `VIIRS_NOAA20_SP` | VIIRS NOAA-20 Standard | 375 m |
| `VIIRS_SNPP_SP` | VIIRS NPP Standard | 375 m |
| `MODIS_SP` | MODIS Standard | 1 km |

---

## India Filtering

1. **Primary**: FIRMS API country parameter `IND` — API returns India-only data
2. **Secondary**: Bounding box filter applied after download:
   - Latitude: 6° – 37.5° N  
   - Longitude: 68° – 98° E

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `[FAIL] FIRMS API key not configured` | `NASA_FIRMS_API_KEY` not in `.env` | Add key to `.env` |
| `HTTP 401/403` | Invalid API key | Check key at https://firms.modaps.eosdis.nasa.gov/api/ |
| `Invalid key` in response | Key format wrong | Keys are alphanumeric, no spaces |
| `0 rows` after ingestion | No fire activity or wrong date | Check `--days` value |
| `hotspots table missing` | Migrations not run | Run `database/migrations/002_create_core_tables.sql` |

---

## CLI Reference

```
ingest_firms.py [OPTIONS]

  --days INTEGER RANGE  Days of data (1-10). Default: 1.
  --source TEXT         FIRMS product. Default: VIIRS_NOAA20_NRT.
  --country TEXT        ISO-3 country. Default: IND.
  --path TEXT           Local CSV path (skips API download).
  --dry-run             Parse without inserting to DB.
  --force-download      Re-download even if today's file exists.
  --batch-size INTEGER  DB batch size.
  --help                Show this message and exit.
```
