-- =============================================================
-- Migration 003 — Context, Historical & Feature Tables
-- HEATWATCH Database
-- =============================================================
-- Tables: industrial_facilities, osm_context, land_context,
--         historical_profiles, feature_vectors
--
-- Depends on: 000, 001, 002
-- =============================================================

-- =============================================================
-- TABLE: industrial_facilities
-- =============================================================
-- Purpose:
--   Known industrial and infrastructure sites used by the
--   source attribution pipeline (Brain 1) to identify whether
--   a thermal object is near a known emission source.
--   This table is populated from external datasets
--   (GEM, GPPD, OSM, regulatory registries) — NOT from
--   satellite observations.
-- =============================================================

CREATE TABLE industrial_facilities (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),

    name             TEXT          NOT NULL,
    facility_type    facility_type NOT NULL,

    -- Source provenance
    source           TEXT          NOT NULL,   -- e.g. 'GEM_2024', 'OSM', 'GPPD', 'EPA'
    source_reference TEXT,                     -- URL or dataset ID

    -- Spatial representation (WGS84, SRID 4326)
    location         GEOMETRY(Point, 4326)          NOT NULL,
    boundary         GEOMETRY(Geometry, 4326),       -- Optional polygon/multipolygon

    -- Data quality
    confidence       NUMERIC(5,4)
                       CHECK (confidence BETWEEN 0.0 AND 1.0),

    -- Extensible metadata (country, operator, capacity, permit IDs, etc.)
    metadata         JSONB,

    created_at       TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE industrial_facilities IS
    'Known industrial sites. Populated from external reference datasets. '
    'Used for spatial proximity matching during source attribution.';

COMMENT ON COLUMN industrial_facilities.boundary IS
    'Optional polygon or multipolygon footprint. '
    'When NULL, point-based proximity queries use location instead.';

CREATE TRIGGER trg_industrial_facilities_updated_at
    BEFORE UPDATE ON industrial_facilities
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- =============================================================
-- TABLE: osm_context
-- =============================================================
-- Purpose:
--   Stores cached OpenStreetMap features within search radius
--   of a thermal object. This table only stores data — it does
--   NOT fetch from OSM. A future enrichment service will populate
--   it via the OSM Overpass API.
-- =============================================================

CREATE TABLE osm_context (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id UUID        NOT NULL
                        REFERENCES thermal_objects(id) ON DELETE CASCADE,

    -- OSM feature reference
    osm_type          TEXT        NOT NULL
                        CHECK (osm_type IN ('node', 'way', 'relation')),
    osm_id            BIGINT      NOT NULL,

    name              TEXT,
    tags              JSONB,

    -- Spatial representation
    geometry          GEOMETRY(Geometry, 4326),

    -- Distance from thermal object centroid (metres)
    distance_meters   NUMERIC(14,2)
                        CHECK (distance_meters >= 0),

    -- Freshness tracking
    retrieved_at      TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate OSM objects per thermal_object
    CONSTRAINT uq_osm_context_feature
        UNIQUE (thermal_object_id, osm_type, osm_id)
);

COMMENT ON TABLE osm_context IS
    'Cached OSM features near a thermal object. '
    'Populated by an external enrichment service, not by this database module. '
    'ON DELETE CASCADE: removing a thermal_object removes its OSM context.';


-- =============================================================
-- TABLE: land_context
-- =============================================================
-- Purpose:
--   Land-cover classification context associated with a thermal
--   object. Populated from ESA WorldCover, MODIS MCD12Q1, or
--   similar land-cover products.
--
-- Score columns store fractional area [0.0, 1.0].
-- All scores for a given row should sum to ≤ 1.0 but this is
-- not enforced at the DB layer because partial-area queries
-- (e.g. only forest fraction) are valid use cases.
-- =============================================================

