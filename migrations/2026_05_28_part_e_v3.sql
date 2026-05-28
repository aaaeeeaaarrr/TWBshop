-- Part E v3 fixes (ChatGPT review round 2, 2026-05-28):
-- 1. Add E-A1a: structured "Can you start within 3 days?" (structured E-T3 trigger)
-- 2. Convert all Part E question seeds to ON CONFLICT DO UPDATE
-- 3. Fix hiring_assessment_message_refs: rename message_id → ops_message_row_id,
--    add telegram_message_id, fix UNIQUE to include finding_id (one msg → multiple findings)
-- 4. Create staff_identity_aliases table
-- 5. Insert Seth's aliases + re-insert 4 previously skipped message refs
-- All idempotent.

-- ── E-A1a: structured delayed-start gate ─────────────────────────────────────
-- Replaces keyword guessing: E-A1a = B (No) or C (Not sure) → E-T3 fires.
-- E-A1 (exact date free text) is still always asked after E-A1a.

INSERT INTO hiring_quiz_questions
    (id, quiz_version_id, part, section, display_order,
     question_text_en, question_text_km,
     answer_type, options, correct_answer,
     trait_tags, severity_if_wrong, requires_verbal_retest, active)
VALUES (
    'E-A1a', 1, 'E', 'E-always', 0,
    'Can you start working here within the next 3 days?',
    'ប្អូនអាចចូលមកធ្វើការនៅទីនេះក្នុងរយៈពេល ៣ ថ្ងៃខាងមុខឬទេ?',
    'single_choice',
    '{"A": "Yes, within 3 days  /  បាទ/ចាស ក្នុង ៣ ថ្ងៃ",
      "B": "No, I need more time  /  ទេ ត្រូវការពេលបន្ថែម",
      "C": "Not sure yet  /  មិនប្រាកដនៅឡើយ"}',
    '{"correct": "A", "rubric": "B or C triggers E-T3 (delayed-start clarification). A = no delay trigger. This replaces keyword guessing from E-A1 free text — the structured answer is authoritative."}',
    ARRAY['schedule', 'availability', 'commitment'],
    'moderate', FALSE, TRUE
)
ON CONFLICT (id) DO UPDATE SET
    question_text_en = EXCLUDED.question_text_en,
    question_text_km  = EXCLUDED.question_text_km,
    options           = EXCLUDED.options,
    correct_answer    = EXCLUDED.correct_answer,
    active            = EXCLUDED.active;

-- ── Convert all original Part E seeds to ON CONFLICT DO UPDATE ────────────────
-- These were originally inserted with DO NOTHING; now they update on re-run.

INSERT INTO hiring_quiz_questions
    (id, quiz_version_id, part, section, display_order,
     question_text_en, question_text_km,
     answer_type, options, correct_answer,
     trait_tags, severity_if_wrong, requires_verbal_retest, active)
VALUES

