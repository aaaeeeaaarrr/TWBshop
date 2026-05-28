-- Migration: 2026_05_28_scoring_schema.sql
-- Adds scoring infrastructure to the hiring system.
-- Safe to re-run (uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

-- ── 1. hiring_contradictions ─────────────────────────────────────────────────
-- Stores tick-vs-written and other detected contradictions per quiz attempt.
-- ai_flagged = rule-detected; human_confirmed = owner reviewed via Telegram.

CREATE TABLE IF NOT EXISTS hiring_contradictions (
    id                  SERIAL PRIMARY KEY,
    attempt_id          INTEGER NOT NULL REFERENCES hiring_quiz_attempts(id) ON DELETE CASCADE,
    question_id_a       TEXT NOT NULL REFERENCES hiring_quiz_questions(id),
    question_id_b       TEXT NOT NULL REFERENCES hiring_quiz_questions(id),
    contradiction_type  VARCHAR(50) NOT NULL
                            CHECK (contradiction_type IN (
                                'tick_vs_written',
                                'tick_vs_tick',
                                'written_vs_written',
                                'schedule_story',
                                'cv_vs_written'
                            )),
    severity            VARCHAR(20) NOT NULL DEFAULT 'moderate'
                            CHECK (severity IN ('critical','moderate','minor')),
    description         TEXT,
    ai_flagged          BOOLEAN NOT NULL DEFAULT FALSE,
    human_confirmed     BOOLEAN,            -- NULL = pending, TRUE = confirmed, FALSE = suppressed
    suppressed          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hiring_contradictions_attempt
    ON hiring_contradictions(attempt_id);


-- ── 2. hiring_quiz_attempts — score_summary + risk_profile ───────────────────
-- score_summary: auto-graded results (stored immediately after session ends)
-- Shape: {"score_a":58,"score_a_max":60,"score_b":22,"score_b_max":22,
--         "d1_priority_score":3,"written_sections_scored":false,
--         "contradiction_count":0,"critical_wrong":[],"not_sure_critical":[],
--         "auto_graded_at":"2026-05-28T..."}
--
-- risk_profile: 8-category profile (stored after Claude rubric scoring)
-- Shape: {"honesty_logic":"strong","schedule_clarity":"clean",
--         "completion_discipline":"strong","customer_instinct":"trainable",
--         "quiet_time_work_ethic":"unclear","experience_credibility":"verified",
--         "leadership_potential":"emerging","trial_recommendation":"trial",
--         "generated_at":"2026-05-28T..."}

ALTER TABLE hiring_quiz_attempts
    ADD COLUMN IF NOT EXISTS score_summary  JSONB,
    ADD COLUMN IF NOT EXISTS risk_profile   JSONB;


-- ── 3. hiring_trial_outcomes — add per-quiz-category fields ─────────────────
-- quiet_time_behavior: was their actual behavior during slow periods productive?
-- schedule_story_match: did their schedule story during trial match what they said?

ALTER TABLE hiring_trial_outcomes
    ADD COLUMN IF NOT EXISTS quiet_time_behavior      TEXT,
    ADD COLUMN IF NOT EXISTS schedule_story_match     TEXT;
