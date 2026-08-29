-- =============================================================
-- HEATWATCH — Demo Industrial Facilities Seed Data
-- database/seeds/seed_industrial_facilities.sql
-- =============================================================
-- ⚠  DEMO DATA ONLY — NOT REAL OPERATIONAL DATA
-- These are fictional/illustrative facilities for development,
-- testing, and demonstration purposes.
-- Do NOT run on production databases with real incident data.
-- =============================================================

BEGIN;

-- Guard: only run in non-production environments
DO $$
BEGIN
    IF current_database() = 'heatwatch_prod' THEN
        RAISE EXCEPTION
            'Seed data must NOT be loaded into the production database (heatwatch_prod). Aborting.';
    END IF;
END $$;

-- Clear existing demo data (safe for dev/test reset)
-- This will cascade to related tables.
DELETE FROM industrial_facilities WHERE source = 'DEMO_SEED';

-- =============================================================
-- Insert demo industrial facilities
-- Coordinates are approximate/illustrative only.
-- =============================================================

INSERT INTO industrial_facilities
    (id, name, facility_type, source, source_reference, location, boundary, confidence, metadata)
VALUES

-- Demo Refinery — Coastal India (approximate)
(
    uuid_generate_v4(),
    'DEMO — Coastal Refinery Alpha',
    'REFINERY',
    'DEMO_SEED',
    'DEMO-REF-001',
    ST_SetSRID(ST_MakePoint(72.870, 21.195), 4326),
    NULL,
    0.90,
    '{"country": "IN", "state": "Gujarat", "capacity_bpd": 200000, "demo": true}'::jsonb
),

-- Demo Power Plant — Northern India (approximate)
(
    uuid_generate_v4(),
    'DEMO — Northern Coal Power Station',
    'POWER_PLANT',
    'DEMO_SEED',
    'DEMO-PP-001',
    ST_SetSRID(ST_MakePoint(79.920, 24.410), 4326),
    ST_SetSRID(
        ST_Buffer(ST_MakePoint(79.920, 24.410)::geography, 1500)::geometry,
        4326
    ),
    0.85,
    '{"country": "IN", "state": "Madhya Pradesh", "capacity_mw": 1320, "demo": true}'::jsonb
),

-- Demo Steel Mill — Eastern India (approximate)
(
    uuid_generate_v4(),
    'DEMO — Eastern Steel Works',
    'STEEL_PLANT',
    'DEMO_SEED',
    'DEMO-ST-001',
    ST_SetSRID(ST_MakePoint(85.833, 20.290), 4326),
    NULL,
    0.80,
    '{"country": "IN", "state": "Odisha", "demo": true}'::jsonb
),

-- Demo Gas Flare — Middle East (approximate)
(
    uuid_generate_v4(),
    'DEMO — Desert Gas Processing Complex',
    'PETROCHEMICAL',
    'DEMO_SEED',
    'DEMO-GAS-001',
    ST_SetSRID(ST_MakePoint(47.580, 24.680), 4326),
    NULL,
    0.88,
    '{"country": "SA", "demo": true}'::jsonb
),

-- Demo LNG Terminal — Western India (approximate)
(
    uuid_generate_v4(),
    'DEMO — West Coast LNG Terminal',
    'LNG_TERMINAL',
    'DEMO_SEED',
    'DEMO-LNG-001',
    ST_SetSRID(ST_MakePoint(70.010, 22.310), 4326),
    NULL,
    0.75,
    '{"country": "IN", "state": "Gujarat", "demo": true}'::jsonb
),

-- Demo Mining Site — Central India (approximate)
(
    uuid_generate_v4(),
    'DEMO — Central Coal Mine Area',
    'MINING',
    'DEMO_SEED',
    'DEMO-MIN-001',
    ST_SetSRID(ST_MakePoint(82.210, 22.050), 4326),
    NULL,
    0.70,
    '{"country": "IN", "state": "Chhattisgarh", "demo": true}'::jsonb
),

-- Demo Cement Plant — Southern India (approximate)
(
    uuid_generate_v4(),
    'DEMO — Southern Cement Works',
    'CEMENT',
    'DEMO_SEED',
    'DEMO-CEM-001',
    ST_SetSRID(ST_MakePoint(77.590, 12.310), 4326),
    NULL,
    0.72,
    '{"country": "IN", "state": "Karnataka", "demo": true}'::jsonb
),

-- Demo Chemical Plant — Northern India (approximate)
(
    uuid_generate_v4(),
    'DEMO — Industrial Chemical Complex',
    'CHEMICAL',
    'DEMO_SEED',
    'DEMO-CHM-001',
    ST_SetSRID(ST_MakePoint(76.850, 28.620), 4326),
    NULL,
    0.65,
    '{"country": "IN", "state": "Haryana", "demo": true}'::jsonb
);

COMMIT;

SELECT COUNT(*) AS demo_facilities_inserted
FROM industrial_facilities
WHERE source = 'DEMO_SEED';
