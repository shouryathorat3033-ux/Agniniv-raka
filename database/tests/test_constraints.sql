-- =============================================================
-- HEATWATCH — Constraint Tests
-- database/tests/test_constraints.sql
-- =============================================================
-- Tests that database constraints correctly reject invalid data.
-- Each test attempts an invalid INSERT and expects it to fail.
-- PASS = the invalid data was rejected.
-- FAIL = the invalid data was accepted (constraint broken).
-- =============================================================

\set ON_ERROR_STOP off

-- =============================================================
-- Helper: count PASS/FAIL
-- =============================================================
CREATE TEMP TABLE IF NOT EXISTS constraint_test_results (
    test_name TEXT,
    result    TEXT,
    detail    TEXT
);

-- =============================================================
-- TEST 1: Invalid latitude (out of range)
-- =============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO hotspots
            (source, latitude, longitude, location, acquisition_time, confidence)
        VALUES (
            'MODIS_TERRA',
            999.0,     -- INVALID: latitude > 90
            77.0,
            ST_SetSRID(ST_MakePoint(77.0, 91.0), 4326),
            NOW(),
            'nominal'
        );
        INSERT INTO constraint_test_results VALUES
            ('invalid_latitude', 'FAIL', 'Invalid latitude was accepted — CHECK constraint broken');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('invalid_latitude', 'PASS', 'Invalid latitude correctly rejected');
    END;
END $$;

-- =============================================================
-- TEST 2: Invalid longitude (out of range)
-- =============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO hotspots
            (source, latitude, longitude, location, acquisition_time, confidence)
        VALUES (
            'MODIS_TERRA',
            28.0,
            999.0,     -- INVALID: longitude > 180
            ST_SetSRID(ST_MakePoint(181.0, 28.0), 4326),
            NOW(),
            'nominal'
        );
        INSERT INTO constraint_test_results VALUES
            ('invalid_longitude', 'FAIL', 'Invalid longitude was accepted — CHECK constraint broken');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('invalid_longitude', 'PASS', 'Invalid longitude correctly rejected');
    END;
END $$;

-- =============================================================
-- TEST 3: Invalid confidence score > 1.0 on source_attributions
-- =============================================================
DO $$
DECLARE
    fake_obj_id UUID := uuid_generate_v4();
BEGIN
    -- Insert a minimal thermal object
    INSERT INTO thermal_objects (id, centroid, first_seen, last_seen)
    VALUES (
        fake_obj_id,
        ST_SetSRID(ST_MakePoint(77.0, 28.0), 4326),
        NOW(), NOW()
    );

    BEGIN
        INSERT INTO source_attributions
            (thermal_object_id, predicted_category, confidence, model_version)
        VALUES (
            fake_obj_id,
            'INDUSTRIAL_FIRE',
            1.5,    -- INVALID: confidence > 1.0
            'test_v1'
        );
        INSERT INTO constraint_test_results VALUES
            ('confidence_over_1', 'FAIL', 'confidence=1.5 was accepted — CHECK constraint broken');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('confidence_over_1', 'PASS', 'confidence=1.5 correctly rejected');
    END;

    -- Cleanup
    DELETE FROM thermal_objects WHERE id = fake_obj_id;
END $$;

-- =============================================================
-- TEST 4: Invalid confidence score < 0.0
-- =============================================================
DO $$
DECLARE
    fake_obj_id UUID := uuid_generate_v4();
BEGIN
    INSERT INTO thermal_objects (id, centroid, first_seen, last_seen)
    VALUES (
        fake_obj_id,
        ST_SetSRID(ST_MakePoint(77.0, 28.0), 4326),
        NOW(), NOW()
    );

    BEGIN
        INSERT INTO source_attributions
            (thermal_object_id, predicted_category, confidence, model_version)
        VALUES (fake_obj_id, 'INDUSTRIAL_FIRE', -0.1, 'test_v1');
        INSERT INTO constraint_test_results VALUES
            ('confidence_negative', 'FAIL', 'Negative confidence was accepted');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('confidence_negative', 'PASS', 'Negative confidence correctly rejected');
    END;

    DELETE FROM thermal_objects WHERE id = fake_obj_id;
END $$;

