-- hiring_intake_events: raw evidence trail of every inbound applicant event.
-- Every text, photo, document, voice, sticker, callback, location — stored before any analysis.
-- AI access is gated by ai_allowed_stage; media is never analyzed before arrival.

CREATE TABLE IF NOT EXISTS hiring_intake_events (
    id                      SERIAL PRIMARY KEY,
    intake_id               INTEGER NOT NULL REFERENCES hiring_intake_sessions(id) ON DELETE CASCADE,
    telegram_chat_id        BIGINT NOT NULL,
    telegram_user_id        BIGINT,
    telegram_message_id     BIGINT,
    event_type              TEXT NOT NULL CHECK (event_type IN (
                                'text','photo','document','voice','video_note',
                                'sticker','callback','location','unknown')),
    text                    TEXT,
    caption                 TEXT,
    file_id                 TEXT,
    file_unique_id          TEXT,
    media_group_id          TEXT,
    callback_data           TEXT,
    current_intake_status   TEXT NOT NULL,
    purpose                 TEXT NOT NULL DEFAULT 'unknown',
    -- cv_document | cv_photo | location_question | appointment_question |
    -- unknown_after_appointment | voice_attempt | button_tap | text_cv |
    -- salary_question | refusal_signal | application_text | unknown
    include_for_review      BOOLEAN NOT NULL DEFAULT TRUE,
    ai_allowed_stage        TEXT NOT NULL DEFAULT 'after_arrival' CHECK (ai_allowed_stage IN (
                                'text_intake',    -- Haiku text-only during intake
                                'after_arrival',  -- only after staff confirms arrival
                                'after_unlock',   -- after TEST_UNLOCKED (quiz started)
                                'after_quiz'      -- after quiz complete (deep scoring)
                            )),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS hiring_intake_events_intake_id_idx
    ON hiring_intake_events(intake_id);
CREATE INDEX IF NOT EXISTS hiring_intake_events_status_idx
    ON hiring_intake_events(intake_id, current_intake_status);
