-- Hiring assessment system: AI assessments, targeted messages,
-- correction responses, and offers.
-- Run once on server after hire bot quiz is live.

-- ── AI assessments (Opus output, one row per attempt) ─────────────────────────
CREATE TABLE IF NOT EXISTS hiring_ai_assessments (
    id                      SERIAL PRIMARY KEY,
    candidate_id            INTEGER REFERENCES hiring_candidates(id),
    intake_id               INTEGER REFERENCES hiring_intake_sessions(id),
    attempt_id              INTEGER REFERENCES hiring_quiz_attempts(id),
    assessment_mode         TEXT NOT NULL DEFAULT 'applicant_hiring_screen',
    -- applicant_hiring_screen | leadership_audit | retraining_review
    provider                TEXT NOT NULL DEFAULT 'anthropic',
    model                   TEXT NOT NULL,
    prompt_version          TEXT NOT NULL,
    rubric_version          TEXT NOT NULL DEFAULT 'twb_2026_v1',
    input_package_json      TEXT NOT NULL,
    output_json             TEXT NOT NULL,
    output_valid            BOOLEAN NOT NULL DEFAULT FALSE,
    recommendation          TEXT CHECK (recommendation IN (
                                'hire','trial','hold_for_retest',
                                'reject','reject_unless_owner_override',
                                'hold_clarify_first','pending')),
    confidence              FLOAT,
    critical_signal_count   INTEGER DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS hiring_ai_assessments_attempt_id_idx
    ON hiring_ai_assessments(attempt_id);

-- ── Targeted messages (EN+KH, point by point) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS hiring_targeted_messages (
    id                      SERIAL PRIMARY KEY,
    candidate_id            INTEGER REFERENCES hiring_candidates(id),
    assessment_id           INTEGER REFERENCES hiring_ai_assessments(id),
    attempt_id              INTEGER REFERENCES hiring_quiz_attempts(id),
    message_type            TEXT NOT NULL DEFAULT 'applicant_correction',
    -- applicant_correction | staff_retraining | offer_condition | trial_watchlist
    points_json             TEXT NOT NULL,   -- [{english, khmer, evidence_refs, goal}]
    english_text            TEXT NOT NULL,
    khmer_text              TEXT,            -- NULL until validated
    khmer_validated         BOOLEAN NOT NULL DEFAULT FALSE,
    khmer_validation_status TEXT NOT NULL DEFAULT 'pending',
    -- pending | passed | failed | manual_approved | auto_send_blocked
    prompt_version          TEXT NOT NULL DEFAULT 'v1',
    owner_approved          BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at                 TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS hiring_targeted_messages_attempt_id_idx
    ON hiring_targeted_messages(attempt_id);

-- ── Correction responses (applicant's open-check answer + classification) ──────
CREATE TABLE IF NOT EXISTS hiring_correction_responses (
    id                      SERIAL PRIMARY KEY,
    candidate_id            INTEGER REFERENCES hiring_candidates(id),
    targeted_message_id     INTEGER REFERENCES hiring_targeted_messages(id),
    attempt_id              INTEGER REFERENCES hiring_quiz_attempts(id),
    telegram_message_id     BIGINT,
    button_tapped           TEXT,   -- 'agree' | 'question' | NULL (typed)
    open_check_question     TEXT,
    open_check_answer       TEXT,
    classification_primary  TEXT,
    -- correction_understood | correction_parroted | conditional_reporting
    -- correction_understanding_failed | hiding_standard_not_accepted
    -- correction_unclear | correction_deflected | correction_understood_with_qualifier
    classification_secondary TEXT[],
    classification_reasoning TEXT,
    severity                TEXT,
    recommendation_update   TEXT,
    -- proceed_to_verbal_retest | reject_unless_owner_override | one_more_probe
    classified_by           TEXT NOT NULL DEFAULT 'opus',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Offers (actual agreed salary, separate from applicant current salary) ──────
CREATE TABLE IF NOT EXISTS hiring_offers (
    id                          SERIAL PRIMARY KEY,
    candidate_id                INTEGER NOT NULL REFERENCES hiring_candidates(id),
    intake_id                   INTEGER REFERENCES hiring_intake_sessions(id),
    attempt_id                  INTEGER REFERENCES hiring_quiz_attempts(id),
    assessment_id               INTEGER REFERENCES hiring_ai_assessments(id),
    base_salary                 NUMERIC(8,2) NOT NULL,
    bonus                       NUMERIC(8,2),
    food_allowance_daily_riel   INTEGER,   -- e.g. 4500 for 9h
    hours_per_day               INTEGER NOT NULL,
    shift_time                  TEXT,      -- e.g. '7am-4pm'
    total_monthly_display       NUMERIC(8,2),
    start_date                  DATE,
    offer_status                TEXT NOT NULL DEFAULT 'proposed'
                                    CHECK (offer_status IN (
                                        'proposed','accepted','refused','changed','cancelled')),
    proposed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at                 TIMESTAMPTZ,
    reason_for_offer            TEXT,
    created_by                  TEXT NOT NULL DEFAULT 'system',
    notes                       TEXT
);
CREATE INDEX IF NOT EXISTS hiring_offers_candidate_id_idx
    ON hiring_offers(candidate_id);