-- =============================================================
-- TEST 5: thermal_object first_seen > last_seen
-- =============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO thermal_objects (centroid, first_seen, last_seen)
        VALUES (
            ST_SetSRID(ST_MakePoint(77.0, 28.0), 4326),
            NOW(),
            NOW() - INTERVAL '1 hour'  -- INVALID: first_seen > last_seen
        );
        INSERT INTO constraint_test_results VALUES
            ('time_order', 'FAIL', 'first_seen > last_seen was accepted');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('time_order', 'PASS', 'first_seen > last_seen correctly rejected');
    END;
END $$;

-- =============================================================
-- TEST 6: Duplicate hotspot (same source+lat+lon+time)
-- =============================================================
DO $$
DECLARE
    test_time TIMESTAMPTZ := '2025-06-15 12:00:00+00';
BEGIN
    -- Insert first hotspot
    INSERT INTO hotspots
        (source, latitude, longitude, location, acquisition_time, confidence)
    VALUES (
        'MODIS_TERRA', 22.5, 73.5,
        ST_SetSRID(ST_MakePoint(73.5, 22.5), 4326),
        test_time, 'nominal'
    )
    ON CONFLICT DO NOTHING;

    BEGIN
        -- Try to insert duplicate
        INSERT INTO hotspots
            (source, latitude, longitude, location, acquisition_time, confidence)
        VALUES (
            'MODIS_TERRA', 22.5, 73.5,
            ST_SetSRID(ST_MakePoint(73.5, 22.5), 4326),
            test_time, 'nominal'
        );
        INSERT INTO constraint_test_results VALUES
            ('duplicate_hotspot', 'FAIL', 'Duplicate hotspot was accepted — UNIQUE constraint broken');
    EXCEPTION WHEN unique_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('duplicate_hotspot', 'PASS', 'Duplicate hotspot correctly rejected');
    END;

    -- Cleanup
    DELETE FROM hotspots
    WHERE source = 'MODIS_TERRA'
      AND latitude = 22.5 AND longitude = 73.5
      AND acquisition_time = test_time;
END $$;

-- =============================================================
-- TEST 7: Orphan FK — human_review referencing non-existent thermal_object
-- =============================================================
DO $$
BEGIN
    BEGIN
        INSERT INTO human_reviews
            (thermal_object_id, original_prediction, review_status)
        VALUES (
            uuid_generate_v4(),  -- Non-existent FK
            'INDUSTRIAL_FIRE',
            'PENDING'
        );
        INSERT INTO constraint_test_results VALUES
            ('fk_human_review', 'FAIL', 'Orphan FK accepted in human_reviews');
    EXCEPTION WHEN foreign_key_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('fk_human_review', 'PASS', 'Orphan FK correctly rejected in human_reviews');
    END;
END $$;

-- =============================================================
-- TEST 8: land_context score out of range (> 1.0)
-- =============================================================
DO $$
DECLARE
    fake_obj_id UUID := uuid_generate_v4();
BEGIN
    INSERT INTO thermal_objects (id, centroid, first_seen, last_seen)
    VALUES (fake_obj_id, ST_SetSRID(ST_MakePoint(77.0, 28.0), 4326), NOW(), NOW());

    BEGIN
        INSERT INTO land_context
            (thermal_object_id, land_cover_source, built_up_score)
        VALUES (fake_obj_id, 'TEST_SOURCE', 1.5);  -- INVALID: > 1.0
        INSERT INTO constraint_test_results VALUES
            ('land_score_range', 'FAIL', 'Land score > 1.0 was accepted');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO constraint_test_results VALUES
            ('land_score_range', 'PASS', 'Land score > 1.0 correctly rejected');
    END;

    DELETE FROM thermal_objects WHERE id = fake_obj_id;
END $$;

-- =============================================================
-- Results summary
-- =============================================================
SELECT
    test_name,
    result,
    detail
FROM constraint_test_results
ORDER BY test_name;

SELECT
    COUNT(CASE WHEN result = 'PASS' THEN 1 END) AS pass_count,
    COUNT(CASE WHEN result = 'FAIL' THEN 1 END) AS fail_count
FROM constraint_test_results;

DROP TABLE constraint_test_results;
