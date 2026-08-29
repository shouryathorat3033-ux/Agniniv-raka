# HEATWATCH Data Ingestion — Data Mapping Reference

This document maps each external dataset's raw fields to HEATWATCH database table columns.

---

## 1. NASA FIRMS → `hotspots`

### Key Column Aliases (FIRMS product variants)

| FIRMS Column (raw) | Normalized Column | Description |
|---|---|---|
| `latitude` / `lat` | `latitude` | Point latitude (Y) |
| `longitude` / `lon` / `long` | `longitude` | Point longitude (X) |
| `acq_date` | `acq_date` | Acquisition date (YYYY-MM-DD) |
| `acq_time` | `acq_time` | Acquisition time (HHMM integer) |
| `satellite` | `satellite` | Satellite name |
| `instrument` | `instrument` | Sensor name |
| `confidence` | `confidence` | l/n/h or 0–100 |
| `brightness` / `bright_ti4` / `bright_t21` | `brightness` | Band 21 brightness temp (K) |
| `bright_ti5` / `bright_t31` | `brightness_2` | Band 31 brightness temp (K) |
| `frp` | `frp` | Fire Radiative Power (MW) |
| `daynight` / `day_night` | `daynight` | D or N |

### Satellite → `source` Mapping

| FIRMS Value | DB `source` |
|---|---|
| Terra / TERRA | MODIS_TERRA |
| Aqua / AQUA | MODIS_AQUA |
| NOAA-20 / J1 | VIIRS_NOAA20 |
| Suomi NPP / SNPP | VIIRS_NPP |
| Landsat-8 | LANDSAT_8 |
| Landsat-9 | LANDSAT_9 |
| Sentinel-2 | SENTINEL_2 |
| Sentinel-3 | SENTINEL_3 |
| GOES-16 | GOES_16 |
| GOES-18 | GOES_18 |
| Himawari-9 | HIMAWARI_9 |
| (anything else) | OTHER |

### `hotspots` Database Fields

| DB Column | Type | Source |
|---|---|---|
| `source` | TEXT (CHECK) | Mapped from satellite field |
| `external_detection_id` | TEXT NULL | NULL for FIRMS CSV (no row-level ID) |
| `latitude` | DOUBLE PRECISION | Direct from CSV |
| `longitude` | DOUBLE PRECISION | Direct from CSV |
| `location` | GEOMETRY(Point,4326) | `ST_SetSRID(ST_MakePoint(lon,lat),4326)` |
| `acquisition_time` | TIMESTAMPTZ | Parsed from acq_date + acq_time → UTC |
| `satellite` | TEXT NULL | Original FIRMS satellite string |
| `instrument` | TEXT NULL | MODIS / VIIRS / OLI etc. |
| `confidence` | TEXT NULL | Normalized: low/nominal/high or integer |
| `brightness` | NUMERIC(10,4) | Band 21/bright_ti4 |
| `brightness_2` | NUMERIC(10,4) | Band 31/bright_ti5 |
| `frp` | NUMERIC(14,4) | Fire Radiative Power (MW) |
| `daynight` | CHAR(1) | D or N |
| `raw_payload` | JSONB | Full original CSV row as JSON |
| `normalized_at` | TIMESTAMPTZ | Ingestion timestamp |

### Deduplication

`UNIQUE(source, latitude, longitude, acquisition_time)` — ON CONFLICT DO NOTHING.

---

## 2. OSM → `industrial_facilities` + `osm_context`

### OSM Routing Logic

OSM features are first read, then classified:

```
OSM Feature
  ↓
Has industrial tag? → YES → industrial_facilities
                   → NO  → osm_context (requires thermal_object_id)
```

### Industrial Tags Checked

| Tag | Values That Route to industrial_facilities |
|---|---|
| `landuse` | industrial |
| `man_made` | petroleum_well, oil_refinery, works, chimney, storage_tank, gasometer, silo, wastewater_plant |
| `industrial` | oil, gas, refinery, steel, mining, chemical, power, petrochemical, cement, coal, fertilizer, aluminium |
| `power` | plant |
| `building` | industrial |

### `industrial_facilities` Fields

