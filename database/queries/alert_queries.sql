-- =============================================================
-- HEATWATCH — Alert Query Examples
-- database/queries/alert_queries.sql
-- =============================================================

-- =============================================================
-- Q1: Highest priority unresolved alerts
-- =============================================================
SELECT
    a.id,
    a.priority,
    a.severity,
    a.status,
    a.title,
    a.created_at,
    ST_X(t.centroid)     AS longitude,
    ST_Y(t.centroid)     AS latitude,
    sa.predicted_category,
    ar.anomaly_level,
    ar.anomaly_score
FROM alerts a
JOIN thermal_objects      t  ON t.id  = a.thermal_object_id
LEFT JOIN source_attributions sa ON sa.id = a.source_attribution_id
LEFT JOIN anomaly_results     ar ON ar.id = a.anomaly_result_id
WHERE a.status NOT IN ('CLOSED', 'VERIFIED')
ORDER BY
    CASE a.priority
        WHEN 'CRITICAL'       THEN 1
        WHEN 'HIGH'           THEN 2
        WHEN 'MEDIUM'         THEN 3
        WHEN 'LOW'            THEN 4
        WHEN 'INFORMATIONAL'  THEN 5
    END,
    a.created_at DESC;


-- =============================================================
-- Q2: Recent alerts (last 48 hours)
-- =============================================================
SELECT
    a.id,
    a.priority,
    a.status,
    a.title,
    a.created_at,
    a.updated_at,
    a.resolved_at
FROM alerts a
WHERE a.created_at >= NOW() - INTERVAL '48 hours'
ORDER BY a.created_at DESC;


-- =============================================================
-- Q3: Alerts grouped by anomaly level
-- =============================================================
SELECT
    ar.anomaly_level,
    COUNT(DISTINCT a.id)    AS alert_count,
    COUNT(DISTINCT CASE WHEN a.status = 'VERIFIED' THEN a.id END) AS verified_count,
    COUNT(DISTINCT CASE WHEN a.status = 'CLOSED'   THEN a.id END) AS closed_count
FROM alerts a
LEFT JOIN anomaly_results ar ON ar.id = a.anomaly_result_id
GROUP BY ar.anomaly_level
ORDER BY alert_count DESC;


-- =============================================================
-- Q4: Alerts linked to INDUSTRIAL attribution categories
-- =============================================================
SELECT
    a.id,
    a.priority,
    a.title,
    a.status,
    sa.predicted_category,
    sa.confidence,
    a.created_at
FROM alerts a
JOIN source_attributions sa ON sa.id = a.source_attribution_id
WHERE sa.predicted_category IN (
    'INDUSTRIAL_FIRE',
    'PERSISTENT_THERMAL_SOURCE',
    'MINING_ACTIVITY'
)
ORDER BY a.created_at DESC;


-- =============================================================
-- Q5: Alert resolution time analysis
-- =============================================================
SELECT
    priority,
    COUNT(*)                                         AS total_alerts,
    COUNT(resolved_at)                               AS resolved_count,
    ROUND(AVG(
        EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600.0
    ), 2)                                            AS avg_resolution_hours
FROM alerts
WHERE resolved_at IS NOT NULL
GROUP BY priority
ORDER BY total_alerts DESC;
