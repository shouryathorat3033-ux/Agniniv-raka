-- =============================================================
-- HEATWATCH — Demo Land Context Seed Data
-- database/seeds/seed_land_context.sql
-- =============================================================
-- ⚠  DEMO DATA ONLY — requires demo thermal objects to exist.
-- Run seed_demo_data.sql FIRST to create demo thermal objects.
-- =============================================================

BEGIN;

DO $$
BEGIN
    IF current_database() = 'heatwatch_prod' THEN
        RAISE EXCEPTION 'Seed data must NOT be loaded into production. Aborting.';
    END IF;
END $$;

-- Insert land context for any demo thermal objects that exist
-- Uses a subquery to get all demo-seeded thermal object IDs
INSERT INTO land_context
    (thermal_object_id, land_cover_class, land_cover_source,
     resolution_meters, built_up_score, cropland_score, tree_cover_score,
     shrubland_score, grassland_score, water_score, bare_land_score, metadata)
SELECT
    t.id,
    class_data.land_cover_class,
    class_data.source,
    class_data.resolution_m,
    class_data.built_up,
    class_data.cropland,
    class_data.tree_cover,
    class_data.shrubland,
    class_data.grassland,
    class_data.water,
    class_data.bare_land,
    jsonb_build_object('demo', true, 'dataset_year', 2023)
FROM thermal_objects t
CROSS JOIN (
    VALUES
        -- Industrial zone profile
        ('Industrial_Zone', 'ESA_WorldCover_2021', 10, 0.75, 0.05, 0.05, 0.02, 0.03, 0.02, 0.08)
) AS class_data(
    land_cover_class, source, resolution_m,
    built_up, cropland, tree_cover, shrubland, grassland, water, bare_land
)
WHERE t.cluster_algorithm = 'DEMO_SEED'
ON CONFLICT (thermal_object_id, land_cover_source) DO NOTHING;

COMMIT;

SELECT COUNT(*) AS demo_land_contexts_inserted
FROM land_context
WHERE metadata @> '{"demo": true}';
