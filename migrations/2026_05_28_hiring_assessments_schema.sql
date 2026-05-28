-- hiring_assessments: assessment-event layer between candidates and findings
-- Idempotent: safe to re-run
--
-- Hierarchy:
--   hiring_candidates (person)
--     → hiring_assessments (one per event: paper review, bot session, trial observation)
--       → hiring_quiz_attempts (optional, bot sessions only, via quiz_attempt_id)
--       → hiring_feedback_points (linked via assessment_id)
--       → hiring_contradictions (linked via attempt_id or assessment_id)
--
-- subject_status_at_assessment captures the person's role at the time of assessment,
-- so a future promotion review does not change how the old hiring screen is read.

CREATE TABLE IF NOT EXISTS hiring_assessments (
    id                          SERIAL PRIMARY KEY,
    candidate_id                INTEGER NOT NULL REFERENCES hiring_candidates(id),

    -- Who this person was at the time of assessment
    subject_status_at_assessment TEXT NOT NULL DEFAULT 'applicant'
        CHECK (subject_status_at_assessment IN (
            'applicant', 'new_staff', 'existing_staff',
            'senior_staff', 'supervisor_candidate', 'manager'
        )),

    -- Where the assessment came from and why
    assessment_source           TEXT NOT NULL DEFAULT 'bot'
        CHECK (assessment_source IN ('bot', 'legacy_paper', 'trial_observation', 'manual')),
    assessment_context          TEXT NOT NULL DEFAULT 'hiring_screen'
        CHECK (assessment_context IN (
            'hiring_screen', 'leadership_audit',
            'retraining_review', 'promotion_review', 'trial_review'
        )),

    -- Optional link to a bot-generated attempt (NULL for legacy paper)
    -- UNIQUE enforces one assessment per attempt
    quiz_attempt_id             INTEGER UNIQUE REFERENCES hiring_quiz_attempts(id),

    assessed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assessor_name               TEXT,       -- staff name, 'legacy_paper', 'claude_opus', etc.
    human_review_confidence     TEXT
        CHECK (human_review_confidence IN ('low', 'medium', 'medium_high', 'high')),
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── hiring_feedback_points additions ─────────────────────────────────────────

-- Link finding to assessment event (preferred) or candidate directly (legacy fallback)
ALTER TABLE hiring_feedback_points
    ADD COLUMN IF NOT EXISTS assessment_id INTEGER REFERENCES hiring_assessments(id);

-- Per-finding: what level of staff is this answer being judged against?
-- Allows the same answer to be "worker_acceptable" for an applicant but
-- "chef_expected_gap" for senior kitchen staff.
ALTER TABLE hiring_feedback_points
    ADD COLUMN IF NOT EXISTS staff_level_expectation TEXT
        CHECK (staff_level_expectation IN (
            'entry_acceptable',
            'worker_acceptable', 'worker_gap',
            'senior_expected_strength', 'senior_expected_gap',
            'supervisor_expected_strength', 'supervisor_expected_gap',
            'chef_expected_strength', 'chef_expected_gap'
        ));

-- Per-finding confidence (distinct from human_review_confidence on the assessment)
-- Low = handwriting unclear or question likely misunderstood
-- High = answer clearly visible, interpretation unambiguous
ALTER TABLE hiring_feedback_points
    ADD COLUMN IF NOT EXISTS confidence TEXT
        CHECK (confidence IN ('low', 'medium', 'high'));

-- Human reviewer interpretation note (the "why this matters" for that finding)
ALTER TABLE hiring_feedback_points
    ADD COLUMN IF NOT EXISTS interpretation TEXT;

-- Expand severity CHECK to include all values ChatGPT format uses.
-- Drop and recreate because PostgreSQL has no ALTER CONSTRAINT.
ALTER TABLE hiring_feedback_points
    DROP CONSTRAINT IF EXISTS hiring_feedback_points_severity_check;
ALTER TABLE hiring_feedback_points
    ADD CONSTRAINT hiring_feedback_points_severity_check
        CHECK (severity IN (
            'strength_high', 'strength_medium',
            'gap_minor', 'gap_low_medium', 'gap_medium', 'gap_high', 'gap_critical',
            'risk_low', 'risk_medium', 'risk_high', 'risk_critical',
            'contradiction'
        ));

-- Expand source_type CHECK to include legacy_paper
ALTER TABLE hiring_feedback_points
    DROP CONSTRAINT IF EXISTS hiring_feedback_points_source_type_check;
ALTER TABLE hiring_feedback_points
    ADD CONSTRAINT hiring_feedback_points_source_type_check
        CHECK (source_type IN (
            'quiz', 'cv', 'observation', 'trial', 'draft', 'legacy_paper'
        ));

-- ── hiring_contradictions additions ──────────────────────────────────────────

-- Allow legacy-paper contradictions that have no quiz_attempt_id
-- Step 1: make attempt_id nullable (was NOT NULL)
ALTER TABLE hiring_contradictions
    ALTER COLUMN attempt_id DROP NOT NULL;

-- Step 2: add assessment_id link for legacy-paper findings
ALTER TABLE hiring_contradictions
    ADD COLUMN IF NOT EXISTS assessment_id INTEGER REFERENCES hiring_assessments(id);

-- Step 3: at least one of attempt_id or assessment_id must be present
ALTER TABLE hiring_contradictions
    DROP CONSTRAINT IF EXISTS hiring_contradictions_source_check;
ALTER TABLE hiring_contradictions
    ADD CONSTRAINT hiring_contradictions_source_check
        CHECK (
            (attempt_id IS NOT NULL)::int +
            (assessment_id IS NOT NULL)::int >= 1
        );

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_hiring_assessments_candidate
    ON hiring_assessments (candidate_id);
CREATE INDEX IF NOT EXISTS idx_hiring_feedback_points_assessment
    ON hiring_feedback_points (assessment_id);
CREATE INDEX IF NOT EXISTS idx_hiring_contradictions_assessment
    ON hiring_contradictions (assessment_id);
