-- =============================================================
-- HEATWATCH — Thermal Object Query Examples
-- database/queries/thermal_object_queries.sql
-- =============================================================

-- =============================================================
-- Q1: Persistent thermal objects (high persistence score)
-- =============================================================
SELECT
    t.id,
    ST_X(t.centroid)      AS longitude,
    ST_Y(t.centroid)      AS latitude,
    t.persistence_score,
    t.duration_hours,
    t.observation_count,
    t.first_seen,
    t.last_seen,
    t.status
FROM thermal_objects t
WHERE t.persistence_score > 0.7
  AND t.status IN ('ACTIVE', 'PERSISTENT')
ORDER BY t.persistence_score DESC;


-- =============================================================
-- Q2: Objects active in the last 24 hours
-- =============================================================
SELECT
    t.id,
    ST_X(t.centroid)      AS longitude,
    ST_Y(t.centroid)      AS latitude,
    t.status,
    t.observation_count,
    t.last_seen,
    sa.predicted_category,
    ar.anomaly_level
FROM thermal_objects t
LEFT JOIN LATERAL (
    SELECT predicted_category
    FROM source_attributions
    WHERE thermal_object_id = t.id
    ORDER BY created_at DESC
    LIMIT 1
) sa ON TRUE
LEFT JOIN LATERAL (
    SELECT anomaly_level
    FROM anomaly_results
    WHERE thermal_object_id = t.id
    ORDER BY created_at DESC
    LIMIT 1
) ar ON TRUE
WHERE t.last_seen >= NOW() - INTERVAL '24 hours'
ORDER BY t.last_seen DESC;


-- =============================================================
-- Q3: Full observation history of a thermal object
-- =============================================================
SELECT
    h.id               AS hotspot_id,
    h.source,
    h.satellite,
    h.acquisition_time,
    h.latitude,
    h.longitude,
    h.frp,
    h.confidence,
    h.daynight,
    too.assigned_at
FROM thermal_object_observations too
JOIN hotspots h ON h.id = too.hotspot_id
WHERE too.thermal_object_id = 'YOUR_THERMAL_OBJECT_UUID_HERE'::uuid
ORDER BY h.acquisition_time;


-- =============================================================
-- Q4: Longest-running active thermal objects
-- =============================================================
SELECT
    id,
    ST_X(centroid)        AS longitude,
    ST_Y(centroid)        AS latitude,
    status,
    duration_hours,
    persistence_score,
    observation_count,
    first_seen
FROM thermal_objects
WHERE status IN ('ACTIVE', 'PERSISTENT')
ORDER BY duration_hours DESC
LIMIT 20;


-- =============================================================
-- Q5: Thermal object summary statistics by status
-- =============================================================
SELECT
    status,
    COUNT(*)                    AS object_count,
    ROUND(AVG(duration_hours), 1) AS avg_duration_hrs,
    ROUND(MAX(duration_hours), 1) AS max_duration_hrs,
    ROUND(AVG(persistence_score), 3) AS avg_persistence,
    SUM(observation_count)      AS total_observations
FROM thermal_objects
GROUP BY status
ORDER BY object_count DESC;
