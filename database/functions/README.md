# HEATWATCH — Database Functions

Reusable PostgreSQL functions for the HEATWATCH database.

## Files

| File | Contents |
|---|---|
| `spatial_functions.sql` | Spatial utilities: nearest facility, radius search, bounding-box queries |
| `maintenance_functions.sql` | Maintenance: updated_at trigger, row counts, cleanup helpers |

## Loading Functions

```bash
psql $DATABASE_URL -f functions/spatial_functions.sql
psql $DATABASE_URL -f functions/maintenance_functions.sql
```

These functions depend on all migration tables existing.
Run after migrations 000–009.

## Key Functions

| Function | Purpose |
|---|---|
| `hw_nearest_facility(lon, lat, max_m)` | Single nearest facility to a point |
| `hw_facilities_within_radius(lon, lat, m)` | All facilities within radius |
| `hw_thermal_objects_in_bbox(...)` | Thermal objects in map viewport |
| `hw_hotspots_in_bbox(...)` | Hotspots in viewport + time range |
| `hw_distance_to_nearest_facility(id)` | Distance from thermal object to nearest facility |
| `hw_table_row_counts()` | Row count audit for all tables |
| `hw_archive_candidates(days)` | Identify old hotspots for archival |
