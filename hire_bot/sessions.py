"""
Session management for the hiring bot.

Token flow:
  Staff creates session → plain token sent once via DM → only SHA-256 hash stored in DB
  Candidate taps deep link → token verified → session bound to telegram_user_id
  Candidate answers questions → attempt progresses via record_answer()
  Session completed → status='completed', token permanently consumed

Resume rules (enforce via attempt.resume_count):
  First abandon                     → candidate can resume once freely
  Second abandon (resume_count ≥ 1) → staff must call reopen_by_staff()
  Completed                         → permanently locked
  Different Telegram account        → rejected (token_already_used)
"""
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

import psycopg2

sys.path.insert(0, '/root/TWBshop')
logger = logging.getLogger(__name__)

TOKEN_EXPIRY_HOURS = 2
QUIZ_VERSION_NAME = "Final v3"
INACTIVITY_TIMEOUT_SECONDS = 600  # 10 minutes


def _conn():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Session creation ─────────────────────────────────────────────────────────

def create_session(candidate_name: str, created_by_staff_id: int) -> tuple[str, int]:
    """
    Create a hiring_candidates row + hiring_sessions row.
    Returns (plain_token, session_id).
    The plain token is returned ONCE and must not be stored — only the hash is in DB.
    """
    import secrets as _sec
    token = _sec.token_urlsafe(18)
    token_hash = _hash(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_candidates (name, candidate_type, notes)
            VALUES (%s, 'applicant', 'Created via hire bot')
            RETURNING id
        """, (candidate_name,))
        candidate_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO hiring_sessions
                (token_hash, candidate_id, created_by_staff, expires_at, status)
            VALUES (%s, %s, %s, %s, 'pending')
            RETURNING id
        """, (token_hash, candidate_id, str(created_by_staff_id), expires_at))
        session_id = cur.fetchone()[0]

        conn.commit()
        logger.info("create_session: session=%s candidate=%s", session_id, candidate_name)
        return token, session_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ── Token verification ───────────────────────────────────────────────────────

