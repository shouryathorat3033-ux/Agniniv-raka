-- =============================================================
-- Migration 000 — Enable Extensions
-- HEATWATCH Database
-- =============================================================
-- Safe to re-run (IF NOT EXISTS).
-- Must be run by a superuser or a user with CREATEROLE privilege.
-- Run BEFORE all other migrations.
-- =============================================================

-- PostGIS: geometry, geography, spatial indexes (GiST)
CREATE EXTENSION IF NOT EXISTS postgis;

-- PostGIS topology (raster + topology support — optional but recommended)
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- pgvector: vector type + ANN indexes for RAG embeddings
-- If not installed on this server, comment out and set
-- PGVECTOR_AVAILABLE=false in your environment.
CREATE EXTENSION IF NOT EXISTS vector;

-- UUID generation helper (uuid_generate_v4)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- GiST support for exclusion constraints (e.g., prevent overlapping ranges)
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Verify installations
DO $$
DECLARE
  ext_name TEXT;
  ext_list TEXT[] := ARRAY['postgis', 'vector', 'uuid-ossp'];
BEGIN
  FOREACH ext_name IN ARRAY ext_list LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_extension WHERE extname = ext_name
    ) THEN
      RAISE EXCEPTION 'Extension "%" failed to install. '
        'Check that it is available on this PostgreSQL server.', ext_name;
    END IF;
  END LOOP;
  RAISE NOTICE 'All required extensions are installed.';
END $$;
