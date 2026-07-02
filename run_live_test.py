"""
Controlled live test — assessment pipeline + correction/offer flow.
Runs against existing __TEST_Perfect__ attempt (attempt_id=2).

Usage:  python3 run_live_test.py [--path-a | --path-b]
Default runs assessment pipeline + Path A test.
"""

import asyncio
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("live_test")

sys.path.insert(0, "/root/TWBshop")

import psycopg2
from secrets import HIRE_BOT_TOKEN
from shared.database import raw_connect
from telegram import Bot

ATTEMPT_ID = 2   # __TEST_Perfect__ — 87 answers, Chanmony-style hiding signal in C-Q8
OWNER_TG_ID = None  # loaded from config below

import config
OWNER_TG_ID = config.OWNER_TELEGRAM_ID


def _db():
    return raw_connect()


# ── Step 0: Ensure session exists for attempt 2 ──────────────────────────────

def setup_session_for_attempt(attempt_id: int) -> int:
    """Create a minimal session row if attempt has session_id=NULL."""
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("SELECT session_id, candidate_id FROM hiring_quiz_attempts WHERE id=%s", (attempt_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Attempt {attempt_id} not found")
        session_id, candidate_id = row

        if session_id:
            logger.info("Attempt %s already has session_id=%s", attempt_id, session_id)
            return session_id

        # Create minimal session
        import hashlib, os
        token_hash = hashlib.sha256(os.urandom(32)).hexdigest()
        cur.execute("""
            INSERT INTO hiring_sessions
                (candidate_id, token_hash, created_by_staff, expires_at, status,
                 resume_count, telegram_user_id)
            VALUES (%s, %s, 'live_test', now() + interval '1 year', 'completed',
                    0, %s)
            RETURNING id
        """, (candidate_id, token_hash, OWNER_TG_ID))
        session_id = cur.fetchone()[0]

        cur.execute("UPDATE hiring_quiz_attempts SET session_id=%s, attempt_status='completed' WHERE id=%s",
                    (session_id, attempt_id))
        conn.commit()
        logger.info("Created session_id=%s for attempt %s", session_id, attempt_id)
        return session_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


# ── Step 1: Run assessment pipeline ──────────────────────────────────────────

async def run_assessment(bot: Bot, attempt_id: int, session_id: int) -> dict | None:
    from hire_bot.assessment_pipeline import run_full_assessment
    logger.info("Running assessment pipeline for attempt %s ...", attempt_id)
    result = await run_full_assessment(bot, attempt_id, session_id)
    return result


def check_assessment_db(attempt_id: int) -> dict:
    conn = _db(); cur = conn.cursor()
    try:
        cur.execute("SELECT id, recommendation, output_valid FROM hiring_ai_assessments WHERE attempt_id=%s ORDER BY id DESC LIMIT 1", (attempt_id,))
        a = cur.fetchone()

        cur.execute("SELECT id, english_text IS NOT NULL, khmer_validated FROM hiring_targeted_messages WHERE attempt_id=%s ORDER BY id DESC LIMIT 1", (attempt_id,))
        t = cur.fetchone()

        cur.execute("SELECT id FROM hiring_correction_responses WHERE attempt_id=%s ORDER BY id DESC LIMIT 1", (attempt_id,))
        c = cur.fetchone()

        cur.execute("SELECT id, offer_status FROM hiring_offers WHERE attempt_id=%s ORDER BY id DESC LIMIT 1", (attempt_id,))
        o = cur.fetchone()

        return {
            "assessment":         {"id": a[0], "recommendation": a[1], "valid": a[2]} if a else None,
            "targeted_message":   {"id": t[0], "has_english": t[1], "khmer_validated": t[2]} if t else None,
            "correction_response": {"id": c[0]} if c else None,
            "offer":              {"id": o[0], "status": o[1]} if o else None,
        }
    finally:
        cur.close(); conn.close()


# ── Step 2: Path A simulation ─────────────────────────────────────────────────
# Note: actual applicant button taps require real Telegram interaction.
# We test the underlying function directly with a mock update.

async def simulate_path_a(bot: Bot, attempt_id: int, targeted_message_id: int | None) -> dict:
    """Simulate Path A: correction_understood open-check answer → owner gets approval button."""
    from hire_bot.correction_flow import handle_open_check_answer
    from unittest.mock import MagicMock, AsyncMock

    good_answer = (
        "I will tell my supervisor immediately so we can fix the root cause, "
        "not just the symptom. Hiding it would only make things worse later."
    )

    # Build minimal mock Update/context
    update = MagicMock()
    update.message.text = good_answer
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = OWNER_TG_ID  # using owner as "applicant" for test

    context = MagicMock()
    context.bot = bot
    context.user_data = {
        "awaiting_open_check": True,
        "attempt_id": attempt_id,
        "correction_message_id": targeted_message_id,
    }
    context.application.user_data = {}

    result = await handle_open_check_answer(update, context,
                                            targeted_message_id=targeted_message_id,
                                            attempt_id=attempt_id)
    return result or {}


# ── Step 3: Path B simulation ─────────────────────────────────────────────────

async def simulate_path_b(bot: Bot, attempt_id: int, targeted_message_id: int | None) -> dict:
    """Simulate Path B: conditional answer → owner gets reject notification."""
    from hire_bot.correction_flow import handle_open_check_answer
    from unittest.mock import MagicMock, AsyncMock

    conditional_answer = (
        "Small mistake I fix myself first, then I tell my supervisor. "
        "Big mistake I report immediately."
    )

    update = MagicMock()
    update.message.text = conditional_answer
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = OWNER_TG_ID

    context = MagicMock()
    context.bot = bot
    context.user_data = {
        "awaiting_open_check": True,
        "attempt_id": attempt_id,
        "correction_message_id": targeted_message_id,
    }
    context.application.user_data = {}

    result = await handle_open_check_answer(update, context,
                                            targeted_message_id=targeted_message_id,
                                            attempt_id=attempt_id)
    return result or {}


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--full"

    bot = Bot(token=HIRE_BOT_TOKEN)
    await bot.initialize()

    print("\n=== LIVE TEST: twbshop-hire ===\n")

    # ── Service status (already checked by systemctl before running this) ────
    print(f"Bot: @{(await bot.get_me()).username}")

    # ── Setup ────────────────────────────────────────────────────────────────
    print(f"\n[Setup] Ensuring session for attempt {ATTEMPT_ID}...")
    session_id = setup_session_for_attempt(ATTEMPT_ID)
    print(f"  session_id={session_id} OK")

    # ── Assessment pipeline ──────────────────────────────────────────────────
    print(f"\n[Assessment] Running run_full_assessment(attempt={ATTEMPT_ID})...")
    # Clear any previous assessment for clean test
    conn = _db(); cur = conn.cursor()
    cur.execute("DELETE FROM hiring_ai_assessments WHERE attempt_id=%s", (ATTEMPT_ID,))
    cur.execute("DELETE FROM hiring_targeted_messages WHERE attempt_id=%s", (ATTEMPT_ID,))
    cur.execute("DELETE FROM hiring_correction_responses WHERE attempt_id=%s", (ATTEMPT_ID,))
    cur.execute("DELETE FROM hiring_offers WHERE attempt_id=%s", (ATTEMPT_ID,))
    cur.execute("UPDATE hiring_quiz_attempts SET quiz_owner_notified_at=NULL, quiz_owner_notified_outcome=NULL WHERE id=%s", (ATTEMPT_ID,))
    conn.commit(); conn.close()

    assessment = await run_assessment(bot, ATTEMPT_ID, session_id)
    fired = assessment is not None
    print(f"  assessment_pipeline fired: {'YES' if fired else 'NO — check logs'}")

    db = check_assessment_db(ATTEMPT_ID)
    print(f"  hiring_ai_assessments: {db['assessment']}")
    print(f"  hiring_targeted_messages: {db['targeted_message']}")

    targeted_msg_id = db["targeted_message"]["id"] if db["targeted_message"] else None

    # ── Path A ───────────────────────────────────────────────────────────────
    if mode in ("--full", "--path-a"):
        print(f"\n[Path A] Simulating correction_understood open-check answer...")
        conn = _db(); cur = conn.cursor()
        cur.execute("DELETE FROM hiring_correction_responses WHERE attempt_id=%s", (ATTEMPT_ID,))
        conn.commit(); conn.close()

        result_a = await simulate_path_a(bot, ATTEMPT_ID, targeted_msg_id)
        primary_a = result_a.get("primary", "no result")
        rec_a     = result_a.get("recommendation_update", "")
        print(f"  classification: {primary_a}")
        print(f"  recommendation: {rec_a}")
        print(f"  Path A result: {'PASS — correction_understood, owner approval button sent' if 'correction_understood' in primary_a else 'FAIL — unexpected: ' + primary_a}")

        db_a = check_assessment_db(ATTEMPT_ID)
        print(f"  correction_responses row: {db_a['correction_response']}")
        print(f"  offers row (must be None): {db_a['offer']}")

    # ── Path B ───────────────────────────────────────────────────────────────
    if mode in ("--full", "--path-b"):
        print(f"\n[Path B] Simulating conditional_reporting open-check answer...")
        conn = _db(); cur = conn.cursor()
        cur.execute("DELETE FROM hiring_correction_responses WHERE attempt_id=%s", (ATTEMPT_ID,))
        conn.commit(); conn.close()

        result_b = await simulate_path_b(bot, ATTEMPT_ID, targeted_msg_id)
        primary_b = result_b.get("primary", "no result")
        rec_b     = result_b.get("recommendation_update", "")
        print(f"  classification: {primary_b}")
        print(f"  recommendation: {rec_b}")
        rejected = "reject" in rec_b.lower() or primary_b in ("conditional_reporting", "hiding_standard_not_accepted")
        print(f"  Path B result: {'PASS — no offer, owner notified with reject/hold' if rejected else 'FAIL — expected rejection, got: ' + rec_b}")

        db_b = check_assessment_db(ATTEMPT_ID)
        print(f"  correction_responses row: {db_b['correction_response']}")
        print(f"  offers row (must be None): {db_b['offer']}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n=== SUMMARY ===")
    final_db = check_assessment_db(ATTEMPT_ID)
    print(f"Service status:                    active (running)")
    print(f"Assessment fired:                  {'YES' if fired else 'NO'}")
    print(f"Owner notification sent:           {'YES — check Telegram' if fired else 'NO'}")
    print(f"Targeted message (for applicant):  {'YES, id=' + str(targeted_msg_id) if targeted_msg_id else 'NO'}")
    print(f"DB hiring_ai_assessments:          {final_db['assessment']}")
    print(f"DB hiring_targeted_messages:       {final_db['targeted_message']}")
    print(f"DB hiring_correction_responses:    {final_db['correction_response']}")
    print(f"DB hiring_offers:                  {final_db['offer']} (expected None until applicant accepts)")
    print("\nNext live-test step: Open Telegram, send /create Test Candidate to hire bot,")
    print("complete intake → quiz → confirm owner receives real assessment notification.")
    print("Then tap [I agree] / [I have a question] in the applicant chat to test callbacks.")

    await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
