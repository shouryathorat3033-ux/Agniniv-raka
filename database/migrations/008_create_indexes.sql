-- =============================================================
-- Migration 008 — Indexes
-- HEATWATCH Database
-- =============================================================
-- Depends on: 000–007 (all tables must exist)
--
-- Index strategy summary:
--
--   GiST  — spatial columns (PostGIS geometry)
--   HNSW  — vector embedding (pgvector ANN)
--         → Chosen over IVFFlat because:
--           • HNSW does not require a training/list-build step
--           • Better recall at low latency for <5M vectors
--           • Supports incremental inserts without rebuild
--           • IVFFlat requires knowing cardinality upfront
--   B-Tree — timestamps, foreign keys, status/category fields
--   GIN    — JSONB columns where key-existence queries occur
--   BRIN   — append-heavy timestamp columns for cheap range scans
-- =============================================================

-- =============================================================
-- hotspots
-- =============================================================

-- Primary spatial index (map viewport + proximity queries)
CREATE INDEX idx_hotspots_location
    ON hotspots USING GIST (location);

-- Composite: satellite + acquisition time (dashboard time-range queries)
CREATE INDEX idx_hotspots_source_acq_time
    ON hotspots (source, acquisition_time DESC);

-- Standalone acquisition time (broad time-range scans)
-- BRIN is cheap and efficient for append-only time-series
CREATE INDEX idx_hotspots_acq_time_brin
    ON hotspots USING BRIN (acquisition_time);

-- Thermal object membership (denormalised for fast join)
CREATE INDEX idx_hotspots_thermal_object
    ON hotspots (id);  -- covered by PK; documented for clarity

-- Confidence filter
CREATE INDEX idx_hotspots_confidence
    ON hotspots (confidence);

-- =============================================================
-- thermal_objects
-- =============================================================

-- Spatial index on centroid (nearest-neighbour, bounding-box)
CREATE INDEX idx_thermal_objects_centroid
    ON thermal_objects USING GIST (centroid);

-- Spatial index on full object geometry (polygon intersection)
CREATE INDEX idx_thermal_objects_geometry
    ON thermal_objects USING GIST (object_geometry);

-- Status filter (operator dashboard: active objects only)
CREATE INDEX idx_thermal_objects_status
    ON thermal_objects (status)
    WHERE status = 'ACTIVE';

-- Recent last_seen (hot path: "objects active in last 24h")
CREATE INDEX idx_thermal_objects_last_seen
    ON thermal_objects (last_seen DESC);

-- Peak FRP (ranking queries)
CREATE INDEX idx_thermal_objects_persistence
    ON thermal_objects (persistence_score DESC NULLS LAST);

-- =============================================================
-- thermal_object_observations
-- =============================================================

-- Join from thermal_object_id (most common join direction)
CREATE INDEX idx_tobj_obs_thermal_object
    ON thermal_object_observations (thermal_object_id);

-- Join from hotspot_id
CREATE INDEX idx_tobj_obs_hotspot
    ON thermal_object_observations (hotspot_id);

-- =============================================================
-- industrial_facilities
-- =============================================================

-- Spatial: point location (KNN, radius queries)
CREATE INDEX idx_facilities_location
    ON industrial_facilities USING GIST (location);

-- Spatial: boundary polygon (intersection queries)
CREATE INDEX idx_facilities_boundary
    ON industrial_facilities USING GIST (boundary);

-- Filter by type
CREATE INDEX idx_facilities_type
    ON industrial_facilities (facility_type);

-- =============================================================
-- osm_context
-- =============================================================

-- Thermal object lookup
CREATE INDEX idx_osm_context_thermal_object
    ON osm_context (thermal_object_id);

-- Spatial index on cached OSM geometries
CREATE INDEX idx_osm_context_geometry
    ON osm_context USING GIST (geometry);

-- OSM type filter
CREATE INDEX idx_osm_context_type
    ON osm_context (osm_type);

-- =============================================================
-- land_context
-- =============================================================

CREATE INDEX idx_land_context_thermal_object
    ON land_context (thermal_object_id);

-- =============================================================
-- historical_profiles
-- =============================================================

CREATE INDEX idx_historical_profiles_thermal_object
    ON historical_profiles (thermal_object_id);

CREATE INDEX idx_historical_profiles_version
    ON historical_profiles (profile_version);

-- =============================================================
-- feature_vectors
-- =============================================================

CREATE INDEX idx_feature_vectors_thermal_object
    ON feature_vectors (thermal_object_id);

CREATE INDEX idx_feature_vectors_schema_version
    ON feature_vectors (feature_schema_version);

-- GIN index on JSONB features:
-- Justification: supports feature key existence checks (e.g.,
-- WHERE features ? 'frp_z_score') during debugging, data quality
-- audits, and schema migration validation.
-- NOT required for standard ML inference queries (those use
-- thermal_object_id lookups which hit the B-Tree index above).
CREATE INDEX idx_feature_vectors_features_gin
    ON feature_vectors USING GIN (features);

