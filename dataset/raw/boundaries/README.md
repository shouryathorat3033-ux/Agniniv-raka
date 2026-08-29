# India Boundary File — REQUIRED

This directory must contain the official India administrative boundary
in GeoJSON format before the Sentinel-2 metadata pipeline can perform
a true India-only geographic filter.

## Required file

```
dataset/raw/boundaries/india_boundary.geojson
```

## Format

- GeoJSON FeatureCollection or single Feature
- Geometry type: Polygon or MultiPolygon
- CRS: WGS-84 (EPSG:4326)
- Represents: India national boundary (Level 0 admin)

## Recommended sources (free, authoritative)

### Option A — Natural Earth (recommended for speed, ~50 KB)
URL: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/
File: ne_10m_admin_0_countries
Filter: ADMIN == "India"
Licence: Public domain

### Option B — GADM (highest precision, ~6 MB)
URL: https://gadm.org/download_country.html
Country: India, Level 0 (national boundary)
Format: GeoJSON
Licence: Free for non-commercial use

### Option C — GeoBoundaries
URL: https://www.geoboundaries.org/
Country: IND, ADM0
Licence: CC-BY 4.0

## How to create this file (Natural Earth example)

1. Download ne_10m_admin_0_countries.zip from Natural Earth.
2. Extract the shapefile.
3. Run (requires geopandas or ogr2ogr):

   python -c "
   import geopandas as gpd
   world = gpd.read_file('ne_10m_admin_0_countries.shp')
   india = world[world.ADMIN == 'India']
   india.to_file('dataset/raw/boundaries/india_boundary.geojson', driver='GeoJSON')
   "

   OR using ogr2ogr (no Python required):

   ogr2ogr -f GeoJSON dataset/raw/boundaries/india_boundary.geojson \
     ne_10m_admin_0_countries.shp \
     -where "ADMIN='India'"

## Why this file is required

The STAC bounding box [68.1, 7.9, 97.4, 37.1] is an initial search
optimisation only.  It includes parts of Pakistan, Bangladesh, Nepal,
Bhutan, Myanmar, Sri Lanka, and China.  The actual India polygon is
required to:

  1. Filter out STAC items whose Sentinel-2 tile footprints do not
     genuinely intersect Indian territory.
  2. Allow the project to correctly claim "India-only" data.

Until this file is present, the discovery pipeline will:
  - Still run with bbox-only filtering
  - Set india_intersection = BBOX_ONLY for every row
  - Clearly label the output as UNVERIFIED for spatial filtering
  - NOT claim the dataset is India-only

## Status

india_boundary.geojson : MISSING — must be manually provided.
