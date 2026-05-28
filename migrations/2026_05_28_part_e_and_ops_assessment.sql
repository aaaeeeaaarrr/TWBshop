-- Part E hiring-facts questions + ops_messages assessment source
-- Idempotent: safe to re-run
--
-- Changes:
--   1. Expand assessment_source CHECK to include 'ops_messages'
--   2. Expand assessment_context CHECK to include 'attendance_review'
--   3. Insert Part E questions into hiring_quiz_questions (ON CONFLICT DO NOTHING)

-- ── assessment_source expansion ───────────────────────────────────────────────

ALTER TABLE hiring_assessments
    DROP CONSTRAINT IF EXISTS hiring_assessments_assessment_source_check;
ALTER TABLE hiring_assessments
    ADD CONSTRAINT hiring_assessments_assessment_source_check
        CHECK (assessment_source IN (
            'bot', 'legacy_paper', 'trial_observation', 'manual', 'ops_messages'
        ));

-- ── assessment_context expansion ──────────────────────────────────────────────

ALTER TABLE hiring_assessments
    DROP CONSTRAINT IF EXISTS hiring_assessments_assessment_context_check;
ALTER TABLE hiring_assessments
    ADD CONSTRAINT hiring_assessments_assessment_context_check
        CHECK (assessment_context IN (
            'hiring_screen', 'leadership_audit',
            'retraining_review', 'promotion_review', 'trial_review',
            'attendance_review'
        ));

-- ── Part E questions ──────────────────────────────────────────────────────────
-- Part E comes after D-Final and before follow-ups.
-- section='E-always'   → shown to every candidate
-- section='E-trigger'  → shown only when trigger condition fires (evaluated in code)
-- section='E-final'    → always last (first-3-days self-commitment)

INSERT INTO hiring_quiz_questions
    (id, quiz_version_id, part, section, display_order,
     question_text_en, question_text_km,
     answer_type, options, correct_answer,
     trait_tags, severity_if_wrong, requires_verbal_retest, active)
VALUES

-- E-A1: Exact start date
(
    'E-A1', 1, 'E', 'E-always', 1,
    'What is the exact date you can start working here? Write the day, month, and year. If you are not sure, write the earliest possible date and explain why.',
    'តើថ្ងៃណា ខែណា ឆ្នាំណា ដែលប្អូនអាចចាប់ផ្ដើមធ្វើការបានដំបូង? សរសេរថ្ងៃ ខែ ឆ្នាំ។ បើប្អូនមិនច្បាស់ សូមសរសេរថ្ងៃដំបូងបំផុតដែលអាចធ្វើបាន និងពន្យល់មូលហេតុ។',
    'free_text', NULL,
    '{"rubric": "Must give a specific date or narrow range. Vague = flag. Delayed start > 7 days → evaluate trigger E-T1."}',
    ARRAY['schedule', 'commitment', 'reliability'],
    'moderate', FALSE, TRUE
),

-- E-A2: Availability next 30 days
(
    'E-A2', 1, 'E', 'E-always', 2,
    'For the next 30 days: which days and hours are you available to work? Are there any specific days you definitely cannot work? List them.',
    'ក្នុង ៣០ ថ្ងៃខាងមុខ: ថ្ងៃណា និងម៉ោងណា ដែលប្អូនអាចធ្វើការបាន? តើមានថ្ងៃណាខ្លះ ដែលប្អូនមិនអាចធ្វើការដាច់ខាត? សរសេរទាំងអស់។',
    'free_text', NULL,
    '{"rubric": "Flag if full 30-day blackout, recurring day blocks, or very limited hours. Cross-check against Part A schedule answers."}',
    ARRAY['schedule', 'availability'],
    'moderate', FALSE, TRUE
),

-- E-A3: School / current job status
(
    'E-A3', 1, 'E', 'E-always', 3,
    'Are you currently studying at school or university? Are you currently working at another job? Answer both questions separately.',
    'ប្អូនកំពុងរៀននៅសាលា ឬមហាវិទ្យាល័យឬទេ? ប្អូនកំពុងធ្វើការនៅកន្លែងផ្សេងទៀតដែរឬទេ? សូមឆ្លើយទាំងពីរប្រការដាច់ពីគ្នា។',
    'free_text', NULL,
    '{"rubric": "Triggers: study keywords → E-T1 (exam communication). Job keywords → E-T2 (last working day). Both → both triggers."}',
    ARRAY['availability', 'schedule', 'commitment'],
    'moderate', FALSE, TRUE
),

