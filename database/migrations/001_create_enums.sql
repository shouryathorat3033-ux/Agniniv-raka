-- =============================================================
-- Migration 001 — Create ENUMs and Controlled Types
-- HEATWATCH Database
-- =============================================================
-- ENUMs are used for values that are:
--   - Stable and unlikely to change
--   - Validated at the database layer
--   - Used across multiple tables
--
-- CHECK constraints are used where:
--   - Values may evolve without a migration
--   - Inline documentation is sufficient
-- =============================================================

-- ── Facility type ─────────────────────────────────────────────
-- Used in: industrial_facilities
CREATE TYPE facility_type AS ENUM (
    'REFINERY',
    'POWER_PLANT',
    'STEEL_PLANT',
    'PETROCHEMICAL',
    'LNG_TERMINAL',
    'MINING',
    'CEMENT',
    'CHEMICAL',
    'OTHER'
);

-- ── Source/attribution category ───────────────────────────────
-- Used in: source_attributions, human_reviews, verified_events
CREATE TYPE source_category AS ENUM (
    'INDUSTRIAL_FIRE',
    'PERSISTENT_THERMAL_SOURCE',
    'FOREST_FIRE',
    'AGRICULTURAL_BURNING',
    'MINING_ACTIVITY',
    'OTHER_OR_UNKNOWN'
);

-- ── Anomaly detection level ───────────────────────────────────
-- Used in: anomaly_results
CREATE TYPE anomaly_level AS ENUM (
    'NORMAL',
    'ELEVATED',
    'HIGH'
);

-- ── RAG supervisor status ────────────────────────────────────
-- Used in: supervisor_reviews
CREATE TYPE supervisor_status AS ENUM (
    'ACCEPTED',
    'FLAGGED_FOR_REVIEW',
    'REJECTED'
);

-- ── Alert lifecycle status ────────────────────────────────────
-- Used in: alerts
CREATE TYPE alert_status AS ENUM (
    'NEW',
    'INVESTIGATING',
    'FLAGGED',
    'VERIFIED',
    'CLOSED'
);

-- ── Human review status ───────────────────────────────────────
-- Used in: human_reviews
CREATE TYPE review_status AS ENUM (
    'PENDING',
    'CONFIRMED',
    'REJECTED',
    'UNKNOWN'
);

-- ── Thermal object lifecycle status ──────────────────────────
-- Used in: thermal_objects
CREATE TYPE thermal_object_status AS ENUM (
    'ACTIVE',
    'COOLING',
    'EXTINGUISHED',
    'PERSISTENT',
    'UNKNOWN'
);

-- ── Alert priority ────────────────────────────────────────────
-- Used in: alerts
CREATE TYPE alert_priority AS ENUM (
    'CRITICAL',
    'HIGH',
    'MEDIUM',
    'LOW',
    'INFORMATIONAL'
);

DO $$
BEGIN
  RAISE NOTICE 'Migration 001: ENUMs created successfully.';
END $$;
