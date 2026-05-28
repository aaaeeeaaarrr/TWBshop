import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    # ── 1. Quiz versions ──────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_quiz_versions (
        id SERIAL PRIMARY KEY,
        version_name TEXT NOT NULL UNIQUE,
        description TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    INSERT INTO hiring_quiz_versions (version_name, description)
    VALUES ('Final v3', 'Candidate Staff Interview Test - Final Edited v3')
    ON CONFLICT (version_name) DO NOTHING;
    """)

    # ── 2. Quiz questions ─────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_quiz_questions (
        id TEXT PRIMARY KEY,
        quiz_version_id INTEGER REFERENCES hiring_quiz_versions(id),
        part TEXT NOT NULL,
        section TEXT,
        display_order INTEGER,
        question_text_en TEXT,
        question_text_km TEXT,
        answer_type TEXT NOT NULL CHECK (answer_type IN (
            'yes_no_not_sure','single_choice','free_text','ranking','rewrite'
        )),
        options JSONB,
        correct_answer JSONB,
        trait_tags TEXT[],
        severity_if_wrong TEXT CHECK (severity_if_wrong IN ('critical','moderate','minor')),
        requires_verbal_retest BOOLEAN DEFAULT FALSE,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 3. Sessions (invite tokens — store hash, never raw) ───────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_sessions (
        id SERIAL PRIMARY KEY,
        token_hash TEXT UNIQUE NOT NULL,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        created_by_staff TEXT,
        telegram_user_id BIGINT,
        telegram_username TEXT,
        expires_at TIMESTAMPTZ NOT NULL,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        abandoned_at TIMESTAMPTZ,
        abandoned_at_question_id TEXT REFERENCES hiring_quiz_questions(id),
        used_at TIMESTAMPTZ,
        status TEXT CHECK (status IN (
            'created','started','completed','expired','abandoned','cancelled'
        )) DEFAULT 'created',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 4. Quiz attempts (one per test sitting) ───────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_quiz_attempts (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        session_id INTEGER REFERENCES hiring_sessions(id),
        quiz_version_id INTEGER REFERENCES hiring_quiz_versions(id),
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        total_duration_seconds INTEGER,
        started_by_staff TEXT,
        interview_location TEXT,
        arrival_status TEXT CHECK (arrival_status IN (
            'on_time','late','no_show','unknown'
        )),
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 5. Quiz answers (core evidence table) ────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_quiz_answers (
        id SERIAL PRIMARY KEY,
        attempt_id INTEGER REFERENCES hiring_quiz_attempts(id),
        question_id TEXT REFERENCES hiring_quiz_questions(id),
        raw_answer TEXT,
        normalized_answer TEXT,
        is_correct BOOLEAN,
        completeness_score INTEGER CHECK (completeness_score BETWEEN 0 AND 3),
        contradiction_score INTEGER DEFAULT 0 CHECK (contradiction_score BETWEEN 0 AND 3),
        time_spent_seconds INTEGER,
        skipped BOOLEAN DEFAULT FALSE,
        graded_by TEXT,
        graded_at TIMESTAMPTZ,
        grader_notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 6. Answer events (Telegram event trail) ───────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_answer_events (
        id SERIAL PRIMARY KEY,
        answer_id INTEGER REFERENCES hiring_quiz_answers(id),
        event_type TEXT NOT NULL CHECK (event_type IN (
            'question_sent','answer_received','answer_edited',
            'question_deleted','timeout','skipped'
        )),
        telegram_message_id BIGINT,
        event_at TIMESTAMPTZ DEFAULT NOW(),
        payload JSONB
    );
    """)

    # ── 7. CV data (parsed CV summary) ───────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_cv_data (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        raw_cv_file_url TEXT,
        parsed_json JSONB,
        claimed_salary TEXT,
        current_job TEXT,
        availability_summary TEXT,
        date_precision_score INTEGER CHECK (date_precision_score BETWEEN 0 AND 5),
        gap_risk_score INTEGER CHECK (gap_risk_score BETWEEN 0 AND 5),
        scoring_method TEXT CHECK (scoring_method IN ('rule','claude','human')),
        scored_by TEXT,
        scored_at TIMESTAMPTZ,
        parsed_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 8. CV jobs (normalized job history) ──────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_cv_jobs (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        employer_name TEXT,
        job_title TEXT,
        start_date DATE,
        end_date DATE,
        start_precision TEXT CHECK (start_precision IN (
            'day','month','year','vague','missing'
        )),
        end_precision TEXT CHECK (end_precision IN (
            'day','month','year','vague','missing'
        )),
        duration_claimed TEXT,
        reason_left TEXT,
        salary_claimed TEXT,
        source_text TEXT,
        stability_score INTEGER CHECK (stability_score BETWEEN 0 AND 5),
        red_flag_notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 9. Feedback points (replaces hiring_feedback_templates) ──────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_feedback_points (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        quiz_answer_id INTEGER REFERENCES hiring_quiz_answers(id),
        version TEXT DEFAULT 'v1.0',
        source_type TEXT CHECK (source_type IN (
            'quiz','cv','observation','trial','draft'
        )),
        source_ref TEXT,
        answer_summary TEXT,
        trait_detected TEXT,
        severity TEXT CHECK (severity IN (
            'strength_high','strength_medium',
            'gap_minor','gap_medium','gap_critical','risk_critical'
        )),
        principle_tag TEXT,
        evidence_status TEXT DEFAULT 'draft_unlinked' CHECK (evidence_status IN (
            'draft_unlinked','linked','verified','obsolete'
        )),
        specificity_score INTEGER DEFAULT 1 CHECK (specificity_score BETWEEN 0 AND 3),
        contradiction_score INTEGER DEFAULT 0 CHECK (contradiction_score BETWEEN 0 AND 3),
        point_number INTEGER,
        english_text TEXT NOT NULL,
        khmer_text TEXT NOT NULL,
        generated_by TEXT,
        reviewed_by TEXT,
        reviewed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        last_updated TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 10. Coaching messages sent to candidates ──────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_coaching_messages (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        session_id INTEGER REFERENCES hiring_sessions(id),
        sent_at TIMESTAMPTZ DEFAULT NOW(),
        message_type TEXT CHECK (message_type IN (
            'education','feedback','question','confirmation','offer','warning'
        )),
        total_word_count INTEGER,
        min_required_read_seconds INTEGER,
        read_time_seconds INTEGER,
        confirmation_text TEXT,
        passed_read_check BOOLEAN,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 11. Coaching message → feedback point join table ──────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_coaching_message_points (
        id SERIAL PRIMARY KEY,
        message_id INTEGER REFERENCES hiring_coaching_messages(id) ON DELETE CASCADE,
        feedback_point_id INTEGER REFERENCES hiring_feedback_points(id),
        point_order INTEGER NOT NULL
    );
    """)

    # ── 12. Observations (real-world notes at any phase) ──────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_observations (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        observer_name TEXT,
        observed_at TIMESTAMPTZ DEFAULT NOW(),
        phase TEXT CHECK (phase IN (
            'arrival','waiting','test','interview',
            'offer','first_day','trial','other'
        )),
        observation_type TEXT,
        severity TEXT CHECK (severity IN (
            'strength','neutral','minor_gap','medium_risk','critical_risk'
        )),
        notes TEXT,
        linked_question_id TEXT REFERENCES hiring_quiz_questions(id),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── 13. Trial outcomes (3/7/30-day validation) ────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hiring_trial_outcomes (
        id SERIAL PRIMARY KEY,
        candidate_id INTEGER REFERENCES hiring_candidates(id),
        observed_at DATE,
        day_mark INTEGER CHECK (day_mark IN (1,3,7,14,30,90)),
        observer_name TEXT,
        punctuality TEXT,
        attitude TEXT,
        accuracy TEXT,
        team_behavior TEXT,
        honesty_incidents TEXT,
        instruction_memory TEXT,
        phone_discipline TEXT,
        customer_behavior TEXT,
        overall_rating INTEGER CHECK (overall_rating BETWEEN 1 AND 5),
        notes TEXT,
        prediction_matched BOOLEAN,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # ── ALTER hiring_candidates: add score cache metadata ────────────────────
    cur.execute("""
    ALTER TABLE hiring_candidates
        ADD COLUMN IF NOT EXISTS score_source_attempt_id INTEGER
            REFERENCES hiring_quiz_attempts(id),
        ADD COLUMN IF NOT EXISTS score_cache_updated_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS score_cache_method TEXT CHECK (
            score_cache_method IN (
                'auto_graded','claude_scored','human_scored','manual_entry'
            )
        );
    """)

    # ── Migrate hiring_feedback_templates → hiring_feedback_points ────────────
    cur.execute("""
    INSERT INTO hiring_feedback_points (
        candidate_id, version, source_type, evidence_status,
        specificity_score, principle_tag, point_number,
        english_text, khmer_text, generated_by, created_at
    )
    SELECT
        candidate_id,
        'v1.0',
        'draft',
        'draft_unlinked',
        1,
        topic,
        point_number,
        english_text,
        khmer_text,
        'chatgpt',
        created_at
    FROM hiring_feedback_templates;
    """)

    conn.commit()
    print('Migration committed.')

    # ── Verification ──────────────────────────────────────────────────────────
    tables = [
        'hiring_quiz_versions', 'hiring_quiz_questions', 'hiring_sessions',
        'hiring_quiz_attempts', 'hiring_quiz_answers', 'hiring_answer_events',
        'hiring_cv_data', 'hiring_cv_jobs', 'hiring_feedback_points',
        'hiring_coaching_messages', 'hiring_coaching_message_points',
        'hiring_observations', 'hiring_trial_outcomes',
    ]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f'  {t}: {cur.fetchone()[0]} rows')

    cur.execute("SELECT name, score_cache_method FROM hiring_candidates")
    for row in cur.fetchall():
        print(f'  candidate: {row}')

except Exception as e:
    conn.rollback()
    print(f'ERROR — rolled back: {e}')
    raise
finally:
    conn.close()
