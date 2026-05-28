-- Add CV media storage columns to hiring_intake_sessions.
-- Stores the Telegram file_id and message_id when a CV is submitted as photo/document.

ALTER TABLE hiring_intake_sessions
    ADD COLUMN IF NOT EXISTS cv_file_id    text,
    ADD COLUMN IF NOT EXISTS cv_message_id bigint;