(
    'E-A1', 1, 'E', 'E-always', 1,
    'What is the exact date you can start working here? Write the day, month, and year. If you are not sure, write the earliest possible date and explain why.',
    'តើថ្ងៃណា ខែណា ឆ្នាំណា ដែលប្អូនអាចចាប់ផ្តើមធ្វើការបានដំបូង? សរសេរថ្ងៃ ខែ ឆ្នាំ។ បើប្អូនមិនច្បាស់ សូមសរសេរថ្ងៃដំបូងបំផុតដែលអាចធ្វើបាន និងពន្យល់មូលហេតុ។',
    'free_text', NULL,
    '{"rubric": "Must give a specific date or narrow range. Vague = flag. E-A1a already determined if start is delayed — this field records the exact date."}',
    ARRAY['schedule', 'commitment', 'reliability'],
    'moderate', FALSE, TRUE
),
(
    'E-A2', 1, 'E', 'E-always', 2,
    'For the next 30 days: which days and hours are you available to work? Are there any specific days you definitely cannot work? List them.',
    'ក្នុង ៣០ ថ្ងៃខាងមុខ: ថ្ងៃណា និងម៉ោងណា ដែលប្អូនអាចធ្វើការបាន? តើមានថ្ងៃណាខ្លះ ដែលប្អូនមិនអាចធ្វើការដាច់ខាត? សរសេរទាំងអស់។',
    'free_text', NULL,
    '{"rubric": "Flag if full 30-day blackout, recurring day blocks, or very limited hours. Cross-check against Part A schedule answers."}',
    ARRAY['schedule', 'availability'],
    'moderate', FALSE, TRUE
),
(
    'E-A4', 1, 'E', 'E-always', 5,
    'In the next 30 days, do you have any known leave, exams, travel, or important family events? If yes, list the exact dates. If no, write None.',
    'ក្នុង ៣០ ថ្ងៃខាងមុខ តើប្អូនមានវត្តមាន ការប្រឡង ការធ្វើដំណើរ ឬព្រឹត្តិការណ៍គ្រួសារសំខាន់ ដែលប្អូនដឹងជាស្រេចឬ? បើមាន សូមសរសេរថ្ងៃច្បាស់លាស់។ បើគ្មាន សរសេរ None។',
    'free_text', NULL,
    '{"rubric": "Flag any conflicts with expected shift pattern. Vague answer (maybe, not sure) = weak. Specific dates = strong self-awareness. Exam keywords here also trigger E-T1."}',
    ARRAY['schedule', 'reliability', 'honesty'],
    'moderate', FALSE, TRUE
),
(
    'E-A5', 1, 'E', 'E-always', 6,
    'How do you travel to work? If your main transport fails or is not available, what is your backup plan?',
    'ប្អូនធ្វើដំណើរមកធ្វើការដោយរបៀបណា? បើអ្វីដែលប្អូនប្រើធ្វើដំណើរមានបញ្ហា ឬមិនអាចប្រើបាន តើប្អូននឹងធ្វើអ្វី?',
    'free_text', NULL,
    '{"rubric": "No backup plan = risk flag. Previous attendance issues often cite transport. Specific backup = reliability indicator."}',
    ARRAY['reliability', 'punctuality'],
    'minor', FALSE, TRUE
),
(
    'E-T1', 1, 'E', 'E-trigger', 7,
    'You mentioned you are studying. If an exam date falls on the same day as your work shift: how many days in advance would you inform management? Choose the best answer.',
    'ប្អូននិយាយថាកំពុងរៀន។ បើការប្រឡងរបស់ប្អូនធ្លាក់ត្រូវថ្ងៃតែមួយជាមួយវេនធ្វើការ: ប្អូននឹងប្រាប់ការគ្រប់គ្រងមុននឹងប៉ុន្មានថ្ងៃ? ជ្រើសរើសចម្លើយដ៏ល្អបំផុត។',
    'single_choice',
    '{"A": "More than a week before the conflict", "B": "The day before", "C": "The same morning", "D": "I would not come and explain after"}',
    '{"correct": "A", "rubric": "A = strong. B = acceptable but weak. C = risk. D = red flag."}',
    ARRAY['communication', 'reliability', 'schedule_honesty'],
    'moderate', FALSE, TRUE
),
(
    'E-T2', 1, 'E', 'E-trigger', 8,
    'You mentioned you are currently working somewhere. What is your last working day at that job? Has your current employer been told you are leaving? Also, break down your current pay: base salary + any bonus + food allowance + hours per day and days per week.',
    'ប្អូននិយាយថាកំពុងធ្វើការនៅកន្លែងផ្សេង។ ថ្ងៃចុងក្រោយដែលប្អូននឹងធ្វើការនៅទីនោះគឺថ្ងៃណា? តើកន្លែងចាស់ដឹងថាប្អូននឹងចេញឬ? ហើយសូមរៀបរាប់ប្រាក់ខែ: ប្រាក់ខែ + Bonus + អាហារ + ម៉ោងក្នុងមួយថ្ងៃ + ថ្ងៃក្នុងមួយអាទិត្យ។',
    'free_text', NULL,
    '{"rubric": "No exact last day = weak. Employer not told = risk. Salary breakdown: flag inflation claims, vague ranges, tips included."}',
    ARRAY['honesty', 'commitment', 'schedule', 'salary_history'],
    'moderate', FALSE, TRUE
),
(
    'E-Final', 1, 'E', 'E-final', 10,
    'In your own words: what should management be able to see from you in your first 3 days here? Write at least 2 specific things.',
    'ជាពាក្យរបស់ប្អូនផ្ទាល់: ក្នុង ៣ ថ្ងៃដំបូងរបស់ប្អូននៅទីនេះ តើការគ្រប់គ្រងគួរតែឃើញអ្វីពីប្អូន? សរសេរ ២ ចំណុចជាក់លាក់ យ៉ាងតិច។',
    'free_text', NULL,
    '{"rubric": "Generic = weak (on time, work hard). Specific and role-aware = strong. This answer is stored for trial comparison."}',
    ARRAY['self_awareness', 'commitment', 'first_3_days'],
    'moderate', FALSE, TRUE
)