-- =============================================================
-- source_attributions
-- =============================================================

CREATE INDEX idx_source_attr_thermal_object
    ON source_attributions (thermal_object_id);

CREATE INDEX idx_source_attr_category
    ON source_attributions (predicted_category);

CREATE INDEX idx_source_attr_model_version
    ON source_attributions (model_version);

CREATE INDEX idx_source_attr_created
    ON source_attributions (created_at DESC);

-- =============================================================
-- anomaly_results
-- =============================================================

CREATE INDEX idx_anomaly_results_thermal_object
    ON anomaly_results (thermal_object_id);

CREATE INDEX idx_anomaly_results_level
    ON anomaly_results (anomaly_level);

-- Partial index: only HIGH anomalies (operator hot path)
CREATE INDEX idx_anomaly_results_high
    ON anomaly_results (thermal_object_id, created_at DESC)
    WHERE anomaly_level = 'HIGH';

CREATE INDEX idx_anomaly_results_model_version
    ON anomaly_results (model_version);

-- =============================================================
-- supervisor_reviews
-- =============================================================

CREATE INDEX idx_supervisor_reviews_thermal_object
    ON supervisor_reviews (thermal_object_id);

CREATE INDEX idx_supervisor_reviews_status
    ON supervisor_reviews (supervisor_status);

CREATE INDEX idx_supervisor_reviews_created
    ON supervisor_reviews (created_at DESC);

-- =============================================================
-- alerts
-- =============================================================

CREATE INDEX idx_alerts_thermal_object
    ON alerts (thermal_object_id);

-- Status + priority (operator dashboard: open high-priority alerts)
CREATE INDEX idx_alerts_status_priority
    ON alerts (status, priority);

-- Partial index for open alerts (avoids scanning closed/verified rows)
CREATE INDEX idx_alerts_open
    ON alerts (priority, created_at DESC)
    WHERE status NOT IN ('CLOSED', 'VERIFIED');

CREATE INDEX idx_alerts_created
    ON alerts (created_at DESC);

-- Spatial (alert map: centroid of associated thermal object via join)
-- No direct geometry on alerts — spatial queries join to thermal_objects

-- =============================================================
-- human_reviews
-- =============================================================

CREATE INDEX idx_human_reviews_thermal_object
    ON human_reviews (thermal_object_id);

CREATE INDEX idx_human_reviews_status
    ON human_reviews (review_status);

-- Partial index for pending reviews (analyst queue)
CREATE INDEX idx_human_reviews_pending
    ON human_reviews (created_at DESC)
    WHERE review_status = 'PENDING';

-- =============================================================
-- verified_events
-- =============================================================

CREATE INDEX idx_verified_events_thermal_object
    ON verified_events (thermal_object_id);

-- Training candidate lookup
CREATE INDEX idx_verified_events_eligible
    ON verified_events (eligible_for_training, final_category)
    WHERE eligible_for_training = TRUE;

-- =============================================================
-- rag_documents
-- =============================================================

CREATE INDEX idx_rag_documents_source_type
    ON rag_documents (source_type);

-- GIN on metadata: supports tag-based filtering before vector retrieval
CREATE INDEX idx_rag_documents_metadata_gin
    ON rag_documents USING GIN (metadata);

-- =============================================================
-- rag_chunks — VECTOR INDEX (HNSW)
-- =============================================================
-- Strategy: HNSW (Hierarchical Navigable Small World)
-- Chosen over IVFFlat because:
--   • No training step required (works with any cardinality)
--   • Supports incremental inserts without full index rebuild
--   • ~10ms P99 ANN recall for datasets up to several million vectors
--   • Tunable recall vs speed via ef_search at query time
--
-- Parameters:
--   m = 16  — number of bi-directional links per node
--             (higher = better recall, more memory)
--   ef_construction = 64 — search width during build
--             (higher = better recall, slower build)
-- Distance metric: vector_cosine_ops (cosine similarity)
--   Appropriate for normalized sentence/document embeddings.
-- =============================================================

CREATE INDEX idx_rag_chunks_embedding_hnsw
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- B-Tree for document-level lookups
CREATE INDEX idx_rag_chunks_document_id
    ON rag_chunks (document_id);

-- GIN on chunk metadata
CREATE INDEX idx_rag_chunks_metadata_gin
    ON rag_chunks USING GIN (metadata);

-- =============================================================
-- model_registry
-- =============================================================
-- Active models index already created in migration 007
-- Additional indexes:

CREATE INDEX idx_model_registry_type
    ON model_registry (model_type);

CREATE INDEX idx_model_registry_version
    ON model_registry (model_name, version);


DO $$
BEGIN
  RAISE NOTICE 'Migration 008: All indexes created successfully.';
END $$;
