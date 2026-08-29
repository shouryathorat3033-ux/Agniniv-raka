-- =============================================================
-- HEATWATCH — Hotspot Query Examples
-- database/queries/hotspot_queries.sql
-- =============================================================

-- =============================================================
-- Q1: Most recent hotspots (last 6 hours)
-- =============================================================
SELECT
    id,
    source,
    satellite,
    latitude,
    longitude,
    frp,
    confidence,
    acquisition_time
FROM hotspots
WHERE acquisition_time >= NOW() - INTERVAL '6 hours'
ORDER BY acquisition_time DESC
LIMIT 100;


-- =============================================================
-- Q2: Hotspots by satellite source in a time range
-- =============================================================
SELECT
    source,
    satellite,
    COUNT(*)            AS detection_count,
    AVG(frp)            AS avg_frp_mw,
    MAX(frp)            AS max_frp_mw,
    MIN(acquisition_time) AS earliest,
    MAX(acquisition_time) AS latest
FROM hotspots
WHERE acquisition_time BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY source, satellite
ORDER BY detection_count DESC;


-- =============================================================
-- Q3: High-confidence, high-FRP hotspots in last 24 hours
-- =============================================================
SELECT
    id,
    source,
    latitude,
    longitude,
    frp,
    confidence,
    acquisition_time
FROM hotspots
WHERE acquisition_time >= NOW() - INTERVAL '24 hours'
  AND confidence = 'high'
  AND frp > 100       -- > 100 MW FRP threshold
ORDER BY frp DESC;


-- =============================================================
-- Q4: Duplicate detection investigation
-- Finds multiple detections very close in time for the same pixel
-- (useful for debugging ingestion deduplication).
-- =============================================================
SELECT
    source,
    latitude,
    longitude,
    acquisition_time,
    COUNT(*) AS count
FROM hotspots
GROUP BY source, latitude, longitude, acquisition_time
HAVING COUNT(*) > 1;


-- =============================================================
-- Q5: Hotspots not yet assigned to any thermal object
-- =============================================================
SELECT h.*
FROM hotspots h
WHERE NOT EXISTS (
    SELECT 1 FROM thermal_object_observations too
    WHERE too.hotspot_id = h.id
)
  AND h.acquisition_time >= NOW() - INTERVAL '48 hours'
ORDER BY h.acquisition_time DESC;


-- =============================================================
-- Q6: Hotspot count per day over last 30 days
-- =============================================================
SELECT
    DATE_TRUNC('day', acquisition_time) AS day,
    source,
    COUNT(*)                             AS hotspot_count
FROM hotspots
WHERE acquisition_time >= NOW() - INTERVAL '30 days'
GROUP BY day, source
ORDER BY day DESC, hotspot_count DESC;