ON CONFLICT (id) DO UPDATE SET
    question_text_en = EXCLUDED.question_text_en,
    question_text_km  = EXCLUDED.question_text_km,
    options           = EXCLUDED.options,
    correct_answer    = EXCLUDED.correct_answer,
    answer_type       = EXCLUDED.answer_type,
    active            = EXCLUDED.active;

-- ── Fix hiring_assessment_message_refs ────────────────────────────────────────
-- Problem: UNIQUE(assessment_id, chat_id, message_id) prevents one message from
-- supporting multiple findings. Rename message_id → ops_message_row_id to clarify
-- it stores ops_messages.id (internal PK), not the Telegram message_id.
-- Add telegram_message_id to store Telegram's actual message_id separately.
-- New unique constraint includes finding_id so one message can link to many findings.

ALTER TABLE hiring_assessment_message_refs
    RENAME COLUMN message_id TO ops_message_row_id;

ALTER TABLE hiring_assessment_message_refs
    ADD COLUMN IF NOT EXISTS telegram_message_id bigint;

-- Drop old unique constraint. Postgres truncates the auto-generated name to 63 chars.
-- The actual name on the server (verified 2026-05-28) is the truncated form below.
ALTER TABLE hiring_assessment_message_refs
    DROP CONSTRAINT IF EXISTS hiring_assessment_message_ref_assessment_id_chat_id_message_key;

-- Drop new constraint if it already exists (idempotent re-run)
ALTER TABLE hiring_assessment_message_refs
    DROP CONSTRAINT IF EXISTS hamr_unique_per_finding;

ALTER TABLE hiring_assessment_message_refs
    ADD CONSTRAINT hamr_unique_per_finding
        UNIQUE (assessment_id, finding_id, chat_id, ops_message_row_id);

-- Backfill telegram_message_id from ops_messages for existing rows
UPDATE hiring_assessment_message_refs mr
SET telegram_message_id = om.message_id
FROM ops_messages om
WHERE mr.chat_id = om.chat_id
  AND mr.ops_message_row_id = om.id
  AND mr.telegram_message_id IS NULL;

-- Re-insert the 4 message refs that were skipped by the old UNIQUE constraint
-- (one message supporting multiple findings is now allowed)

-- finding_id=93 (no_show_exam_claim), ops_message_row_id=792886
INSERT INTO hiring_assessment_message_refs
    (assessment_id, finding_id, chat_id, ops_message_row_id, confidence, notes)
VALUES (5, 93, -4980513319, 792886, 'confirmed',
    'Met Solina: ''Mr Piseth ask permission again today he can''t come to work because have exams.'' '
    'Full no-show May 27. Same-day notice. Word ''again'' confirms habitual pattern.')
ON CONFLICT (assessment_id, finding_id, chat_id, ops_message_row_id) DO NOTHING;

-- finding_id=94 (rotating_excuse_pattern): three messages showing different excuses
INSERT INTO hiring_assessment_message_refs
    (assessment_id, finding_id, chat_id, ops_message_row_id, confidence, notes)