-- E-A4: Known leave / exam dates
(
    'E-A4', 1, 'E', 'E-always', 4,
    'In the next 30 days, do you have any known leave, exams, travel, or important family events? If yes, list the exact dates. If no, write None.',
    'ក្នុង ៣០ ថ្ងៃខាងមុខ តើប្អូនមានវត្តមាន ការប្រឡង ការធ្វើដំណើរ ឬព្រឹត្តិការណ៍គ្រួសារសំខាន់ ដែលប្អូនដឹងជាស្រេចឬ? បើមាន សូមសរសេរថ្ងៃច្បាស់លាស់។ បើគ្មាន សរសេរ None។',
    'free_text', NULL,
    '{"rubric": "Flag any conflicts with expected shift pattern. Vague answer (maybe, not sure) = weak. Specific dates = strong self-awareness."}',
    ARRAY['schedule', 'reliability', 'honesty'],
    'moderate', FALSE, TRUE
),

-- E-A5: Transport + backup
(
    'E-A5', 1, 'E', 'E-always', 5,
    'How do you travel to work? If your main transport fails or is not available, what is your backup plan?',
    'ប្អូនធ្វើដំណើរមកធ្វើការដោយរបៀបណា? បើអ្វីដែលប្អូនប្រើធ្វើដំណើរមានបញ្ហា ឬមិនអាចប្រើបាន តើប្អូននឹងធ្វើអ្វី?',
    'free_text', NULL,
    '{"rubric": "No backup plan = risk flag. Previous attendance issues often cite transport. Specific backup = reliability indicator."}',
    ARRAY['reliability', 'punctuality'],
    'minor', FALSE, TRUE
),

-- E-T1: Studying → exam communication (trigger: study keywords in E-A3)
(
    'E-T1', 1, 'E', 'E-trigger', 6,
    'You mentioned you are studying. If an exam date falls on the same day as your work shift: how many days in advance would you inform management? Choose the best answer.',
    'ប្អូននិយាយថាកំពុងរៀន។ បើការប្រឡងរបស់ប្អូនធ្លាក់ត្រូវថ្ងៃតែមួយជាមួយវេនធ្វើការ: ប្អូននឹងប្រាប់ការគ្រប់គ្រងមុននឹងប៉ុន្មានថ្ងៃ? ជ្រើសរើសចម្លើយដ៏ល្អបំផុត។',
    'single_choice',
    '{"A": "More than a week before the conflict", "B": "The day before", "C": "The same morning", "D": "I would not come and explain after"}',
    '{"correct": "A", "rubric": "A = strong. B = acceptable but weak. C = risk. D = red flag."}',
    ARRAY['communication', 'reliability', 'schedule_honesty'],
    'moderate', FALSE, TRUE
),

-- E-T2: Current/previous job → last working day + salary (trigger: job keywords in E-A3 or C-Q1 non-empty)
(
    'E-T2', 1, 'E', 'E-trigger', 7,
    'You mentioned you are currently working somewhere. What is your last working day at that job? Has your current employer been told you are leaving? Also, break down your current pay: base salary + any bonus + food allowance + hours per day and days per week.',
    'ប្អូននិយាយថាកំពុងធ្វើការនៅកន្លែងផ្សេង។ ថ្ងៃចុងក្រោយដែលប្អូននឹងធ្វើការនៅទីនោះគឺថ្ងៃណា? តើកន្លែងចាស់ដឹងថាប្អូននឹងចេញឬ? ហើយសូមរៀបរាប់ប្រាក់ខែ: ប្រាក់ខែ + Bonus + អាហារ + ម៉ោងក្នុងមួយថ្ងៃ + ថ្ងៃក្នុងមួយអាទិត្យ។',
    'free_text', NULL,
    '{"rubric": "No exact last day = weak. Employer not told = risk (may leave suddenly). Salary breakdown: check for inflation claims, vague ranges, tips included."}',
    ARRAY['honesty', 'commitment', 'schedule', 'salary_history'],
    'moderate', FALSE, TRUE
),

-- E-Final: First-3-days self-commitment (always last)
(
    'E-Final', 1, 'E', 'E-final', 8,
    'In your own words: what should management be able to see from you in your first 3 days here? Write at least 2 specific things.',
    'ជាពាក្យរបស់ប្អូនផ្ទាល់: ក្នុង ៣ ថ្ងៃដំបូងរបស់ប្អូននៅទីនេះ តើការគ្រប់គ្រងគួរតែឃើញអ្វីពីប្អូន? សរសេរ ២ ចំណុចជាក់លាក់ យ៉ាងតិច។',
    'free_text', NULL,
    '{"rubric": "Generic = weak (on time, work hard). Specific and role-aware = strong. This answer is stored for trial comparison."}',
    ARRAY['self_awareness', 'commitment', 'first_3_days'],
    'moderate', FALSE, TRUE
)

ON CONFLICT (id) DO NOTHING;
