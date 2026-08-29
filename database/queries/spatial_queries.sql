-- =============================================================
-- HEATWATCH — Spatial Query Examples
-- database/queries/spatial_queries.sql
-- =============================================================
-- All queries are ready to run via psql or any SQL client.
-- Replace :parameter placeholders with actual values.
-- =============================================================

-- =============================================================
-- Q1: Thermal objects within a bounding box
-- Map viewport query — replace coordinates with your viewport.
-- =============================================================
SELECT
    t.id,
    ST_X(t.centroid)     AS longitude,
    ST_Y(t.centroid)     AS latitude,
    t.status,
    t.persistence_score,
    t.first_seen,
    t.last_seen,
    t.observation_count
FROM thermal_objects t
WHERE t.centroid && ST_MakeEnvelope(
    68.0,   -- min longitude (SW corner, India example)
    8.0,    -- min latitude
    97.5,   -- max longitude (NE corner)
    37.0,   -- max latitude
    4326
)
  AND t.status = 'ACTIVE'
ORDER BY t.last_seen DESC;


-- =============================================================
-- Q2: Nearest industrial facility to a thermal object centroid
-- =============================================================
SELECT
    f.id                          AS facility_id,
    f.name,
    f.facility_type,
    ST_Distance(
        t.centroid::geography,
        f.location::geography
    )                             AS distance_m
FROM thermal_objects t
CROSS JOIN LATERAL (
    SELECT id, name, facility_type, location
    FROM industrial_facilities
    ORDER BY location <-> t.centroid   -- KNN operator uses GiST index
    LIMIT 1
) f
WHERE t.id = 'YOUR_THERMAL_OBJECT_UUID_HERE'::uuid;


-- =============================================================
-- Q3: All facilities within 10 km of a coordinate
-- =============================================================
SELECT
    f.id,
    f.name,
    f.facility_type,
    f.confidence,
    ST_Distance(
        f.location::geography,
        ST_SetSRID(ST_MakePoint(77.1025, 28.7041), 4326)::geography
    ) AS distance_m
FROM industrial_facilities f
WHERE ST_DWithin(
    f.location::geography,
    ST_SetSRID(ST_MakePoint(77.1025, 28.7041), 4326)::geography,
    10000  -- 10 km in metres
)
ORDER BY distance_m;


-- =============================================================
-- Q4: Distance from each active thermal object to its nearest facility
-- =============================================================
SELECT
    t.id                          AS thermal_object_id,
    ST_X(t.centroid)              AS longitude,
    ST_Y(t.centroid)              AS latitude,
    f.name                        AS nearest_facility,
    f.facility_type,
    ST_Distance(
        t.centroid::geography,
        f.location::geography
    )                             AS distance_m
FROM thermal_objects t
CROSS JOIN LATERAL (
    SELECT name, facility_type, location
    FROM industrial_facilities
    ORDER BY location <-> t.centroid
    LIMIT 1
) f
WHERE t.status = 'ACTIVE'
ORDER BY distance_m;


-- =============================================================
-- Q5: Thermal objects that intersect a facility boundary
-- (for facilities with polygon footprints)
-- =============================================================
SELECT DISTINCT
    t.id                          AS thermal_object_id,
    f.name                        AS facility_name,
    f.facility_type
FROM thermal_objects t
JOIN industrial_facilities f
    ON ST_Intersects(t.object_geometry, f.boundary)
WHERE f.boundary IS NOT NULL
  AND t.status IN ('ACTIVE', 'PERSISTENT');


-- =============================================================
-- Q6: Hotspots along a pipeline corridor (2 km buffer)
-- Replace the LINESTRING with your actual pipeline geometry.
-- =============================================================
WITH pipeline AS (
    SELECT ST_Buffer(
        ST_GeomFromText(
            'LINESTRING(68.5 23.0, 72.8 21.0, 76.2 20.1)',
            4326
        )::geography,
        2000         -- 2 km buffer in metres
    )::geometry AS corridor
)
SELECT
    h.id,
    h.latitude,
    h.longitude,
    h.frp,
    h.acquisition_time,
    h.confidence
FROM hotspots h, pipeline p
WHERE ST_Within(h.location, p.corridor)
  AND h.acquisition_time >= NOW() - INTERVAL '48 hours'
ORDER BY h.frp DESC NULLS LAST;