VALUES (5, 94, -4980513319, 792213, 'likely',
    'Excuse 1 (Mar 11): SAM PHARM: ''Mr pisey late 30mn because busy with family at mom house.''')
ON CONFLICT (assessment_id, finding_id, chat_id, ops_message_row_id) DO NOTHING;

INSERT INTO hiring_assessment_message_refs
    (assessment_id, finding_id, chat_id, ops_message_row_id, confidence, notes)
VALUES (5, 94, -4980513319, 792258, 'confirmed',
    'Excuse 2 (Apr 27): Lina So: ''Mr Piseth can''t come on time he ask to come at 4pm.'' No reason given.')
ON CONFLICT (assessment_id, finding_id, chat_id, ops_message_row_id) DO NOTHING;

INSERT INTO hiring_assessment_message_refs
    (assessment_id, finding_id, chat_id, ops_message_row_id, confidence, notes)
VALUES (5, 94, -4980513319, 792886, 'confirmed',
    'Excuse 3 (May 27): Met Solina: ''can''t come to work because have exams.'' Third distinct reason across 3 months.')
ON CONFLICT (assessment_id, finding_id, chat_id, ops_message_row_id) DO NOTHING;

-- Backfill telegram_message_id for newly inserted rows too
UPDATE hiring_assessment_message_refs mr
SET telegram_message_id = om.message_id
FROM ops_messages om
WHERE mr.chat_id = om.chat_id
  AND mr.ops_message_row_id = om.id
  AND mr.telegram_message_id IS NULL;

-- ── staff_identity_aliases table ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS staff_identity_aliases (
    id               SERIAL PRIMARY KEY,
    candidate_id     integer REFERENCES hiring_candidates(id),
    alias_text       text NOT NULL,
    telegram_sender_name text,
    telegram_user_id bigint,
    chat_id          bigint,
    confidence       text DEFAULT 'confirmed'
                     CHECK (confidence IN ('confirmed', 'likely', 'inferred')),
    confirmed_by     text,
    notes            text,
    created_at       timestamptz DEFAULT now(),
    UNIQUE (candidate_id, alias_text)
);

-- Seth (Phan Piseth, candidate_id=27) known aliases
INSERT INTO staff_identity_aliases
    (candidate_id, alias_text, telegram_sender_name, chat_id, confidence, confirmed_by, notes)
VALUES

(27, 'Seth',
    'Seth 🫵', -1003952029131,
    'confirmed',
    'Self-introduction Stock Checks 2026-05-27: ''Hello Sir,My name Phan Piseth, call me Seth'' (ops_messages id=792905)',
    'Primary call name used in all group chats.'),

(27, 'Phan Piseth',
    NULL, NULL,
    'confirmed',
    'Self-introduction Stock Checks 2026-05-27 (same message). Also used by supervisors in reports.',
    'Full legal name. Supervisors Lina So, Rath Phal, Bart KimHeng, Met Solina all use this.'),

(27, 'Mr Piseth',
    NULL, -4980513319,
    'confirmed',
    'Used by Lina So (ops_messages 792258), Rath Phal (792273), Met Solina (792886), Bart KimHeng (792256).',
    'How supervisors refer to him in Supervisors TWB group. Unambiguous in 2026 messages.'),

(27, 'Mr pisey',
    'SAM PHARM', -4980513319,
    'likely',
    'SAM PHARM message 2026-03-11 (ops_messages id=792213): content matches known Mar 11 late incident.',
    'SAM PHARM often writes ''pisey'' for Piseth. Likely = Seth, but SAM PHARM also reports SAM-side Mr Pisey. Do not assume without corroborating evidence.'),

(27, 'Mr Sith',
    'SAM PHARM', -4980513319,
    'likely',
    'SAM PHARM message 2026-03-13 (ops_messages id=792215): ''Mr Sith he payback 1h already.'' Typo for Seth.',
    'Likely typo for Seth. Same sender (SAM PHARM) same period.')

ON CONFLICT (candidate_id, alias_text) DO NOTHING;
