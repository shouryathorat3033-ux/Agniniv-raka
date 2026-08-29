-- =============================================================
-- Migration 005 — Human Feedback Tables
-- HEATWATCH Database
-- =============================================================
-- Tables: human_reviews, verified_events
--
-- Depends on: 000, 001, 002, 003, 004
--
-- Data governance rules:
--   1. Original AI predictions are NEVER modified.
--      human_reviews stores what the AI predicted vs. what the
--      human decided — both are preserved immutably.
--   2. verified_events are populated ONLY from human_reviews
--      where the review has been explicitly confirmed.
--   3. eligible_for_training = FALSE by default.
--      A senior reviewer must explicitly set it TRUE.
--   4. Model predictions are NEVER automatically inserted into
--      verified_events. Only human-validated records qualify.
-- =============================================================

-- =============================================================
-- TABLE: human_reviews
-- =============================================================
-- Purpose:
--   Records a human analyst's validation decision on a thermal
--   object, preserving both the original AI prediction and the
--   human's assessment side-by-side for comparison.
--
-- IMPORTANT: original_prediction is set at insert time and must
--   never be updated. The database does NOT enforce this with a
--   trigger (to keep the schema simple) but the application layer
--   must treat original_prediction as append-only.
-- =============================================================

CREATE TABLE human_reviews (
    id                   UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id    UUID          NOT NULL
                           REFERENCES thermal_objects(id) ON DELETE CASCADE,

    -- Original AI prediction — frozen at review time
    original_prediction  source_category NOT NULL,
    original_confidence  NUMERIC(6,4)
                           CHECK (original_confidence BETWEEN 0.0 AND 1.0),

    -- Human analyst decision
    reviewer_category    source_category,
    reviewer_note        TEXT,
    reviewer_confidence  NUMERIC(6,4)
                           CHECK (reviewer_confidence BETWEEN 0.0 AND 1.0),

    -- Review state
    review_status        review_status  NOT NULL DEFAULT 'PENDING',

    -- Reviewer identity (username / JWT sub — nullable if auth not yet implemented)
    reviewer_identifier  TEXT,

    -- Timing
    reviewed_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE human_reviews IS
    'Human analyst validation of AI predictions. '
    'original_prediction is frozen at insert and must never be updated. '
    'Stores AI result alongside human decision for comparison and bias analysis.';

COMMENT ON COLUMN human_reviews.original_prediction IS
    'The AI prediction at the time of review. '
    'Treat as append-only: do NOT update after insert.';

COMMENT ON COLUMN human_reviews.reviewer_identifier IS
    'Analyst username or JWT sub. Nullable until authentication is implemented.';


-- =============================================================
-- TABLE: verified_events
-- =============================================================
-- Purpose:
--   Curated, human-approved ground truth records that MAY be
--   used for future ML training datasets.
--
-- DATA GOVERNANCE:
--   - Only records with human_reviews.review_status = 'CONFIRMED'
--     should ever be inserted here.
--   - eligible_for_training = FALSE by default.
--   - A senior reviewer must explicitly set eligible_for_training
--     = TRUE through the application layer.
--   - Model predictions are NEVER automatically inserted here.
--   - label_source documents the human decision chain.
-- =============================================================

CREATE TABLE verified_events (
    id                       UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    thermal_object_id        UUID          NOT NULL
                               REFERENCES thermal_objects(id)  ON DELETE CASCADE,
    human_review_id          UUID          NOT NULL UNIQUE
                               REFERENCES human_reviews(id)    ON DELETE RESTRICT,

    -- Ground truth label
    final_category           source_category NOT NULL,

    -- Provenance
    label_source             TEXT          NOT NULL
                               CHECK (label_source IN (
                                   'HUMAN_REVIEW',
                                   'SENIOR_ANALYST',
                                   'EXPERT_CONSENSUS',
                                   'REGULATORY_CONFIRMATION'
                               )),

    -- Quality rating
    verification_confidence  NUMERIC(6,4)
                               CHECK (verification_confidence BETWEEN 0.0 AND 1.0),

    -- Training eligibility — must be set explicitly by a senior reviewer
    -- DEFAULT FALSE: no record is eligible for training without explicit approval
    eligible_for_training    BOOLEAN       NOT NULL DEFAULT FALSE,

    -- Timing
    verified_at              TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at               TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE verified_events IS
    'Curated ground truth labels for future ML training. '
    'Populated ONLY from confirmed human reviews. '
    'eligible_for_training = FALSE by default — requires explicit senior reviewer approval. '
    'Model predictions are NEVER auto-inserted here.';

COMMENT ON COLUMN verified_events.eligible_for_training IS
    'Training dataset eligibility flag. '
    'Must be set TRUE explicitly by a qualified senior reviewer. '
    'DEFAULT FALSE prevents accidental training data contamination.';

COMMENT ON COLUMN verified_events.human_review_id IS
    'FK to the human_review that produced this verified label. '
    'UNIQUE ensures one-to-one mapping: one review → at most one verified event. '
    'ON DELETE RESTRICT prevents removing the source review without removing this record first.';


DO $$
BEGIN
  RAISE NOTICE 'Migration 005: Human feedback tables created (human_reviews, verified_events).';
END $$;
