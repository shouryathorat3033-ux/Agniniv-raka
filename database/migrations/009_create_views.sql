-- =============================================================
-- Migration 009 — Database Views
-- HEATWATCH Database
-- =============================================================
-- Depends on: 000–008 (all tables and indexes)
--
-- Views provide pre-joined, read-only query surfaces.
-- All views are CREATE OR REPLACE for safe re-execution.
-- =============================================================

-- =============================================================
-- VIEW: v_active_thermal_objects
-- =============================================================
-- Returns recent, active thermal objects with their latest
-- source attribution and anomaly result.
-- "Latest" = most recently created result for that object.
-- =============================================================

CREATE OR REPLACE VIEW v_active_thermal_objects AS
WITH latest_attribution AS (
    SELECT DISTINCT ON (thermal_object_id)
        thermal_object_id,
        predicted_category,
        confidence   AS attribution_confidence,
        model_version AS attribution_model_version,
        created_at   AS attribution_created_at
    FROM source_attributions
    ORDER BY thermal_object_id, created_at DESC
),
latest_anomaly AS (
    SELECT DISTINCT ON (thermal_object_id)
        thermal_object_id,
        anomaly_level,
        anomaly_score,
        model_version AS anomaly_model_version,
        created_at    AS anomaly_created_at
    FROM anomaly_results
    ORDER BY thermal_object_id, created_at DESC
)
SELECT
    t.id                          AS thermal_object_id,
    ST_AsText(t.centroid)         AS centroid_wkt,
    ST_X(t.centroid)              AS longitude,
    ST_Y(t.centroid)              AS latitude,
    t.first_seen,
    t.last_seen,
    t.duration_hours,
    t.observation_count,
    t.persistence_score,
    t.status,
    -- Source attribution
    la.predicted_category,
    la.attribution_confidence,
    la.attribution_model_version,
    -- Anomaly detection
    an.anomaly_level,
    an.anomaly_score,
    an.anomaly_model_version
FROM thermal_objects t
LEFT JOIN latest_attribution la ON la.thermal_object_id = t.id
LEFT JOIN latest_anomaly     an ON an.thermal_object_id = t.id
WHERE t.status IN ('ACTIVE', 'PERSISTENT')
  AND t.last_seen >= NOW() - INTERVAL '7 days';

COMMENT ON VIEW v_active_thermal_objects IS
    'Active/persistent thermal objects seen in last 7 days with latest AI results. '
    'Does NOT include COOLING, EXTINGUISHED, or UNKNOWN objects.';


-- =============================================================
-- VIEW: v_alert_dashboard
-- =============================================================
-- Returns alert-ready information with linked thermal object,
-- source category, anomaly level, priority, and status.
-- Intended for the operational monitoring dashboard.
-- =============================================================

CREATE OR REPLACE VIEW v_alert_dashboard AS
SELECT
    a.id                          AS alert_id,
    a.priority,
    a.severity,
    a.status                      AS alert_status,
    a.title,
    a.description,
    a.created_at                  AS alert_created_at,
    a.updated_at                  AS alert_updated_at,
    a.resolved_at,
    -- Thermal object
    t.id                          AS thermal_object_id,
    ST_X(t.centroid)              AS longitude,
    ST_Y(t.centroid)              AS latitude,
    t.persistence_score,
    t.observation_count,
    t.first_seen,
    t.last_seen,
    -- Source attribution (linked directly through alert FK)
    sa.predicted_category,
    sa.confidence                 AS attribution_confidence,
    -- Anomaly result
    ar.anomaly_level,
    ar.anomaly_score
FROM alerts a
JOIN thermal_objects t    ON t.id  = a.thermal_object_id
LEFT JOIN source_attributions sa ON sa.id = a.source_attribution_id
LEFT JOIN anomaly_results     ar ON ar.id = a.anomaly_result_id
ORDER BY
    CASE a.priority
        WHEN 'CRITICAL'       THEN 1
        WHEN 'HIGH'           THEN 2
        WHEN 'MEDIUM'         THEN 3
        WHEN 'LOW'            THEN 4
        WHEN 'INFORMATIONAL'  THEN 5
    END,
    a.created_at DESC;

COMMENT ON VIEW v_alert_dashboard IS
    'Operator dashboard view: all alerts with linked thermal object context. '
    'Ordered by priority (CRITICAL first) then recency.';


