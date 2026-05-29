-- AI decision log for intake funnel (Haiku intent + CV extraction calls)
-- Every Haiku call during intake is stored here for calibration and audit.

CREATE TABLE IF NOT EXISTS hiring_intake_ai_events (
    id              SERIAL PRIMARY KEY,
    intake_id       INTEGER NOT NULL REFERENCES hiring_intake_sessions(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL,   -- intent_check | cv_extraction | deflection_check
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    input_text      TEXT NOT NULL,
    output_json     TEXT NOT NULL,
    intent          TEXT,            -- applying | clear_refusal | wrong_number | confused | error
    confidence      FLOAT,
    action_taken    TEXT,            -- continue | close | reprompt | fallback_continue
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS hiring_intake_ai_events_intake_id_idx
    ON hiring_intake_ai_events(intake_id);

-- Deflection counter on intake sessions
ALTER TABLE hiring_intake_sessions
    ADD COLUMN IF NOT EXISTS cv_deflection_count INTEGER NOT NULL DEFAULT 0;