CREATE TABLE land_context (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id UUID        NOT NULL
                        REFERENCES thermal_objects(id) ON DELETE CASCADE,

    land_cover_class  TEXT,               -- Dominant class label
    land_cover_source TEXT        NOT NULL, -- e.g. 'ESA_WorldCover_2021', 'MODIS_MCD12Q1'
    resolution_meters INTEGER
                        CHECK (resolution_meters > 0),

    -- Fractional area scores [0.0, 1.0]
    built_up_score    NUMERIC(5,4) CHECK (built_up_score    BETWEEN 0.0 AND 1.0),
    cropland_score    NUMERIC(5,4) CHECK (cropland_score    BETWEEN 0.0 AND 1.0),
    tree_cover_score  NUMERIC(5,4) CHECK (tree_cover_score  BETWEEN 0.0 AND 1.0),
    shrubland_score   NUMERIC(5,4) CHECK (shrubland_score   BETWEEN 0.0 AND 1.0),
    grassland_score   NUMERIC(5,4) CHECK (grassland_score   BETWEEN 0.0 AND 1.0),
    water_score       NUMERIC(5,4) CHECK (water_score       BETWEEN 0.0 AND 1.0),
    bare_land_score   NUMERIC(5,4) CHECK (bare_land_score   BETWEEN 0.0 AND 1.0),

    -- Extensible metadata (dataset version, pixel count, etc.)
    metadata          JSONB,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate context records for the same object + data source
    CONSTRAINT uq_land_context_source
        UNIQUE (thermal_object_id, land_cover_source)
);

COMMENT ON TABLE land_context IS
    'Land-cover fractional scores for a thermal object area. '
    'Distinguishes industrial/urban heat from forest fires.';

CREATE TRIGGER trg_land_context_updated_at
    BEFORE UPDATE ON land_context
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- =============================================================
-- TABLE: historical_profiles
-- =============================================================
-- Purpose:
--   Baseline behavioural statistics for a thermal object
--   computed over a defined time window.
--   Used by Brain 2 (anomaly detection) to identify deviations.
--
-- profile_version supports re-computation as algorithms evolve.
-- =============================================================

CREATE TABLE historical_profiles (
    id                  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id   UUID        NOT NULL
                          REFERENCES thermal_objects(id) ON DELETE CASCADE,

    -- Baseline window (UTC)
    baseline_start      TIMESTAMPTZ NOT NULL,
    baseline_end        TIMESTAMPTZ NOT NULL,

    -- FRP statistics
    rolling_frp_mean    NUMERIC(14,4) CHECK (rolling_frp_mean >= 0),
    rolling_frp_std     NUMERIC(14,4) CHECK (rolling_frp_std  >= 0),

    -- Activity metrics
    historical_frequency NUMERIC(8,4) CHECK (historical_frequency >= 0),
    recurrence_score     NUMERIC(6,4) CHECK (recurrence_score BETWEEN 0.0 AND 1.0),
    persistence_days     INTEGER      CHECK (persistence_days >= 0),

    -- Seasonal pattern (hour-of-day histogram, monthly index, etc.)
    seasonal_pattern    JSONB,

    -- Algorithm versioning
    profile_version     TEXT        NOT NULL DEFAULT 'v1',

    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Temporal integrity
    CONSTRAINT chk_historical_profile_time_order
        CHECK (baseline_start <= baseline_end),

    -- One profile per object per version per window
    CONSTRAINT uq_historical_profile_version
        UNIQUE (thermal_object_id, profile_version, baseline_start, baseline_end)
);

COMMENT ON TABLE historical_profiles IS
    'Baseline statistics for a thermal object computed over a time window. '
    'Used by the anomaly detection pipeline for deviation scoring.';

CREATE TRIGGER trg_historical_profiles_updated_at
    BEFORE UPDATE ON historical_profiles
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- =============================================================
-- TABLE: feature_vectors
-- =============================================================
-- Purpose:
--   Stores engineered ML features for a thermal object at a
--   given point in time.
--
-- Design decision: features are stored in JSONB, NOT in separate
-- SQL columns. Rationale:
--   • Feature engineering is experimental and changes frequently.
--   • Adding/removing SQL columns requires migrations.
--   • JSONB allows flexible schema evolution.
--   • feature_schema_version tracks which set of features is stored.
-- A GIN index is created on features to support JSON key existence
-- queries (e.g. feature presence checks during debugging). It is
-- NOT required for standard SELECT by thermal_object_id.
-- =============================================================

CREATE TABLE feature_vectors (
    id                    UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id     UUID        NOT NULL
                            REFERENCES thermal_objects(id) ON DELETE CASCADE,

    -- Feature engineering pipeline version (e.g. 'v1.2', 'schema_2025_q3')
    feature_schema_version TEXT       NOT NULL,

    -- All engineered features as a flexible JSON document
    features              JSONB       NOT NULL,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE feature_vectors IS
    'Engineered ML feature snapshots per thermal object. '
    'JSONB storage allows schema evolution without SQL migrations. '
    'feature_schema_version tracks which feature set is stored.';


DO $$
BEGIN
  RAISE NOTICE 'Migration 003: Context, historical, and feature tables created.';
END $$;