| DB Column | Source |
|---|---|
| `name` | `name` property or fallback |
| `facility_type` | Keyword-mapped from tags/name (ENUM) |
| `source` | `"OSM"` |
| `source_reference` | `"way/123456789"` or `"node/..."` |
| `location` | Centroid of geometry → POINT(lon lat) |
| `boundary` | Full geometry if Polygon/MultiPolygon |
| `confidence` | 0.6 (OSM data is approximate) |
| `metadata` | JSON with osm_type, osm_id, full tags |

---

## 3. ESA WorldCover → `land_context`

### Class Code Mapping

| Code | Class | land_context Field |
|---|---|---|
| 10 | Tree cover | tree_cover_score |
| 20 | Shrubland | shrubland_score |
| 30 | Grassland | grassland_score |
| 40 | Cropland | cropland_score |
| 50 | Built-up | built_up_score |
| 60 | Bare/sparse veg | bare_land_score |
| 80 | Permanent water | water_score |
| 90 | Herbaceous wetland | grassland_score |
| 95 | Mangroves | tree_cover_score |
| 100 | Moss/lichen | bare_land_score |

### Lookup Method

For each `thermal_object`:
1. Read buffer window (default 0.01° ≈ 1 km) from raster around centroid
2. Count pixels per class code
3. Compute fractional score = class_count / total_valid_pixels
4. Identify dominant class name

### `land_context` Fields

| DB Column | Source |
|---|---|
| `thermal_object_id` | FK to thermal_objects (required) |
| `land_cover_class` | Dominant class name string |
| `land_cover_source` | From LANDCOVER_DATASET_ID env var |
| `resolution_meters` | From LANDCOVER_RESOLUTION_M env var |
| `built_up_score` | Fraction in [0.0, 1.0] |
| `cropland_score` | Fraction in [0.0, 1.0] |
| `tree_cover_score` | Fraction in [0.0, 1.0] |
| etc. | Fraction in [0.0, 1.0] |

---

## 4. Industrial Facility DB → `industrial_facilities`

### Flexible Column Detection

| DB Field | Recognized Raw Column Names |
|---|---|
| `name` | name, plant_name, facility_name, site_name, operator |
| `source_reference` | source_reference, source_ref, id, gid, uid, identifier |
| `facility_type` | facility_type, type, plant_type, category, sector, kind |
| latitude (CSV) | latitude, lat |
| longitude (CSV) | longitude, lon, long |

### facility_type ENUM Keyword Mapping

| Input String Contains | Maps To |
|---|---|
| refinery, oil refinery | REFINERY |
| power plant, coal plant | POWER_PLANT |
| steel, blast furnace | STEEL_PLANT |
| petrochemical | PETROCHEMICAL |
| lng, liquefied natural gas | LNG_TERMINAL |
| mine, mining, quarry | MINING |
| cement, clinker | CEMENT |
| chemical, fertilizer, ammonia | CHEMICAL |
| (no match) | OTHER |

### Confidence Score

0.8 — higher than OSM (structured database, more reliable)

---

## 5. Satellite Metadata → scene_catalogue.json

No PostgreSQL table exists yet. Metadata stored as JSON:
- `dataset/processed/satellite/scene_catalogue.json`

**Future migration:** add `satellite_scenes` table (template documented in `satellite/metadata_transformer.py`).

---

## Deduplication Summary

| Dataset | Method | Scope |
|---|---|---|
| FIRMS (all) | DB: ON CONFLICT uq_hotspot_pixel_time DO NOTHING | source + lat + lon + time |
| Industrial | App: check source + source_reference before insert | Per record |
| OSM industrial | DB: ON CONFLICT DO NOTHING | source + source_reference |
| Land context | DB: ON CONFLICT uq_land_context_source DO NOTHING | thermal_object_id + source |

---

## What Is NOT Stored

| Data | Reason |
|---|---|
| Raw raster pixels | Too large; lookup performed on-demand |
| Satellite imagery | Too large; stored locally only |
| OSM context rows (without thermal_object_id) | FK constraint — saved to processed/ JSON |
| ML features | Computed by analytics pipeline, not ingestion |
