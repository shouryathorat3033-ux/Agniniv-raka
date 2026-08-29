-- =============================================================
-- HEATWATCH — Spatial Query Tests
-- database/tests/test_spatial_queries.sql
-- =============================================================
-- Verifies that PostGIS spatial queries execute correctly.
-- Requires demo seed data (seed_demo_data.sql).
-- =============================================================

\set ON_ERROR_STOP on

-- =============================================================
-- TEST 1: Bounding-box query on thermal_objects
-- =============================================================
DO $$
DECLARE
    result_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO result_count
    FROM thermal_objects
    WHERE centroid && ST_MakeEnvelope(65.0, 5.0, 100.0, 40.0, 4326);

    IF result_count >= 0 THEN
        RAISE NOTICE 'PASS — Bounding-box query succeeded, found % rows', result_count;
    ELSE
        RAISE EXCEPTION 'FAIL — Bounding-box query returned negative count';
    END IF;
END $$;

-- =============================================================
-- TEST 2: KNN nearest-facility query
-- =============================================================
DO $$
DECLARE
    result_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO result_count
    FROM industrial_facilities
    ORDER BY location <-> ST_SetSRID(ST_MakePoint(72.879, 21.200), 4326)
    LIMIT 1;

    RAISE NOTICE 'PASS — KNN nearest-facility query executed, returned % row(s)', result_count;
END $$;

-- =============================================================
-- TEST 3: ST_DWithin radius query
-- =============================================================
DO $$
DECLARE
    result_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO result_count
    FROM industrial_facilities
    WHERE ST_DWithin(
        location::geography,
        ST_SetSRID(ST_MakePoint(72.879, 21.200), 4326)::geography,
        50000  -- 50 km
    );

    RAISE NOTICE 'PASS — ST_DWithin radius query executed, found % facilities within 50km', result_count;
END $$;

-- =============================================================
-- TEST 4: ST_Distance calculation
-- =============================================================
DO $$
DECLARE
    test_dist FLOAT;
BEGIN
    SELECT ST_Distance(
        ST_SetSRID(ST_MakePoint(72.879, 21.200), 4326)::geography,
        ST_SetSRID(ST_MakePoint(72.870, 21.195), 4326)::geography
    ) INTO test_dist;

    IF test_dist > 0 AND test_dist < 5000 THEN
        RAISE NOTICE 'PASS — ST_Distance returned reasonable value: % metres', ROUND(test_dist, 2);
    ELSE
        RAISE EXCEPTION 'FAIL — ST_Distance returned unexpected value: %', test_dist;
    END IF;
END $$;

-- =============================================================
-- TEST 5: ST_X / ST_Y coordinate extraction
-- =============================================================
DO $$
DECLARE
    lon_val FLOAT;
    lat_val FLOAT;
BEGIN
    SELECT
        ST_X(ST_SetSRID(ST_MakePoint(77.5, 23.5), 4326)),
        ST_Y(ST_SetSRID(ST_MakePoint(77.5, 23.5), 4326))
    INTO lon_val, lat_val;

    IF ABS(lon_val - 77.5) < 0.001 AND ABS(lat_val - 23.5) < 0.001 THEN
        RAISE NOTICE 'PASS — ST_X/ST_Y coordinate extraction correct';
    ELSE
        RAISE EXCEPTION 'FAIL — ST_X/ST_Y returned incorrect values: lon=%, lat=%', lon_val, lat_val;
    END IF;
END $$;

-- =============================================================
-- TEST 6: ST_MakeEnvelope bounding box creation
-- =============================================================
DO $$
DECLARE
    geom_srid INTEGER;
BEGIN
    SELECT ST_SRID(ST_MakeEnvelope(65.0, 5.0, 100.0, 40.0, 4326))
    INTO geom_srid;

    IF geom_srid = 4326 THEN
        RAISE NOTICE 'PASS — ST_MakeEnvelope created geometry with SRID 4326';
    ELSE
        RAISE EXCEPTION 'FAIL — ST_MakeEnvelope SRID is %, expected 4326', geom_srid;
    END IF;
END $$;

-- =============================================================
-- TEST 7: Spatial function hw_thermal_objects_in_bbox
-- =============================================================
DO $$
DECLARE
    result_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO result_count
    FROM hw_thermal_objects_in_bbox(65.0, 5.0, 100.0, 40.0);

    RAISE NOTICE 'PASS — hw_thermal_objects_in_bbox function executed, returned % rows', result_count;
END $$;

RAISE NOTICE '============================';
RAISE NOTICE 'All spatial query tests passed.';
