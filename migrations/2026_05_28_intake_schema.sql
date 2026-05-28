-- Intake funnel for public-ad applicants.
-- Handles everything from first message to staff-confirmed arrival.
-- No Claude API calls occur before intake_status = 'test_unlocked'.

CREATE TABLE IF NOT EXISTS hiring_intake_sessions (
    id                      serial PRIMARY KEY,
    telegram_chat_id        bigint NOT NULL UNIQUE,
    telegram_user_id        bigint NOT NULL,
    sender_name             text,

    -- State machine
    intake_status           text NOT NULL DEFAULT 'language_check',

    -- Language: 'en' = bilingual output, 'km' = Khmer-only output
    language                text NOT NULL DEFAULT 'en',

    -- CV
    cv_submitted            boolean NOT NULL DEFAULT false,
    cv_format               text,  -- 'photo', 'document', 'text'

    -- Voice escalation
    voice_warning_sent      boolean NOT NULL DEFAULT false,
    voice_strike_count      int NOT NULL DEFAULT 0,

    -- Appointment
    appointment_slot        timestamptz,
    appointment_confirmed_at timestamptz,

    -- Outcome
    arrived                 boolean,
    no_show                 boolean NOT NULL DEFAULT false,

    -- Block reason
    intake_blocked_reason   text,

    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hiring_intake_flags (
    id          serial PRIMARY KEY,
    intake_id   int NOT NULL REFERENCES hiring_intake_sessions(id) ON DELETE CASCADE,
    flag        text NOT NULL,
    severity    text NOT NULL DEFAULT 'gap_low',
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (intake_id, flag)
);

-- Index for lookup by appointment slot (day-of reminders)
CREATE INDEX IF NOT EXISTS idx_intake_slot ON hiring_intake_sessions (appointment_slot)
    WHERE intake_status = 'appointment_set';