-- =============================================================
-- VIEW: v_training_candidates
-- =============================================================
-- Returns ONLY records suitable for ML training:
--   • Must have a human_review with review_status = 'CONFIRMED'
--   • Must have eligible_for_training = TRUE
--   • Must have a final_category label
--
-- Model predictions are NEVER returned by this view.
-- This view is the authoritative source for the training data pipeline.
-- =============================================================

CREATE OR REPLACE VIEW v_training_candidates AS
SELECT
    ve.id                         AS verified_event_id,
    ve.thermal_object_id,
    ve.final_category,
    ve.label_source,
    ve.verification_confidence,
    ve.verified_at,
    ve.eligible_for_training,
    -- Human review context
    hr.reviewer_category,
    hr.reviewer_confidence,
    hr.reviewer_identifier,
    hr.reviewed_at,
    -- Feature vector (join for training feature retrieval)
    fv.feature_schema_version,
    fv.features,
    fv.created_at                 AS features_created_at
FROM verified_events ve
JOIN human_reviews hr
    ON hr.id = ve.human_review_id
    AND hr.review_status = 'CONFIRMED'   -- Only confirmed reviews
LEFT JOIN feature_vectors fv
    ON fv.thermal_object_id = ve.thermal_object_id
WHERE ve.eligible_for_training = TRUE    -- Explicit training eligibility required
ORDER BY ve.verified_at DESC;

COMMENT ON VIEW v_training_candidates IS
    'Authoritative training dataset view. '
    'Returns ONLY human-confirmed, explicitly training-eligible verified events. '
    'Model predictions and unconfirmed reviews are excluded. '
    'Used by the ML training pipeline to retrieve labeled examples.';


-- =============================================================
-- VIEW: v_open_alerts_spatial
-- =============================================================
-- Open alerts with centroid WKT for map display.
-- Excludes CLOSED and VERIFIED alerts.
-- =============================================================

CREATE OR REPLACE VIEW v_open_alerts_spatial AS
SELECT
    a.id                          AS alert_id,
    a.priority,
    a.severity,
    a.status,
    a.title,
    a.created_at,
    t.id                          AS thermal_object_id,
    ST_AsText(t.centroid)         AS centroid_wkt,
    ST_X(t.centroid)              AS longitude,
    ST_Y(t.centroid)              AS latitude,
    sa.predicted_category,
    ar.anomaly_level
FROM alerts a
JOIN thermal_objects      t  ON t.id  = a.thermal_object_id
LEFT JOIN source_attributions sa ON sa.id = a.source_attribution_id
LEFT JOIN anomaly_results     ar ON ar.id = a.anomaly_result_id
WHERE a.status NOT IN ('CLOSED', 'VERIFIED')
ORDER BY a.created_at DESC;

COMMENT ON VIEW v_open_alerts_spatial IS
    'Open alerts with centroid coordinates for map display. '
    'Excludes resolved alerts.';


-- =============================================================
-- VIEW: v_human_review_queue
-- =============================================================
-- Pending human reviews awaiting analyst action.
-- =============================================================

CREATE OR REPLACE VIEW v_human_review_queue AS
SELECT
    hr.id                        AS review_id,
    hr.thermal_object_id,
    hr.original_prediction,
    hr.original_confidence,
    hr.review_status,
    hr.created_at,
    t.persistence_score,
    t.observation_count,
    ST_X(t.centroid)             AS longitude,
    ST_Y(t.centroid)             AS latitude,
    al.priority                  AS alert_priority,
    al.title                     AS alert_title
FROM human_reviews hr
JOIN thermal_objects t ON t.id = hr.thermal_object_id
LEFT JOIN alerts al     ON al.thermal_object_id = hr.thermal_object_id
WHERE hr.review_status = 'PENDING'
ORDER BY al.priority NULLS LAST, hr.created_at;

COMMENT ON VIEW v_human_review_queue IS
    'Pending human review queue ordered by alert priority then creation time.';


DO $$
BEGIN
  RAISE NOTICE 'Migration 009: Views created (v_active_thermal_objects, v_alert_dashboard, '
               'v_training_candidates, v_open_alerts_spatial, v_human_review_queue).';
END $$;
