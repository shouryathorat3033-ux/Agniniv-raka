-- =============================================================
-- HEATWATCH — Human Feedback Query Examples
-- database/queries/human_feedback_queries.sql
-- =============================================================

-- =============================================================
-- Q1: Pending human review queue
-- =============================================================
SELECT
    hr.id                    AS review_id,
    hr.thermal_object_id,
    hr.original_prediction,
    hr.original_confidence,
    hr.review_status,
    hr.created_at,
    ST_X(t.centroid)         AS longitude,
    ST_Y(t.centroid)         AS latitude,
    t.persistence_score,
    al.priority              AS alert_priority,
    al.title                 AS alert_title
FROM human_reviews hr
JOIN thermal_objects t ON t.id = hr.thermal_object_id
LEFT JOIN alerts al    ON al.thermal_object_id = hr.thermal_object_id
                       AND al.status NOT IN ('CLOSED', 'VERIFIED')
WHERE hr.review_status = 'PENDING'
ORDER BY al.priority NULLS LAST, hr.created_at;


-- =============================================================
-- Q2: Confirmed events (all reviewer decisions)
-- =============================================================
SELECT
    hr.id,
    hr.thermal_object_id,
    hr.original_prediction,
    hr.reviewer_category,
    hr.reviewer_confidence,
    hr.reviewer_note,
    hr.reviewer_identifier,
    hr.reviewed_at
FROM human_reviews hr
WHERE hr.review_status = 'CONFIRMED'
ORDER BY hr.reviewed_at DESC;


-- =============================================================
-- Q3: AI vs human disagreement analysis
-- Cases where the reviewer changed the category
-- =============================================================
SELECT
    hr.id,
    hr.original_prediction        AS ai_prediction,
    hr.reviewer_category          AS human_decision,
    hr.reviewer_confidence,
    hr.reviewer_note,
    hr.reviewed_at
FROM human_reviews hr
WHERE hr.review_status = 'CONFIRMED'
  AND hr.reviewer_category IS NOT NULL
  AND hr.reviewer_category != hr.original_prediction
ORDER BY hr.reviewed_at DESC;


-- =============================================================
-- Q4: Training-eligible verified events
-- =============================================================
SELECT
    ve.id                        AS verified_event_id,
    ve.thermal_object_id,
    ve.final_category,
    ve.label_source,
    ve.verification_confidence,
    ve.verified_at,
    hr.reviewer_identifier,
    hr.reviewer_confidence,
    fv.feature_schema_version,
    fv.features
FROM verified_events ve
JOIN human_reviews hr  ON hr.id = ve.human_review_id
LEFT JOIN feature_vectors fv ON fv.thermal_object_id = ve.thermal_object_id
WHERE ve.eligible_for_training = TRUE
ORDER BY ve.verified_at DESC;


-- =============================================================
-- Q5: Review volume and agreement rate per reviewer
-- =============================================================
SELECT
    reviewer_identifier,
    COUNT(*)                                     AS total_reviews,
    COUNT(CASE WHEN review_status = 'CONFIRMED'  THEN 1 END) AS confirmed,
    COUNT(CASE WHEN review_status = 'REJECTED'   THEN 1 END) AS rejected,
    COUNT(CASE WHEN reviewer_category != original_prediction
               AND review_status = 'CONFIRMED'   THEN 1 END) AS disagreements,
    ROUND(
        100.0 * COUNT(CASE WHEN reviewer_category = original_prediction
                           AND review_status = 'CONFIRMED' THEN 1 END)
            / NULLIF(COUNT(CASE WHEN review_status = 'CONFIRMED' THEN 1 END), 0),
        1
    ) AS agreement_rate_pct
FROM human_reviews
WHERE reviewer_identifier IS NOT NULL
GROUP BY reviewer_identifier
ORDER BY total_reviews DESC;
