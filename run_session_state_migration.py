import sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL
import psycopg2

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    # ── hiring_quiz_attempts — session state tracking ─────────────────────────
    cur.execute("""
        ALTER TABLE hiring_quiz_attempts
            ADD COLUMN IF NOT EXISTS attempt_status          TEXT NOT NULL DEFAULT 'created'
                CHECK (attempt_status IN (
                    'created','started','in_progress','abandoned',
                    'resumed','completed','expired','cancelled','reopened_by_staff'
                )),
            ADD COLUMN IF NOT EXISTS abandoned_at_question_id TEXT REFERENCES hiring_quiz_questions(id),
            ADD COLUMN IF NOT EXISTS resume_count             INTEGER NOT NULL DEFAULT 0
    """)
    print("hiring_quiz_attempts: added attempt_status, abandoned_at_question_id, resume_count")

    # ── hiring_sessions — token-level resume tracking ─────────────────────────
    cur.execute("""
        ALTER TABLE hiring_sessions
            ADD COLUMN IF NOT EXISTS resume_count   INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS reopened_by    TEXT
    """)
    print("hiring_sessions: added resume_count, reopened_by")

    conn.commit()
    print("\nMigration complete.")

    # ── verify ────────────────────────────────────────────────────────────────
    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_name IN ('hiring_quiz_attempts', 'hiring_sessions')
          AND column_name IN (
            'attempt_status','abandoned_at_question_id','resume_count','reopened_by'
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
