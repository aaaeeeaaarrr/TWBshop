-- Part E structural fixes (ChatGPT review 2026-05-28):
-- 1. Split E-A3 into E-A3a (studying?) + E-A3b (working?) structured Yes/No
-- 2. Add E-T3: delayed-start clarification (Lyhouy trigger)
-- 3. Add answer_sensitivity column to hiring_quiz_questions
-- 4. Add part_e_triggered column to hiring_quiz_attempts
-- 5. Create hiring_assessment_message_refs for ops-message evidence links
-- All idempotent (IF NOT EXISTS / ON CONFLICT DO UPDATE).

-- ── Schema additions ──────────────────────────────────────────────────────────

ALTER TABLE hiring_quiz_questions
    ADD COLUMN IF NOT EXISTS answer_sensitivity text DEFAULT 'normal';

ALTER TABLE hiring_quiz_questions
    DROP CONSTRAINT IF EXISTS hiring_quiz_questions_answer_sensitivity_check;

ALTER TABLE hiring_quiz_questions
    ADD CONSTRAINT hiring_quiz_questions_answer_sensitivity_check
        CHECK (answer_sensitivity IN ('normal', 'owner_only'));

ALTER TABLE hiring_quiz_attempts
    ADD COLUMN IF NOT EXISTS part_e_triggered text[] DEFAULT NULL;

-- ── Deactivate old E-A3 (replaced by E-A3a + E-A3b) ─────────────────────────

UPDATE hiring_quiz_questions SET active = FALSE WHERE id = 'E-A3';

-- ── Insert / update Part E v2 questions ──────────────────────────────────────
-- ON CONFLICT DO UPDATE so re-running this migration updates question text.

INSERT INTO hiring_quiz_questions
    (id, quiz_version_id, part, section, display_order,
     question_text_en, question_text_km,
     answer_type, options, correct_answer,
     trait_tags, severity_if_wrong, requires_verbal_retest, active)
VALUES

-- E-A3a: Currently studying? (structured Yes/No — replaces keyword guessing)
(
    'E-A3a', 1, 'E', 'E-always', 3,
    'Are you currently studying at school or university?',
    'ប្អូនកំពុងរៀននៅសាលា ឬមហាវិទ្យាល័យឬទេ?',
    'single_choice',
    '{"A": "Yes  /  បាទ/ចាស", "B": "No  /  ទេ"}',
    '{"correct": "B", "rubric": "A triggers E-T1 (exam communication timing)."}',
    ARRAY['availability', 'schedule'],
    'moderate', FALSE, TRUE
),

-- E-A3b: Currently working elsewhere? (structured Yes/No)
(
    'E-A3b', 1, 'E', 'E-always', 4,
    'Are you currently working at another job?',
    'ប្អូនកំពុងធ្វើការនៅកន្លែងផ្សេងទៀតដែរឬទេ?',
    'single_choice',
    '{"A": "Yes  /  បាទ/ចាស", "B": "No  /  ទេ"}',
    '{"correct": "B", "rubric": "A triggers E-T2 (last working day + salary breakdown)."}',
    ARRAY['availability', 'commitment'],
    'moderate', FALSE, TRUE
),

-- E-T3: Delayed-start clarification (Lyhouy trigger — fires when E-A1 signals delay)
(
    'E-T3', 1, 'E', 'E-trigger', 9,
    'You mentioned your start date is not immediate. What exactly is stopping you from starting sooner? And is there any shift arrangement — for example, different hours or fewer days — that would allow you to start earlier?',
    'ប្អូននិយាយថាថ្ងៃចូលធ្វើការមិនមែនភ្លាមៗ។ តើអ្វីដែលធ្វើឲ្យប្អូនមិនអាចចាប់ផ្តើមមុនជាងនេះ? ហើយតើមានការរៀបចំវេន ឧទាហរណ៍ ម៉ោងផ្សេង ឬថ្ងៃតិចជាង ដែលអាចឲ្យប្អូនចាប់ផ្តើមមុនបានទេ?',
    'free_text', NULL,
    '{"rubric": "Vague or evasive = red flag. Clear logistical reason (notice period, travel, move) = acceptable. Openness to a schedule adjustment = strong positive signal. This question surfaces the Lyhouy pattern: candidates who state a hard start date but would accept different conditions sooner."}',
    ARRAY['schedule', 'commitment', 'availability'],
    'moderate', FALSE, TRUE
)

ON CONFLICT (id) DO UPDATE SET
    question_text_en  = EXCLUDED.question_text_en,
    question_text_km  = EXCLUDED.question_text_km,
    options           = EXCLUDED.options,
    correct_answer    = EXCLUDED.correct_answer,
    answer_type       = EXCLUDED.answer_type,
    active            = EXCLUDED.active;

-- Mark E-T2 as owner_only — contains salary breakdown data, never include in group reports
UPDATE hiring_quiz_questions SET answer_sensitivity = 'owner_only' WHERE id = 'E-T2';

-- Renumber display_order after inserting E-A3a/E-A3b at slots 3 and 4
UPDATE hiring_quiz_questions SET display_order = 5  WHERE id = 'E-A4';
UPDATE hiring_quiz_questions SET display_order = 6  WHERE id = 'E-A5';
UPDATE hiring_quiz_questions SET display_order = 7  WHERE id = 'E-T1';
UPDATE hiring_quiz_questions SET display_order = 8  WHERE id = 'E-T2';
UPDATE hiring_quiz_questions SET display_order = 10 WHERE id = 'E-Final';

-- ── ops-message evidence reference table ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS hiring_assessment_message_refs (
    id            SERIAL PRIMARY KEY,
    assessment_id integer NOT NULL REFERENCES hiring_assessments(id),
    finding_id    integer REFERENCES hiring_feedback_points(id),
    chat_id       bigint  NOT NULL,
    message_id    bigint  NOT NULL,
    sent_at       text,
    sender_name   text,
    message_text  text,
    media_ref     text,
    confidence    text DEFAULT 'confirmed'
                  CHECK (confidence IN ('confirmed', 'likely', 'inferred')),
    notes         text,
    created_at    timestamptz DEFAULT now(),
    UNIQUE (assessment_id, chat_id, message_id)
);
