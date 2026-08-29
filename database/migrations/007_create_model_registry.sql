-- =============================================================
-- Migration 007 — Model Registry
-- HEATWATCH Database
-- =============================================================
-- Table: model_registry
--
-- Depends on: 000, 001
--
-- Purpose:
--   Tracks all deployed ML model versions.
--   Referenced by source_attributions.model_version,
--   anomaly_results.model_version, and supervisor_reviews.model_name.
--   (Stored as TEXT references, not FKs, because model_version
--    strings from external ML pipelines may arrive before the
--    registry row is created. Applications should reconcile.)
--
-- Storage policy:
--   model_registry stores ONLY metadata and a URI/path reference.
--   Binary model weights are NEVER stored in PostgreSQL.
--   artifact_location holds a reference to object storage
--   (e.g. S3 URI, GCS path, MLflow run ID, local path).
-- =============================================================

CREATE TABLE model_registry (
    id                     UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identity
    model_name             TEXT        NOT NULL,
    model_type             TEXT        NOT NULL
                             CHECK (model_type IN (
                                 'SOURCE_ATTRIBUTION',   -- Brain 1
                                 'ANOMALY_DETECTION',    -- Brain 2
                                 'SUPERVISOR_LLM',       -- RAG supervisor
                                 'EMBEDDER',             -- RAG embedding model
                                 'CLUSTERING',           -- ST-DBSCAN or similar
                                 'FEATURE_ENGINEERING',  -- Feature pipeline
                                 'OTHER'
                             )),
    version                TEXT        NOT NULL,

    -- Lineage
    dataset_version        TEXT,
    feature_schema_version TEXT,

    -- Training timestamp (UTC; nullable for pre-trained / off-the-shelf models)
    training_date          TIMESTAMPTZ,

    -- Performance metrics (validation scores, AUC, F1, etc.)
    metrics                JSONB,

    -- Hyperparameters and configuration
    parameters             JSONB,

    -- Reference to model artifact storage (NOT the binary — only a path/URI)
    artifact_location      TEXT,

    -- Deployment control
    is_active              BOOLEAN     NOT NULL DEFAULT FALSE,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate model_name/version combinations
    CONSTRAINT uq_model_registry_name_version UNIQUE (model_name, version)
);

COMMENT ON TABLE model_registry IS
    'ML model version registry. '
    'Stores metadata and artifact URI only — no binary weights in PostgreSQL. '
    'is_active = TRUE marks the currently deployed version of each model.';

COMMENT ON COLUMN model_registry.artifact_location IS
    'Reference URI to model artifact storage: S3/GCS path, MLflow run ID, '
    'or local filesystem path. Binary weights are NEVER stored in PostgreSQL.';

COMMENT ON COLUMN model_registry.is_active IS
    'Set TRUE for the currently deployed model version. '
    'Multiple versions can be marked active if different model types are deployed simultaneously.';

-- Index active models (hot query path: "give me the active attribution model")
CREATE INDEX idx_model_registry_active
    ON model_registry (model_type, is_active)
    WHERE is_active = TRUE;


DO $$
BEGIN
  RAISE NOTICE 'Migration 007: Model registry table created.';
END $$;
