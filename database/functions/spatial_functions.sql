-- =============================================================
-- HEATWATCH — Spatial Functions
-- database/functions/spatial_functions.sql
-- =============================================================
-- Reusable PostgreSQL functions for spatial operations.
-- These functions wrap PostGIS primitives for common
-- HEATWATCH query patterns.
--
-- SCOPE: These are database-layer spatial utilities ONLY.
-- Do NOT add satellite processing, ML, or business logic here.
-- =============================================================

-- =============================================================
-- FUNCTION: hw_nearest_facility
-- Returns the nearest industrial facility to a given point.
-- =============================================================
-- Parameters:
--   p_longitude  FLOAT8   — WGS84 longitude
--   p_latitude   FLOAT8   — WGS84 latitude
--   p_max_dist_m FLOAT8   — maximum search radius in metres
--                           (default: 50 km)
-- Returns: TABLE row with facility info and distance_m
-- =============================================================

CREATE OR REPLACE FUNCTION hw_nearest_facility(
    p_longitude  FLOAT8,
    p_latitude   FLOAT8,
    p_max_dist_m FLOAT8 DEFAULT 50000.0
)
RETURNS TABLE (
    facility_id    UUID,
    name           TEXT,
    facility_type  facility_type,
    distance_m     FLOAT8,
    source         TEXT,
    confidence     NUMERIC
) LANGUAGE sql STABLE AS $$
    SELECT
        f.id,
        f.name,
        f.facility_type,
        ST_Distance(
            f.location::geography,
            ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography
        ) AS distance_m,
        f.source,
        f.confidence
    FROM industrial_facilities f
    WHERE ST_DWithin(
        f.location::geography,
        ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography,
        p_max_dist_m
    )
    ORDER BY f.location <-> ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)
    LIMIT 1;
$$;

COMMENT ON FUNCTION hw_nearest_facility IS
    'Returns the single nearest industrial facility within p_max_dist_m metres '
    'of the given WGS84 coordinates. Uses KNN operator (<->) for index efficiency.';


-- =============================================================
-- FUNCTION: hw_facilities_within_radius
-- Returns all industrial facilities within a radius.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_facilities_within_radius(
    p_longitude  FLOAT8,
    p_latitude   FLOAT8,
    p_radius_m   FLOAT8
)
RETURNS TABLE (
    facility_id    UUID,
    name           TEXT,
    facility_type  facility_type,
    distance_m     FLOAT8
) LANGUAGE sql STABLE AS $$
    SELECT
        f.id,
        f.name,
        f.facility_type,
        ST_Distance(
            f.location::geography,
            ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography
        ) AS distance_m
    FROM industrial_facilities f
    WHERE ST_DWithin(
        f.location::geography,
        ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326)::geography,
        p_radius_m
    )
    ORDER BY distance_m;
$$;

COMMENT ON FUNCTION hw_facilities_within_radius IS
    'Returns all industrial facilities within p_radius_m metres of a point. '
    'Ordered by ascending distance.';


-- =============================================================
-- FUNCTION: hw_thermal_objects_in_bbox
-- Returns thermal objects within a bounding box.
-- =============================================================
-- Parameters:
--   p_min_lon, p_min_lat — SW corner
--   p_max_lon, p_max_lat — NE corner
-- Used for map viewport queries.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_thermal_objects_in_bbox(
    p_min_lon FLOAT8,
    p_min_lat FLOAT8,
    p_max_lon FLOAT8,
    p_max_lat FLOAT8
)
RETURNS TABLE (
    thermal_object_id UUID,
    centroid_lon      FLOAT8,
    centroid_lat      FLOAT8,
    status            thermal_object_status,
    persistence_score NUMERIC,
    first_seen        TIMESTAMPTZ,
    last_seen         TIMESTAMPTZ,
    observation_count INTEGER
) LANGUAGE sql STABLE AS $$
    SELECT
        t.id,
        ST_X(t.centroid),
        ST_Y(t.centroid),
        t.status,
        t.persistence_score,
        t.first_seen,
        t.last_seen,
        t.observation_count
    FROM thermal_objects t
    WHERE t.centroid && ST_MakeEnvelope(p_min_lon, p_min_lat, p_max_lon, p_max_lat, 4326);
$$;

COMMENT ON FUNCTION hw_thermal_objects_in_bbox IS
    'Returns thermal objects whose centroid falls within the given bounding box. '
    'Uses the && operator with GiST index for fast spatial filtering.';


-- =============================================================
-- FUNCTION: hw_distance_to_nearest_facility
-- Returns distance in metres from a thermal object centroid
-- to the nearest industrial facility.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_distance_to_nearest_facility(
    p_thermal_object_id UUID
)
RETURNS FLOAT8 LANGUAGE sql STABLE AS $$
    SELECT
        ST_Distance(
            t.centroid::geography,
            f.location::geography
        )
    FROM thermal_objects t
    CROSS JOIN LATERAL (
        SELECT location
        FROM industrial_facilities
        ORDER BY location <-> t.centroid
        LIMIT 1
    ) f
    WHERE t.id = p_thermal_object_id;
$$;

COMMENT ON FUNCTION hw_distance_to_nearest_facility IS
    'Returns distance in metres from a thermal object centroid to the nearest '
    'industrial facility. Returns NULL if no facilities exist.';


-- =============================================================
-- FUNCTION: hw_hotspots_in_bbox
-- Returns hotspots within a bounding box and time range.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_hotspots_in_bbox(
    p_min_lon   FLOAT8,
    p_min_lat   FLOAT8,
    p_max_lon   FLOAT8,
    p_max_lat   FLOAT8,
    p_from_time TIMESTAMPTZ DEFAULT NOW() - INTERVAL '24 hours',
    p_to_time   TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (
    hotspot_id       UUID,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,
    acquisition_time TIMESTAMPTZ,
    source           TEXT,
    frp              NUMERIC,
    confidence       TEXT
) LANGUAGE sql STABLE AS $$
    SELECT
        h.id,
        h.latitude,
        h.longitude,
        h.acquisition_time,
        h.source,
        h.frp,
        h.confidence
    FROM hotspots h
    WHERE h.location && ST_MakeEnvelope(p_min_lon, p_min_lat, p_max_lon, p_max_lat, 4326)
      AND h.acquisition_time BETWEEN p_from_time AND p_to_time
    ORDER BY h.acquisition_time DESC;
$$;

COMMENT ON FUNCTION hw_hotspots_in_bbox IS
    'Returns hotspots within a bounding box and time range. '
    'Defaults to the last 24 hours if times are not specified.';
