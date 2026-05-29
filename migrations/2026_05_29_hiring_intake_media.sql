-- hiring_intake_media: stores every photo/document sent during intake
-- One row per file. Applicants may send multiple CV pages, certificates, IDs.
-- No AI analysis until TEST_UNLOCKED — store first, analyse later.

CREATE TABLE IF NOT EXISTS hiring_intake_media (
    id                      SERIAL PRIMARY KEY,
    intake_id               INTEGER NOT NULL REFERENCES hiring_intake_sessions(id) ON DELETE CASCADE,
    telegram_chat_id        BIGINT NOT NULL,
    telegram_user_id        BIGINT,
    telegram_message_id     BIGINT NOT NULL,
    telegram_file_id        TEXT NOT NULL,
    telegram_file_unique_id TEXT,
    media_group_id          TEXT,           -- Telegram album ID (same for photos sent together)
    media_type              TEXT NOT NULL CHECK (media_type IN ('photo','document','video','other')),
    original_filename       TEXT,
    mime_type               TEXT,
    file_size               BIGINT,
    caption                 TEXT,
    purpose                 TEXT NOT NULL DEFAULT 'unknown'
                                CHECK (purpose IN ('cv','credential','certificate','id_doc','unknown')),
    include_for_review      BOOLEAN NOT NULL DEFAULT TRUE,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS hiring_intake_media_intake_id_idx
    ON hiring_intake_media(intake_id);

-- Prevent duplicate rows for the same message in the same intake
CREATE UNIQUE INDEX IF NOT EXISTS hiring_intake_media_unique_msg
    ON hiring_intake_media(intake_id, telegram_message_id);
