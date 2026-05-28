-- Session state tracking for hiring_quiz_attempts and hiring_sessions
-- Idempotent: safe to run multiple times
-- Already applied to production DB via run_session_state_migration.py on 2026-05-28

ALTER TABLE hiring_quiz_attempts
    ADD COLUMN IF NOT EXISTS attempt_status TEXT NOT NULL DEFAULT 'created'
        CHECK (attempt_status IN (
            'created','started','in_progress','abandoned',
            'resumed','completed','expired','cancelled','reopened_by_staff'
        )),
    ADD COLUMN IF NOT EXISTS abandoned_at_question_id TEXT REFERENCES hiring_quiz_questions(id),
    ADD COLUMN IF NOT EXISTS resume_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE hiring_sessions
    ADD COLUMN IF NOT EXISTS resume_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reopened_by TEXT;
