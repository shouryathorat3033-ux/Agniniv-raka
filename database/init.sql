-- =============================================================
-- HEATWATCH — Database Bootstrap Entry Point
-- database/init.sql
-- =============================================================
-- This file documents the correct initialization order.
-- PostgreSQL does NOT automatically execute files from subdirectories.
--
-- To initialize the full database, use ONE of these methods:
--
-- METHOD 1 — Recommended (shell script):
--   bash database/scripts/migrate.sh
--
-- METHOD 2 — Manual psql (Windows PowerShell compatible):
--   Set-Item Env:PGPASSWORD "your_password"
--   $DB = "postgresql://user:pass@localhost:5432/heatwatch"
--   @(
--     "000_enable_extensions.sql",
--     "001_create_enums.sql",
--     "002_create_core_tables.sql",
--     "003_create_context_tables.sql",
--     "004_create_ai_result_tables.sql",
--     "005_create_feedback_tables.sql",
--     "006_create_rag_tables.sql",
--     "007_create_model_registry.sql",
--     "008_create_indexes.sql",
--     "009_create_views.sql"
--   ) | ForEach-Object {
--     psql $DB -f "migrations/$_"
--     if ($LASTEXITCODE -ne 0) { throw "Failed: $_" }
--   }
--   # Load functions
--   psql $DB -f "functions/spatial_functions.sql"
--   psql $DB -f "functions/maintenance_functions.sql"
--
-- METHOD 3 — Docker auto-init:
--   Uncomment the volume mount in docker-compose.yml:
--     - ./init.sql:/docker-entrypoint-initdb.d/00_init.sql:ro
--   The file below will run on first container start.
--   LIMITATION: it cannot use \i to include other files in the
--   Docker entrypoint context. You must still run migrate.sh
--   after the container starts.
-- =============================================================

-- Minimal bootstrap to verify connectivity:
SELECT version() AS postgresql_version;

SELECT
    extname AS extension,
    extversion AS version
FROM pg_extension
WHERE extname IN ('postgis', 'vector', 'uuid-ossp')
ORDER BY extname;

-- After running this file, proceed with:
--   bash database/scripts/migrate.sh
