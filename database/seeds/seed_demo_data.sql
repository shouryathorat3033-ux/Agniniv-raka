-- =============================================================
-- HEATWATCH — Full Demo Data Seed
-- database/seeds/seed_demo_data.sql
-- =============================================================
-- ⚠  DEMO DATA ONLY — NOT REAL SATELLITE OBSERVATIONS
-- All data is fictional for development and demonstration.
-- Run AFTER migrations 000–009 and seed_industrial_facilities.sql
-- =============================================================

BEGIN;

DO $$
BEGIN
    IF current_database() = 'heatwatch_prod' THEN
        RAISE EXCEPTION 'Seed data must NOT be loaded into production. Aborting.';
    END IF;
END $$;

-- Clean up existing demo data (safe for dev reset)
DELETE FROM alerts         WHERE title LIKE 'DEMO%';
DELETE FROM anomaly_results WHERE model_version = 'DEMO_v1';
DELETE FROM source_attributions WHERE model_version = 'DEMO_v1';
DELETE FROM thermal_object_observations
    WHERE thermal_object_id IN (
        SELECT id FROM thermal_objects WHERE cluster_algorithm = 'DEMO_SEED'
    );
DELETE FROM hotspots WHERE source = 'DEMO_SEED';
DELETE FROM thermal_objects WHERE cluster_algorithm = 'DEMO_SEED';
DELETE FROM model_registry WHERE model_name = 'DEMO_Brain1';
DELETE FROM rag_documents  WHERE source = 'DEMO_SEED';

-- =============================================================
-- 1. Demo Model Registry Entry
-- =============================================================
INSERT INTO model_registry
    (id, model_name, model_type, version, is_active,
     metrics, parameters, artifact_location)
VALUES
(
    'a0000000-0000-0000-0000-000000000001'::uuid,
    'DEMO_Brain1',
    'SOURCE_ATTRIBUTION',
    'DEMO_v1',
    FALSE,
    '{"accuracy": 0.88, "f1_macro": 0.85}'::jsonb,
    '{"n_estimators": 200, "max_depth": 6}'::jsonb,
    's3://heatwatch-models-demo/brain1/demo_v1/'
);

-- =============================================================
-- 2. Demo Hotspots
-- =============================================================

-- Demo hotspot A — near Gujarat refinery (industrial area)
WITH ins_h1 AS (
    INSERT INTO hotspots
        (id, source, latitude, longitude, location,
         acquisition_time, satellite, instrument, confidence,
         brightness, frp, daynight)
    VALUES (
        'b0000000-0000-0000-0000-000000000001'::uuid,
        'DEMO_SEED',
        21.202, 72.878,
        ST_SetSRID(ST_MakePoint(72.878, 21.202), 4326),
        NOW() - INTERVAL '2 hours',
        'DEMO-SAT-1', 'DEMO-VIIRS',
        'high', 345.2, 187.5, 'D'
    )
    ON CONFLICT DO NOTHING
    RETURNING id
)
SELECT id FROM ins_h1;

-- Demo hotspot B — same area, different pass
INSERT INTO hotspots
    (id, source, latitude, longitude, location,
     acquisition_time, satellite, instrument, confidence,
     brightness, frp, daynight)
VALUES (
    'b0000000-0000-0000-0000-000000000002'::uuid,
    'DEMO_SEED',
    21.198, 72.881,
    ST_SetSRID(ST_MakePoint(72.881, 21.198), 4326),
    NOW() - INTERVAL '6 hours',
    'DEMO-SAT-2', 'DEMO-MODIS',
    'nominal', 328.1, 142.3, 'D'
)
ON CONFLICT DO NOTHING;

-- Demo hotspot C — forest fire scenario (Kerala)
INSERT INTO hotspots
    (id, source, latitude, longitude, location,
     acquisition_time, satellite, instrument, confidence,
     brightness, frp, daynight)
VALUES (
    'b0000000-0000-0000-0000-000000000003'::uuid,
    'DEMO_SEED',
    10.850, 76.270,
    ST_SetSRID(ST_MakePoint(76.270, 10.850), 4326),
    NOW() - INTERVAL '3 hours',
    'DEMO-SAT-1', 'DEMO-VIIRS',
    'high', 312.7, 55.2, 'D'
)
ON CONFLICT DO NOTHING;

-- =============================================================
-- 3. Demo Thermal Objects
-- =============================================================

-- Thermal object 1 — Industrial cluster (Gujarat refinery area)
INSERT INTO thermal_objects
    (id, centroid, object_geometry, first_seen, last_seen,
     observation_count, persistence_score, status,
     cluster_algorithm, cluster_params)