def get_session_by_token(token: str) -> Optional[dict]:
    """Verify token and return session dict, or None if invalid/expired/used."""
    token_hash = _hash(token)
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT s.id, s.candidate_id, s.status, s.expires_at, s.resume_count,
                   s.telegram_user_id, c.name
            FROM hiring_sessions s
            JOIN hiring_candidates c ON c.id = s.candidate_id
            WHERE s.token_hash = %s
        """, (token_hash,))
        row = cur.fetchone()
        if not row:
            return None
        sid, cid, status, expires_at, resume_count, bound_uid, name = row
        return {
            "session_id": sid,
            "candidate_id": cid,
            "status": status,
            "expires_at": expires_at,
            "resume_count": resume_count,
            "bound_telegram_user_id": bound_uid,
            "candidate_name": name,
        }
    finally:
        cur.close()
        conn.close()


def get_active_session(telegram_user_id: int) -> Optional[dict]:
    """Look up the current non-completed session for a Telegram user."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT s.id, s.candidate_id, s.status, s.resume_count,
                   a.id, a.attempt_status, a.abandoned_at_question_id,
                   c.name
            FROM hiring_sessions s
            JOIN hiring_candidates c ON c.id = s.candidate_id
            LEFT JOIN hiring_quiz_attempts a ON a.session_id = s.id
            WHERE s.telegram_user_id = %s
              AND s.status NOT IN ('completed', 'cancelled', 'expired')
            ORDER BY s.created_at DESC
            LIMIT 1
        """, (telegram_user_id,))
        row = cur.fetchone()
        if not row:
            return None
        sid, cid, status, resume_count, aid, attempt_status, abandoned_qid, name = row
        return {
            "session_id": sid,
            "candidate_id": cid,
            "status": status,
            "resume_count": resume_count,
            "attempt_id": aid,
            "attempt_status": attempt_status,
            "abandoned_at_question_id": abandoned_qid,
            "candidate_name": name,
        }
    finally:
        cur.close()
        conn.close()


# ── Session open / resume ────────────────────────────────────────────────────

def open_session(session_id: int, telegram_user_id: int,
                 telegram_username: Optional[str]) -> tuple[int, bool]:
    """
    Bind session to telegram_user_id and create or resume an attempt.
    Transaction-safe: SELECT FOR UPDATE prevents double-open.
    Returns (attempt_id, is_resume).
    Raises ValueError("session_expired" | "session_completed" | "session_cancelled" |
                      "token_already_used" | "resume_needs_staff") on invalid state.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT status, expires_at, resume_count, telegram_user_id, candidate_id
            FROM hiring_sessions WHERE id = %s FOR UPDATE
        """, (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("session_not_found")
        status, expires_at, resume_count, bound_uid, candidate_id = row

        if status == "completed":
            raise ValueError("session_completed")
        if status == "cancelled":
            raise ValueError("session_cancelled")
        now = datetime.now(timezone.utc)
        if status == "expired" or (expires_at and now > expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else now > expires_at):
            cur.execute("UPDATE hiring_sessions SET status = 'expired' WHERE id = %s", (session_id,))
            conn.commit()
            raise ValueError("session_expired")
        if bound_uid and bound_uid != telegram_user_id:
            raise ValueError("token_already_used")

        cur.execute("SELECT id FROM hiring_quiz_versions WHERE version_name = %s",
                    (QUIZ_VERSION_NAME,))
        vid = cur.fetchone()[0]

        # Check for existing attempt
        cur.execute("""
            SELECT id, attempt_status, resume_count FROM hiring_quiz_attempts
            WHERE session_id = %s ORDER BY created_at DESC LIMIT 1
        """, (session_id,))
        existing = cur.fetchone()

        is_resume = False
        if existing:
            attempt_id, attempt_status, attempt_resume_count = existing
            if attempt_status == "completed":
                raise ValueError("session_completed")
            if attempt_status == "abandoned":
                if attempt_resume_count >= 1:
                    raise ValueError("resume_needs_staff")
                # First free resume allowed
                cur.execute("""
                    UPDATE hiring_quiz_attempts
                    SET attempt_status = 'resumed', resume_count = resume_count + 1,
                        abandoned_at_question_id = NULL
                    WHERE id = %s
                """, (attempt_id,))
                is_resume = True
            elif attempt_status == "reopened_by_staff":
                cur.execute("""
                    UPDATE hiring_quiz_attempts
                    SET attempt_status = 'resumed', resume_count = resume_count + 1,
                        abandoned_at_question_id = NULL
                    WHERE id = %s
                """, (attempt_id,))
                is_resume = True
            # started / in_progress / resumed → just continue
        else:
            cur.execute("""
                INSERT INTO hiring_quiz_attempts
                    (candidate_id, session_id, quiz_version_id, started_at, attempt_status, arrival_status)
                VALUES (%s, %s, %s, NOW(), 'started', 'on_time')
                RETURNING id
            """, (candidate_id, session_id, vid))
            attempt_id = cur.fetchone()[0]

        cur.execute("""
            UPDATE hiring_sessions
            SET status = 'active',
                telegram_user_id = %s,
                telegram_username = %s,
                used_at = COALESCE(used_at, NOW())
            WHERE id = %s
        """, (telegram_user_id, telegram_username, session_id))

        conn.commit()
        logger.info("open_session: session=%s attempt=%s user=%s resume=%s",
                    session_id, attempt_id, telegram_user_id, is_resume)
        return attempt_id, is_resume
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ── Answer recording ─────────────────────────────────────────────────────────

def record_answer(attempt_id: int, question_id: str, raw_answer: dict) -> None:
    """
    Insert an answer row. Checks for existing row first to avoid duplicates.
    Idempotent: if already answered, does nothing.
    Also marks attempt as in_progress on first answer.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id FROM hiring_quiz_answers
            WHERE attempt_id = %s AND question_id = %s LIMIT 1
        """, (attempt_id, question_id))
        if cur.fetchone():
            return  # Already recorded — duplicate callback, ignore

        cur.execute("""
            INSERT INTO hiring_quiz_answers (attempt_id, question_id, raw_answer, skipped)
            VALUES (%s, %s, %s, FALSE)
        """, (attempt_id, question_id, json.dumps(raw_answer)))

        cur.execute("""
            UPDATE hiring_quiz_attempts
            SET attempt_status = 'in_progress'
            WHERE id = %s AND attempt_status IN ('started', 'resumed', 'reopened_by_staff')
        """, (attempt_id,))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def upsert_partial_ranking(attempt_id: int, question_id: str, partial_order: list) -> None:
    """Update D1 ranking partial state. Uses INSERT...ON UPDATE pattern via check+upsert."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id FROM hiring_quiz_answers
            WHERE attempt_id = %s AND question_id = %s LIMIT 1
        """, (attempt_id, question_id))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE hiring_quiz_answers SET raw_answer = %s
                WHERE attempt_id = %s AND question_id = %s
            """, (json.dumps({"order": partial_order}), attempt_id, question_id))
        else:
            cur.execute("""
                INSERT INTO hiring_quiz_answers (attempt_id, question_id, raw_answer, skipped)
                VALUES (%s, %s, %s, FALSE)
            """, (attempt_id, question_id, json.dumps({"order": partial_order})))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_answered_question_ids(attempt_id: int) -> set:
    """
    Return set of fully-answered question_ids for this attempt.
    D1 is only counted as answered when order has 7 items.
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT ON (question_id) question_id, raw_answer
            FROM hiring_quiz_answers
            WHERE attempt_id = %s AND skipped = FALSE
            ORDER BY question_id, id DESC
        """, (attempt_id,))
        answered = set()
        for qid, raw in cur.fetchall():
            if raw is None:
                continue
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                parsed = {}
            if qid == "D1":
                if isinstance(parsed.get("order"), list) and len(parsed["order"]) == 7:
                    answered.add(qid)
            else:
                answered.add(qid)
        return answered
    finally:
        cur.close()
        conn.close()


