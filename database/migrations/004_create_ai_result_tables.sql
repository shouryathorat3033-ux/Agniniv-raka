-- =============================================================
-- Migration 004 — AI Result Tables + Alerts
-- HEATWATCH Database
-- =============================================================
-- Tables: source_attributions, anomaly_results,
--         supervisor_reviews, alerts
--
-- Depends on: 000, 001, 002, 003
--
-- Architecture note:
--   These tables store RESULTS produced by external ML pipelines.
--   The database is NOT responsible for running inference.
--   Each table preserves full traceability: model_version is
--   stored alongside every result row.
-- =============================================================

-- =============================================================
-- TABLE: source_attributions
-- =============================================================
-- Purpose:
--   Stores Brain 1 (source attribution classifier) outputs.
--   Classifies whether a thermal object is industrial, wildfire,
--   agricultural burn, etc.
-- =============================================================

CREATE TABLE source_attributions (
    id                   UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id    UUID          NOT NULL
                           REFERENCES thermal_objects(id) ON DELETE CASCADE,

    -- Prediction
    predicted_category   source_category NOT NULL,
    confidence           NUMERIC(6,4)
                           CHECK (confidence BETWEEN 0.0 AND 1.0),

    -- Evidence scoring (0–100 or normalised, depending on model)
    evidence_score       NUMERIC(8,4)
                           CHECK (evidence_score BETWEEN 0.0 AND 100.0),

    -- Structured evidence and conflicts
    evidence             JSONB,
    conflicting_evidence JSONB,

    -- Model traceability
    model_version        TEXT          NOT NULL,

    created_at           TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE source_attributions IS
    'Brain 1 classification results: fire/heat source attribution. '
    'Original predictions are immutable once inserted. '
    'Human corrections go into human_reviews, not here.';

COMMENT ON COLUMN source_attributions.conflicting_evidence IS
    'Evidence that contradicts the primary prediction. '
    'Stored separately to preserve scientific transparency.';


-- =============================================================
-- TABLE: anomaly_results
-- =============================================================
-- Purpose:
--   Stores Brain 2 (anomaly detector) outputs.
--   Flags thermal objects whose behaviour deviates from baseline.
-- =============================================================

CREATE TABLE anomaly_results (
    id                  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id   UUID         NOT NULL
                          REFERENCES thermal_objects(id) ON DELETE CASCADE,

    -- Classification
    anomaly_level       anomaly_level NOT NULL,
    anomaly_score       NUMERIC(8,6)
                          CHECK (anomaly_score BETWEEN 0.0 AND 1.0),

    -- Component anomaly flags (boolean — component-level breakdown)
    frp_anomaly         BOOLEAN,      -- Fire Radiative Power spike
    spatial_anomaly     BOOLEAN,      -- Spatial extent anomaly
    temporal_anomaly    BOOLEAN,      -- Temporal pattern anomaly
    footprint_anomaly   BOOLEAN,      -- Fire footprint area anomaly
    centroid_drift      BOOLEAN,      -- Centroid moved unexpectedly
    duration_anomaly    BOOLEAN,      -- Duration longer than baseline
    diurnal_anomaly     BOOLEAN,      -- Unusual time-of-day pattern

    -- Structured evidence
    evidence            JSONB,

    -- Model traceability
    model_version       TEXT         NOT NULL,

    created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE anomaly_results IS
    'Brain 2 anomaly detection results. '
    'Boolean component flags allow targeted investigation. '
    'anomaly_score is the combined model score [0,1].';


-- =============================================================
-- TABLE: supervisor_reviews
-- =============================================================
-- Purpose:
--   Stores RAG-grounded LLM supervisor assessments.
--   Synthesises Brain 1 + Brain 2 results into a human-readable
--   structured assessment.
--
-- IMPORTANT:
--   This table stores LLM-generated text and structured JSON.
--   It MUST NOT overwrite or modify source_attributions or
--   anomaly_results. Those remain as immutable calculation results.
--   Traceability is maintained via FK to source_attribution_id
--   and anomaly_result_id.
-- =============================================================

CREATE TABLE supervisor_reviews (
    id                    UUID             PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id     UUID             NOT NULL
                            REFERENCES thermal_objects(id)     ON DELETE CASCADE,
    source_attribution_id UUID
                            REFERENCES source_attributions(id) ON DELETE SET NULL,
    anomaly_result_id     UUID
                            REFERENCES anomaly_results(id)     ON DELETE SET NULL,

    -- Supervisor decision
    supervisor_status     supervisor_status NOT NULL,
    supervisor_assessment TEXT,

    -- Structured reasoning (JSON arrays/objects from LLM output)
    supported_by          JSONB,          -- Evidence supporting the assessment
    conflicts             JSONB,          -- Conflicts detected between sources
    missing_evidence      JSONB,          -- Evidence gaps flagged by supervisor

    -- Recommendations
    possible_alternative  TEXT,
    recommended_action    TEXT,
    explanation           TEXT,

    -- RAG traceability
    rag_sources           JSONB,          -- Document IDs and chunk IDs retrieved

    -- LLM provenance
    model_name            TEXT            NOT NULL,
    prompt_version        TEXT            NOT NULL,

    created_at            TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE supervisor_reviews IS
    'RAG-grounded LLM supervisor assessments. '
    'Stores synthesis of Brain 1 + Brain 2 results. '
    'Does NOT overwrite deterministic pipeline results.';

COMMENT ON COLUMN supervisor_reviews.rag_sources IS
    'JSONB array of retrieved RAG chunk IDs and document references used '
    'to generate the supervisor assessment. Preserves full retrieval audit trail.';


-- =============================================================
-- TABLE: alerts
-- =============================================================
-- Purpose:
--   Actionable incidents surfaced to operators/analysts.
--   One alert per thermal object per meaningful anomaly event.
--
-- Lifecycle: NEW → INVESTIGATING → FLAGGED → VERIFIED or CLOSED
-- =============================================================

CREATE TABLE alerts (
    id                    UUID           PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id     UUID           NOT NULL
                            REFERENCES thermal_objects(id)     ON DELETE CASCADE,
    source_attribution_id UUID
                            REFERENCES source_attributions(id) ON DELETE SET NULL,
    anomaly_result_id     UUID
                            REFERENCES anomaly_results(id)     ON DELETE SET NULL,

    -- Incident classification
    priority              alert_priority NOT NULL DEFAULT 'MEDIUM',
    severity              TEXT           NOT NULL DEFAULT 'MEDIUM'
                            CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW','INFORMATIONAL')),
    status                alert_status   NOT NULL DEFAULT 'NEW',

    -- Human-readable content
    title                 TEXT           NOT NULL,
    description           TEXT,

    -- Timing
    created_at            TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at           TIMESTAMPTZ,

    -- Integrity
    CONSTRAINT chk_alert_resolved_after_created
        CHECK (resolved_at IS NULL OR resolved_at >= created_at)
);

COMMENT ON TABLE alerts IS
    'Prioritized incident alerts for operator review. '
    'ON DELETE CASCADE from thermal_objects removes associated alerts. '
    'Lifecycle: NEW → INVESTIGATING → FLAGGED/VERIFIED/CLOSED.';

CREATE TRIGGER trg_alerts_updated_at
    BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


DO $$
BEGIN
  RAISE NOTICE 'Migration 004: AI result tables and alerts created.';
END $$;
