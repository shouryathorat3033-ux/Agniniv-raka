-- =============================================================
-- HEATWATCH — Maintenance Functions
-- database/functions/maintenance_functions.sql
-- =============================================================
-- Database maintenance utilities.
-- SCOPE: DB maintenance ONLY.
-- No satellite processing, ML, or business logic.
-- =============================================================

-- =============================================================
-- FUNCTION: trigger_set_updated_at
-- Auto-maintain updated_at on UPDATE.
-- =============================================================
-- Already created in migration 002 but re-defined here
-- with CREATE OR REPLACE for standalone execution.
-- =============================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION trigger_set_updated_at IS
    'Trigger function: sets updated_at to CURRENT_TIMESTAMP on row update. '
    'Used by all tables that have an updated_at column.';


-- =============================================================
-- FUNCTION: hw_table_row_counts
-- Returns row counts for all HEATWATCH tables.
-- Useful for health checks and data quality audits.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_table_row_counts()
RETURNS TABLE (
    table_name TEXT,
    row_count  BIGINT
) LANGUAGE sql STABLE AS $$
    SELECT relname::TEXT, reltuples::BIGINT
    FROM pg_class
    WHERE relkind = 'r'
      AND relname IN (
          'hotspots',
          'thermal_objects',
          'thermal_object_observations',
          'industrial_facilities',
          'osm_context',
          'land_context',
          'historical_profiles',
          'feature_vectors',
          'source_attributions',
          'anomaly_results',
          'supervisor_reviews',
          'alerts',
          'human_reviews',
          'verified_events',
          'rag_documents',
          'rag_chunks',
          'model_registry'
      )
    ORDER BY relname;
$$;

COMMENT ON FUNCTION hw_table_row_counts IS
    'Returns estimated row counts for all HEATWATCH tables. '
    'Uses pg_class.reltuples (approximate; updated by ANALYZE). '
    'For exact counts, use COUNT(*) per table.';


-- =============================================================
-- FUNCTION: hw_cleanup_orphaned_osm_context
-- Remove OSM context rows whose parent thermal_object is gone.
-- =============================================================
-- Note: ON DELETE CASCADE handles most cases at insert time.
-- This function is a safety net for manual cleanups or
-- bulk data corrections.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_cleanup_orphaned_osm_context()
RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM osm_context
    WHERE thermal_object_id NOT IN (SELECT id FROM thermal_objects);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'hw_cleanup_orphaned_osm_context: deleted % rows.', deleted_count;
    RETURN deleted_count;
END;
$$;

COMMENT ON FUNCTION hw_cleanup_orphaned_osm_context IS
    'Safety cleanup: removes osm_context rows with no matching thermal_object. '
    'ON DELETE CASCADE handles normal cases. Call this only after bulk corrections.';


-- =============================================================
-- FUNCTION: hw_archive_old_hotspots
-- Returns IDs of hotspots older than a retention threshold
-- for archival by an external process.
-- =============================================================
-- DESIGN: This function identifies candidates only.
-- The actual archival (move to cold storage / delete) is the
-- responsibility of the external data retention process.
-- The database does NOT automatically delete production data.
-- =============================================================

CREATE OR REPLACE FUNCTION hw_archive_candidates(
    p_older_than_days INTEGER DEFAULT 365
)
RETURNS TABLE (
    hotspot_id   UUID,
    acquired_at  TIMESTAMPTZ,
    source       TEXT
) LANGUAGE sql STABLE AS $$
    SELECT
        id,
        acquisition_time,
        source
    FROM hotspots
    WHERE acquisition_time < NOW() - (p_older_than_days || ' days')::INTERVAL
    ORDER BY acquisition_time;
$$;

COMMENT ON FUNCTION hw_archive_candidates IS
    'Returns hotspot IDs older than p_older_than_days for external archival. '
    'Does NOT delete data. Archival must be performed by an external process.';


-- =============================================================
-- VIEW: hw_index_usage
-- Monitor index hit rates for performance tuning.
-- =============================================================

CREATE OR REPLACE VIEW hw_index_usage AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan        AS index_scans,
    idx_tup_read    AS tuples_read,
    idx_tup_fetch   AS tuples_fetched,
    CASE WHEN idx_scan = 0 THEN 'UNUSED'
         WHEN idx_scan < 100 THEN 'LOW_USE'
         ELSE 'ACTIVE'
    END AS usage_status
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

COMMENT ON VIEW hw_index_usage IS
    'Monitor index scan counts for performance tuning. '
    'UNUSED indexes are candidates for removal after sufficient observation time.';