def get_d1_partial_order(attempt_id: int) -> list:
    """Return current partial D1 ranking (may be [] or 1-6 items)."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT raw_answer FROM hiring_quiz_answers
            WHERE attempt_id = %s AND question_id = 'D1' LIMIT 1
        """, (attempt_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return []
        try:
            parsed = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            return parsed.get("order", [])
        except Exception:
            return []
    finally:
        cur.close()
        conn.close()


# ── Session state transitions ────────────────────────────────────────────────

def mark_abandoned(attempt_id: int, session_id: int, question_id: str) -> None:
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_quiz_attempts
            SET attempt_status = 'abandoned', abandoned_at_question_id = %s
            WHERE id = %s AND attempt_status NOT IN ('completed', 'cancelled')
        """, (question_id, attempt_id))
        cur.execute("""
            UPDATE hiring_sessions SET abandoned_at = NOW(), abandoned_at_question_id = %s
            WHERE id = %s
        """, (question_id, session_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def reopen_by_staff(attempt_id: int, staff_name: str) -> None:
    """Allow one more resume after a second abandon."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_quiz_attempts
            SET attempt_status = 'reopened_by_staff'
            WHERE id = %s AND attempt_status = 'abandoned'
        """, (attempt_id,))
        cur.execute("""
            UPDATE hiring_sessions SET reopened_by = %s
            WHERE id = (SELECT session_id FROM hiring_quiz_attempts WHERE id = %s)
        """, (staff_name, attempt_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def complete_session(session_id: int, attempt_id: int) -> None:
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_quiz_attempts SET attempt_status = 'completed', completed_at = NOW()
            WHERE id = %s
        """, (attempt_id,))
        cur.execute("""
            UPDATE hiring_sessions SET status = 'completed', completed_at = NOW()
            WHERE id = %s
        """, (session_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ── Follow-up answer storage ─────────────────────────────────────────────────

def store_followup_answer(attempt_id: int, callback_key: str, answer_text: str) -> None:
    """Store a follow-up answer in score_summary.followup_answers JSONB."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_quiz_attempts
            SET score_summary = jsonb_set(
                jsonb_set(
                    COALESCE(score_summary, '{}'::jsonb),
                    '{followup_answers}',
                    COALESCE(score_summary->'followup_answers', '{}'::jsonb)
                ),
                ARRAY['followup_answers', %s],
                %s::jsonb
            )
            WHERE id = %s
        """, (callback_key, json.dumps(answer_text), attempt_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
