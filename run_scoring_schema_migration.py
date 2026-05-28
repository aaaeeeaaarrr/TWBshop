import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    # ── 1. hiring_contradictions (new table) ─────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hiring_contradictions (
            id                  SERIAL PRIMARY KEY,
            attempt_id          INTEGER NOT NULL REFERENCES hiring_quiz_attempts(id) ON DELETE CASCADE,
            question_id_a       TEXT NOT NULL REFERENCES hiring_quiz_questions(id),
            question_id_b       TEXT NOT NULL REFERENCES hiring_quiz_questions(id),
            contradiction_type  VARCHAR(50) NOT NULL
                                    CHECK (contradiction_type IN (
                                        'tick_vs_written',
                                        'tick_vs_tick',
                                        'written_vs_written',
                                        'schedule_story',
                                        'cv_vs_written'
                                    )),
            severity            VARCHAR(20) NOT NULL DEFAULT 'moderate'
                                    CHECK (severity IN ('critical','moderate','minor')),
            description         TEXT,
            ai_flagged          BOOLEAN NOT NULL DEFAULT FALSE,
            human_confirmed     BOOLEAN,
            suppressed          BOOLEAN NOT NULL DEFAULT FALSE,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    print("hiring_contradictions: created")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_hiring_contradictions_attempt
            ON hiring_contradictions(attempt_id)
    """)

    # ── 2. hiring_quiz_attempts — add risk_profile + score_summary ───────────
    cur.execute("""
        ALTER TABLE hiring_quiz_attempts
            ADD COLUMN IF NOT EXISTS score_summary  JSONB,
            ADD COLUMN IF NOT EXISTS risk_profile   JSONB
    """)
    print("hiring_quiz_attempts: added score_summary, risk_profile")

    # score_summary shape (stored as JSONB, written by scorer):
    # {
    #   "score_a": 58, "score_a_max": 60,
    #   "score_b": 22, "score_b_max": 22,
    #   "d1_priority_score": 2,          -- 0-3
    #   "written_sections_scored": false, -- true once Claude scores C/D
    #   "contradiction_count": 0,
    #   "critical_wrong": ["A1-Q5","A4-Q38"],
    #   "not_sure_critical": ["A2-Q13"],
    #   "auto_graded_at": "2026-05-28T..."
    # }

    # risk_profile shape (stored as JSONB, written after rubric scoring):
    # {
    #   "honesty_logic": "strong",        -- strong/medium/weak
    #   "schedule_clarity": "clean",      -- clean/unclear/red_flag
    #   "completion_discipline": "strong",
    #   "customer_instinct": "trainable",
    #   "quiet_time_work_ethic": "unclear",
    #   "experience_credibility": "verified",
    #   "leadership_potential": "emerging",
    #   "trial_recommendation": "trial",  -- reject/trial/hire
    #   "generated_at": "2026-05-28T..."
    # }

    # ── 3. hiring_trial_outcomes — add quiet_time + schedule fields ──────────
    cur.execute("""
        ALTER TABLE hiring_trial_outcomes
            ADD COLUMN IF NOT EXISTS quiet_time_behavior      TEXT,
            ADD COLUMN IF NOT EXISTS schedule_story_match     TEXT
    """)
    print("hiring_trial_outcomes: added quiet_time_behavior, schedule_story_match")

    conn.commit()
    print("\nMigration complete.")

    # ── verify ───────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_name IN ('hiring_contradictions','hiring_quiz_attempts','hiring_trial_outcomes')
          AND column_name IN (
            'id','attempt_id','question_id_a','question_id_b','contradiction_type','severity',
            'description','ai_flagged','human_confirmed','suppressed',
            'score_summary','risk_profile',
            'quiet_time_behavior','schedule_story_match'
          )
        ORDER BY table_name, column_name
    """)
    print("\nVerification:")
    for row in cur.fetchall():
        print(" ", row)

except Exception as e:
    conn.rollback()
    print(f"ERROR — rolled back: {e}")
    raise
finally:
    cur.close()
    conn.close()