VALUES (
    'c0000000-0000-0000-0000-000000000001'::uuid,
    ST_SetSRID(ST_MakePoint(72.879, 21.200), 4326),
    ST_Buffer(
        ST_SetSRID(ST_MakePoint(72.879, 21.200), 4326)::geography,
        800
    )::geometry,
    NOW() - INTERVAL '72 hours',
    NOW() - INTERVAL '2 hours',
    2,
    0.82,
    'PERSISTENT',
    'DEMO_SEED',
    '{"eps_km": 2.0, "min_pts": 3}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Thermal object 2 — Forest fire cluster (Kerala)
INSERT INTO thermal_objects
    (id, centroid, first_seen, last_seen, observation_count,
     persistence_score, status, cluster_algorithm)
VALUES (
    'c0000000-0000-0000-0000-000000000002'::uuid,
    ST_SetSRID(ST_MakePoint(76.270, 10.850), 4326),
    NOW() - INTERVAL '5 hours',
    NOW() - INTERVAL '3 hours',
    1,
    0.25,
    'ACTIVE',
    'DEMO_SEED'
)
ON CONFLICT DO NOTHING;

-- =============================================================
-- 4. Link Hotspots → Thermal Objects
-- =============================================================

INSERT INTO thermal_object_observations (thermal_object_id, hotspot_id)
VALUES
    ('c0000000-0000-0000-0000-000000000001'::uuid,
     'b0000000-0000-0000-0000-000000000001'::uuid),
    ('c0000000-0000-0000-0000-000000000001'::uuid,
     'b0000000-0000-0000-0000-000000000002'::uuid),
    ('c0000000-0000-0000-0000-000000000002'::uuid,
     'b0000000-0000-0000-0000-000000000003'::uuid)
ON CONFLICT DO NOTHING;

-- =============================================================
-- 5. Demo Source Attributions (Brain 1 Results)
-- =============================================================

INSERT INTO source_attributions
    (id, thermal_object_id, predicted_category, confidence,
     evidence_score, model_version, evidence)
VALUES
(
    'd0000000-0000-0000-0000-000000000001'::uuid,
    'c0000000-0000-0000-0000-000000000001'::uuid,
    'PERSISTENT_THERMAL_SOURCE',
    0.91,
    78.5,
    'DEMO_v1',
    '{"nearest_facility_m": 320, "built_up_fraction": 0.75, "demo": true}'::jsonb
),
(
    'd0000000-0000-0000-0000-000000000002'::uuid,
    'c0000000-0000-0000-0000-000000000002'::uuid,
    'FOREST_FIRE',
    0.78,
    62.1,
    'DEMO_v1',
    '{"tree_cover_fraction": 0.82, "nearest_facility_m": 8500, "demo": true}'::jsonb
)
ON CONFLICT DO NOTHING;

-- =============================================================
-- 6. Demo Anomaly Results (Brain 2 Results)
-- =============================================================

INSERT INTO anomaly_results
    (id, thermal_object_id, anomaly_level, anomaly_score,
     frp_anomaly, temporal_anomaly, model_version, evidence)
VALUES
(
    'e0000000-0000-0000-0000-000000000001'::uuid,
    'c0000000-0000-0000-0000-000000000001'::uuid,
    'HIGH',
    0.87,
    TRUE, FALSE,
    'DEMO_v1',
    '{"frp_z_score": 3.2, "note": "DEMO anomaly result"}'::jsonb
),
(
    'e0000000-0000-0000-0000-000000000002'::uuid,
    'c0000000-0000-0000-0000-000000000002'::uuid,
    'ELEVATED',
    0.54,
    FALSE, FALSE,
    'DEMO_v1',
    '{"frp_z_score": 1.8, "note": "DEMO anomaly result"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- =============================================================
-- 7. Demo Alerts
-- =============================================================

INSERT INTO alerts
    (id, thermal_object_id, source_attribution_id,
     anomaly_result_id, priority, severity, status, title, description)
VALUES
(
    'f0000000-0000-0000-0000-000000000001'::uuid,
    'c0000000-0000-0000-0000-000000000001'::uuid,
    'd0000000-0000-0000-0000-000000000001'::uuid,
    'e0000000-0000-0000-0000-000000000001'::uuid,
    'HIGH',
    'HIGH',
    'NEW',
    'DEMO — Persistent High-FRP Industrial Thermal Source',
    'Demo alert: Persistent thermal anomaly detected near industrial facility. FRP > 180 MW for 72h.'
),
(
    'f0000000-0000-0000-0000-000000000002'::uuid,
    'c0000000-0000-0000-0000-000000000002'::uuid,
    'd0000000-0000-0000-0000-000000000002'::uuid,
    'e0000000-0000-0000-0000-000000000002'::uuid,
    'MEDIUM',
    'MEDIUM',
    'NEW',
    'DEMO — Potential Forest Fire — Western Ghats',
    'Demo alert: Single hotspot detection in high tree-cover area. Elevation monitoring required.'
)
ON CONFLICT DO NOTHING;

-- =============================================================
-- 8. Demo RAG Document
-- =============================================================

INSERT INTO rag_documents
    (id, title, source, source_type, content, version, metadata)
VALUES (
    '00000000-rag0-0000-0000-000000000001'::uuid,
    'DEMO — Industrial Flaring Classification Policy',
    'DEMO_SEED',
    'CLASSIFICATION_POLICY',
    'This is a demo policy document for HEATWATCH development. '
    'Gas flaring is defined as the controlled combustion of associated petroleum gas. '
    'Key indicators: persistent thermal source, proximity to oil/gas infrastructure, '
    'stable spatial footprint, night-time activity consistent with 24/7 operations.',
    '1',
    '{"demo": true, "topic": "gas_flare"}'::jsonb
)
ON CONFLICT DO NOTHING;

COMMIT;

-- =============================================================
-- Verification summary
-- =============================================================
SELECT
    (SELECT COUNT(*) FROM hotspots         WHERE source = 'DEMO_SEED')    AS demo_hotspots,
    (SELECT COUNT(*) FROM thermal_objects  WHERE cluster_algorithm = 'DEMO_SEED') AS demo_thermal_objects,
    (SELECT COUNT(*) FROM source_attributions WHERE model_version = 'DEMO_v1') AS demo_attributions,
    (SELECT COUNT(*) FROM anomaly_results  WHERE model_version = 'DEMO_v1') AS demo_anomaly_results,
    (SELECT COUNT(*) FROM alerts           WHERE title LIKE 'DEMO%')       AS demo_alerts,
    (SELECT COUNT(*) FROM rag_documents    WHERE source = 'DEMO_SEED')     AS demo_rag_docs;
