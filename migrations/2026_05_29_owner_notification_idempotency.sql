-- Idempotency columns for owner notifications.
-- Prevents duplicate messages if a handler fires twice.

ALTER TABLE hiring_intake_sessions
    ADD COLUMN IF NOT EXISTS intake_owner_notified_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS intake_owner_notified_status TEXT;

ALTER TABLE hiring_quiz_attempts
    ADD COLUMN IF NOT EXISTS quiz_owner_notified_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS quiz_owner_notified_outcome  TEXT;
