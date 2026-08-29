-- =============================================================
-- Migration 002 — Core Tables
-- HEATWATCH Database
-- =============================================================
-- Tables: hotspots, thermal_objects, thermal_object_observations
--
-- Depends on: 000_enable_extensions.sql, 001_create_enums.sql
-- =============================================================

-- =============================================================
-- TABLE: hotspots
-- =============================================================
-- Purpose:
--   Stores raw and normalized individual NASA FIRMS thermal
--   observations. One row = one satellite pixel detection event.
--
-- Duplicate prevention strategy:
--   • When an external_detection_id is provided (source + ID):
--     → UNIQUE(source, external_detection_id)
--   • When no external ID exists (some FIRMS products omit it):
--     → UNIQUE(source, latitude, longitude, acquisition_time)
--     This prevents exact re-ingestion of the same pixel.
--     Slight coordinate rounding differences between passes of
--     the same event will NOT be deduplicated — this is correct.
-- =============================================================

CREATE TABLE hotspots (
    id                    UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source identification
    source                TEXT         NOT NULL
                            CHECK (source IN (
                                'MODIS_TERRA', 'MODIS_AQUA',
                                'VIIRS_NOAA20', 'VIIRS_NPP',
                                'LANDSAT_8', 'LANDSAT_9',
                                'SENTINEL_2', 'SENTINEL_3',
                                'GOES_16', 'GOES_18',
                                'HIMAWARI_9', 'OTHER'
                            )),
    external_detection_id TEXT,        -- Provider-native pixel ID (nullable)

    -- Coordinates (WGS84 / SRID 4326)
    latitude              DOUBLE PRECISION NOT NULL
                            CHECK (latitude  BETWEEN -90.0  AND  90.0),
    longitude             DOUBLE PRECISION NOT NULL
                            CHECK (longitude BETWEEN -180.0 AND 180.0),

    -- PostGIS point geometry (SRID 4326)
    -- Kept in sync with latitude/longitude by the inserting application.
    location              GEOMETRY(Point, 4326) NOT NULL,

    -- Detection timing (UTC)
    acquisition_time      TIMESTAMPTZ  NOT NULL,

    -- Sensor metadata
    satellite             TEXT,
    instrument            TEXT,

    -- Confidence: TEXT because different products use different scales
    -- (FIRMS uses 'low'/'nominal'/'high'; GOES uses 0-100).
    confidence            TEXT,

    -- Thermal measurements
    brightness            NUMERIC(10,4),  -- Band 21 brightness temp (K)
    brightness_2          NUMERIC(10,4),  -- Band 31 brightness temp (K)
    frp                   NUMERIC(14,4),  -- Fire Radiative Power (MW)
    daynight              CHAR(1)
                            CHECK (daynight IN ('D', 'N')),

    -- Raw ingested payload (original JSON/CSV row for audit)
    raw_payload           JSONB,

    -- Ingestion tracking
    normalized_at         TIMESTAMPTZ,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Duplicate prevention when external_detection_id is present
    CONSTRAINT uq_hotspot_external_id UNIQUE (source, external_detection_id),

    -- Duplicate prevention when no external_detection_id is available
    CONSTRAINT uq_hotspot_pixel_time  UNIQUE (source, latitude, longitude, acquisition_time)
);

COMMENT ON TABLE hotspots IS
    'Raw and FIRMS-normalized thermal pixel detection events. '
    'One row per satellite pixel per acquisition time. '
    'Parent data for thermal object clustering.';

COMMENT ON COLUMN hotspots.external_detection_id IS
    'Provider-native detection ID. NULL when the source product does not supply one. '
    'UNIQUE(source, external_detection_id) prevents duplicate ingestion when present.';

COMMENT ON COLUMN hotspots.location IS
    'PostGIS Point geometry in SRID 4326. Must match latitude/longitude columns. '
    'Use ::geography for accurate metre-scale distance calculations.';


-- =============================================================
-- TABLE: thermal_objects
-- =============================================================
-- Purpose:
--   Spatiotemporal clusters of hotspot observations.
--   One thermal_object represents a single persistent heat source
--   tracked across satellite passes. Clustering is performed by
--   an external pipeline (e.g. ST-DBSCAN) which then inserts
--   rows here.
-- =============================================================

CREATE TABLE thermal_objects (
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Spatial representation
    object_geometry   GEOMETRY(Geometry, 4326),  -- Convex hull or cluster polygon
    centroid          GEOMETRY(Point, 4326) NOT NULL,

    -- Temporal span (UTC)
    first_seen        TIMESTAMPTZ  NOT NULL,
    last_seen         TIMESTAMPTZ  NOT NULL,

    -- Aggregate metrics
    observation_count INTEGER      NOT NULL DEFAULT 0
                        CHECK (observation_count >= 0),
    duration_hours    NUMERIC(10,2)
                        GENERATED ALWAYS AS (
                            EXTRACT(EPOCH FROM (last_seen - first_seen)) / 3600.0
                        ) STORED,
    persistence_score NUMERIC(6,4)
                        CHECK (persistence_score BETWEEN 0.0 AND 1.0),

    -- Lifecycle status
    status            thermal_object_status NOT NULL DEFAULT 'ACTIVE',

    -- Clustering metadata
    cluster_algorithm TEXT,
    cluster_params    JSONB,

    created_at        TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Temporal integrity
    CONSTRAINT chk_thermal_object_time_order
        CHECK (first_seen <= last_seen)
);

COMMENT ON TABLE thermal_objects IS
    'Spatiotemporal clusters of hotspot observations. '
    'One row = one tracked heat source. '
    'Parent entity for all AI analysis, alerts, and human reviews.';

COMMENT ON COLUMN thermal_objects.duration_hours IS
    'Computed column: (last_seen - first_seen) in hours. Stored physically for query efficiency.';

COMMENT ON COLUMN thermal_objects.persistence_score IS
    'Normalized score [0,1] indicating how persistent this thermal object is. '
    'Computed by the clustering pipeline. 1.0 = fully persistent.';


-- =============================================================
-- TABLE: thermal_object_observations
-- =============================================================
-- Purpose:
--   Bridge table linking thermal_objects to their constituent
--   hotspot observations (M:M relationship).
--
-- Cascade strategy:
--   ON DELETE CASCADE from thermal_objects: removing a cluster
--     removes all its membership records but does NOT delete
--     the underlying hotspot rows (those remain for audit).
--   ON DELETE CASCADE from hotspots: if a hotspot is retracted,
--     remove its membership. The thermal_object remains.
-- =============================================================

CREATE TABLE thermal_object_observations (
    thermal_object_id UUID        NOT NULL
        REFERENCES thermal_objects(id) ON DELETE CASCADE,
    hotspot_id        UUID        NOT NULL
        REFERENCES hotspots(id)        ON DELETE CASCADE,
    assigned_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (thermal_object_id, hotspot_id)
);

COMMENT ON TABLE thermal_object_observations IS
    'Bridge table: M:M between thermal_objects and hotspots. '
    'Cascade from thermal_objects removes membership; cascade from hotspots '
    'removes membership but preserves the thermal_object.';


-- =============================================================
-- Triggers: updated_at auto-maintenance
-- =============================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_thermal_objects_updated_at
    BEFORE UPDATE ON thermal_objects
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


DO $$
BEGIN
  RAISE NOTICE 'Migration 002: Core tables created (hotspots, thermal_objects, thermal_object_observations).';
END $$;
