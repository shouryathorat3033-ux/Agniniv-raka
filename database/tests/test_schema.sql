-- =============================================================
-- HEATWATCH — Schema Tests
-- database/tests/test_schema.sql
-- =============================================================
-- Verifies that all 17 required tables and key views exist.
-- Returns PASS/FAIL per check.
-- Safe to run on any environment (read-only checks).
-- =============================================================

\set ON_ERROR_STOP on

DO $$
DECLARE
    required_tables TEXT[] := ARRAY[
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
    ];
    required_views TEXT[] := ARRAY[
        'v_active_thermal_objects',
        'v_alert_dashboard',
        'v_training_candidates',
        'v_open_alerts_spatial',
        'v_human_review_queue'
    ];
    tbl TEXT;
    vw  TEXT;
    pass_count INTEGER := 0;
    fail_count INTEGER := 0;
BEGIN
    -- Check tables
    FOREACH tbl IN ARRAY required_tables LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name   = tbl
              AND table_type   = 'BASE TABLE'
        ) THEN
            RAISE NOTICE 'PASS — Table exists: %', tbl;
            pass_count := pass_count + 1;
        ELSE
            RAISE WARNING 'FAIL — Table MISSING: %', tbl;
            fail_count := fail_count + 1;
        END IF;
    END LOOP;

    -- Check views
    FOREACH vw IN ARRAY required_views LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'public'
              AND table_name   = vw
        ) THEN
            RAISE NOTICE 'PASS — View exists: %', vw;
            pass_count := pass_count + 1;
        ELSE
            RAISE WARNING 'FAIL — View MISSING: %', vw;
            fail_count := fail_count + 1;
        END IF;
    END LOOP;

    RAISE NOTICE '============================';
    RAISE NOTICE 'Schema test results: % PASS, % FAIL', pass_count, fail_count;

    IF fail_count > 0 THEN
        RAISE EXCEPTION 'Schema test FAILED: % objects are missing.', fail_count;
    END IF;
END $$;


-- =============================================================
-- Column existence checks for critical tables
-- =============================================================

DO $$
DECLARE
    checks TEXT[][] := ARRAY[
        -- table, column
        ARRAY['hotspots',        'location'],
        ARRAY['hotspots',        'acquisition_time'],
        ARRAY['hotspots',        'frp'],
        ARRAY['thermal_objects', 'centroid'],
        ARRAY['thermal_objects', 'duration_hours'],
        ARRAY['thermal_objects', 'persistence_score'],
        ARRAY['rag_chunks',      'embedding'],
        ARRAY['verified_events', 'eligible_for_training'],
        ARRAY['human_reviews',   'original_prediction']
    ];
    pair TEXT[];
    pass_count INTEGER := 0;
    fail_count INTEGER := 0;
BEGIN
    FOREACH pair SLICE 1 IN ARRAY checks LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = pair[1]
              AND column_name  = pair[2]
        ) THEN
            RAISE NOTICE 'PASS — Column %.% exists', pair[1], pair[2];
            pass_count := pass_count + 1;
        ELSE
            RAISE WARNING 'FAIL — Column %.% MISSING', pair[1], pair[2];
            fail_count := fail_count + 1;
        END IF;
    END LOOP;

    RAISE NOTICE '============================';
    RAISE NOTICE 'Column test results: % PASS, % FAIL', pass_count, fail_count;

    IF fail_count > 0 THEN
        RAISE EXCEPTION 'Column test FAILED.';
    END IF;
END $$;
