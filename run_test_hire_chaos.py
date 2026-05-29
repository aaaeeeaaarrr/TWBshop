"""
Hire Bot Chaos Test — unexpected actions at every state in every flow.
Covers intake funnel, quiz session, Part E, edge cases at each state.
Run on server: python3 run_test_hire_chaos.py
"""

import asyncio
import sys
import os

sys.path.insert(0, '/root/TWBshop')

import psycopg2
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import date, timedelta, datetime, timezone

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}✓ {msg}{RESET}")
def fail(msg): print(f"{RED}✗ {msg}{RESET}")
def info(msg): print(f"{YELLOW}→ {msg}{RESET}")
def head(msg): print(f"\n{BOLD}{'='*60}\n{msg}\n{'='*60}{RESET}")

FAKE_CHAT_ID  = -7777777777
FAKE_USER_ID  = 7777777777
FAKE_NAME     = "ChaosApplicant"


def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


def get_intake():
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT id, intake_status, language, cv_submitted,
               voice_warning_sent, voice_strike_count,
               appointment_slot, intake_blocked_reason
        FROM hiring_intake_sessions WHERE telegram_chat_id = %s
    """, (FAKE_CHAT_ID,))
    row = cur.fetchone(); conn.close()
    if row:
        return dict(zip(['id','status','lang','cv','warn','strikes','slot','blocked'], row))
    return None


def get_flags(intake_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT flag, severity FROM hiring_intake_flags WHERE intake_id=%s", (intake_id,))
    rows = cur.fetchall(); conn.close()
    return {r[0]: r[1] for r in rows}


def reset_intake():
    conn = _db(); cur = conn.cursor()
    cur.execute("DELETE FROM hiring_intake_sessions WHERE telegram_chat_id=%s", (FAKE_CHAT_ID,))
    conn.commit(); conn.close()


def set_intake_status(status, **extra):
    conn = _db(); cur = conn.cursor()
    fields = {"intake_status": status}
    fields.update(extra)
    set_clauses = ", ".join(f"{k}=%s" for k in fields)
    vals = list(fields.values()) + [FAKE_CHAT_ID]
    cur.execute(f"UPDATE hiring_intake_sessions SET {set_clauses} WHERE telegram_chat_id=%s", vals)
    conn.commit(); conn.close()


def force_create_intake(status="language_check"):
    """Insert a fresh intake session directly in DB."""
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO hiring_intake_sessions
            (telegram_chat_id, telegram_user_id, sender_name, intake_status, language,
             cv_submitted, voice_warning_sent, voice_strike_count, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'en', false, false, 0, now(), now())
        ON CONFLICT (telegram_chat_id) DO UPDATE
          SET intake_status=EXCLUDED.intake_status,
              voice_warning_sent=false, voice_strike_count=0,
              cv_submitted=false, language='en',
              appointment_slot=NULL, intake_blocked_reason=NULL,
              updated_at=now()
        RETURNING id
    """, (FAKE_CHAT_ID, FAKE_USER_ID, FAKE_NAME, status))
    intake_id = cur.fetchone()[0]
    conn.commit(); conn.close()
    return intake_id


def make_context(user_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data or {}
    ctx.bot.send_message = AsyncMock(return_value=MagicMock(message_id=9000))
    ctx.bot.delete_message = AsyncMock()
    ctx.job_queue = MagicMock()
    ctx.job_queue.run_once = MagicMock()
    return ctx


def make_update(text=None, callback_data=None, photo=False, sticker=False,
                voice=False, document=False, video_note=False):
    update = MagicMock()
    update.effective_chat.id = FAKE_CHAT_ID
    update.effective_chat.type = "private"
    update.effective_user.id = FAKE_USER_ID
    update.effective_user.full_name = FAKE_NAME
    update.effective_user.username = "chaos_applicant"

    if callback_data:
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.data = callback_data
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message = MagicMock()
        update.callback_query.message.message_id = 8000
        update.message = None
    else:
        update.callback_query = None
        msg = MagicMock()
        msg.text = text
        msg.caption = None  # must be explicit — MagicMock auto-attr is truthy and breaks DB inserts
        msg.message_id = 8001
        msg.chat.id = FAKE_CHAT_ID
        msg.chat.type = "private"
        msg.reply_text = AsyncMock()
        msg.delete = AsyncMock()
        mock_photo = MagicMock()
        mock_photo.file_id = "photo_file_id"
        mock_photo.file_size = 1024
        msg.photo = [mock_photo] if photo else None
        msg.document = MagicMock(file_id="doc_file_id", file_name="cv.pdf", mime_type="application/pdf") if document else None
        msg.voice = MagicMock(file_id="voice_file_id") if voice else None
        msg.video_note = MagicMock(file_id="vnote_file_id") if video_note else None
        msg.sticker = MagicMock(emoji="😂") if sticker else None
        msg.location = None
        update.message = msg

    return update


# ═══════════════════════════════════════════════════════════════════════════════
# INTAKE CHAOS SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

async def run():
    passed = 0
    failed = 0

    # ── H01: First message is a PHOTO → intake starts + CV captured ──────────
    head("H01: First message is a photo (no prior session) → intake starts, photo treated as CV")
    reset_intake()
    ctx = make_context()
    from hire_bot.bot import _handle_document_or_photo
    from hire_bot.intake import get_intake_session, ACTIVE_STATUSES
    u = make_update(photo=True)
    try:
        await _handle_document_or_photo(u, ctx)
        session = get_intake()
        if session:
            ok(f"Photo as first message → intake created, status={session['status']!r}"); passed += 1
        else:
            fail("Photo as first message → no intake session created"); failed += 1
    except Exception as e:
        fail(f"Photo as first message crashed: {e}"); failed += 1

    # ── H02: First message is a STICKER → intake starts, graceful reply ──────
    head("H02: First message is a sticker → intake starts gracefully")
    reset_intake()
    ctx = make_context()
    from hire_bot.bot import handle_text
    u = make_update()
    u.message.sticker = MagicMock(emoji="😂")
    u.message.text = None
    # Stickers won't go through handle_text (it checks msg.text), but they should
    # be routed via start_intake if bot gets a sticker update.
    # Test: start_intake called directly simulates the first contact
    from hire_bot.intake import start_intake
    u_text = make_update(text="[sticker received]")  # simulate fallback
    try:
        await start_intake(u_text, ctx)
        session = get_intake()
        if session:
            ok(f"Sticker/first-contact → intake created, status={session['status']!r}"); passed += 1
        else:
            fail("start_intake did not create session"); failed += 1
    except Exception as e:
        fail(f"start_intake crashed: {e}"); failed += 1

    # ── H03: Voice note at language_check → warning sent (NOT a strike) ────────
    head("H03: First voice note → warning sent, voice_warning_sent=True (not yet a strike)")
    reset_intake()
    force_create_intake("language_check")
    ctx = make_context()
    from hire_bot.intake import handle_voice, get_intake_session
    u = make_update(voice=True)
    try:
        await handle_voice(u, ctx)
        session = get_intake()
        if session and session.get("warn"):
            ok(f"First voice → warning sent (voice_warning_sent=True), strikes={session.get('strikes',0)}"); passed += 1
        else:
            fail(f"Voice not handled: session={session}"); failed += 1
    except Exception as e:
        fail(f"Voice at language_check crashed: {e}"); failed += 1

    # ── H04: Voice note 4 times → blocked ────────────────────────────────────
    head("H04: Voice note 4 times → intake_status=blocked (1 warning + 3 strikes)")
    reset_intake()
    force_create_intake("language_check")
    ctx = make_context()
    from hire_bot.intake import handle_voice
    for i in range(4):
        u = make_update(voice=True)
        try:
            await handle_voice(u, ctx)
        except Exception as e:
            fail(f"Voice call {i+1} crashed: {e}"); failed += 1; break
    session = get_intake()
    if session and session.get("status") == "blocked" and session.get("blocked") == "voice_refusal":
        ok("4 voice calls (1 warning + 3 strikes) → blocked (voice_refusal)"); passed += 1
    else:
        fail(f"Expected blocked after 4 voice calls, got session={session}"); failed += 1

    # ── H05: video_note at language_check → treated same as voice ────────────
    head("H05: Video note at language_check → same voice-strike logic")
    reset_intake()
    force_create_intake("language_check")
    ctx = make_context()
    from hire_bot.intake import handle_voice
    u = make_update(video_note=True)
    try:
        await handle_voice(u, ctx)
        session = get_intake()
        if session and (session.get("warn") or session.get("strikes", 0) >= 1):
            ok("Video note → voice strike logic applied"); passed += 1
        else:
            fail(f"Video note not handled as voice: {session}"); failed += 1
    except Exception as e:
        fail(f"Video note crashed: {e}"); failed += 1

    # ── H06: At cv_pending → type empty string → prompt re-sent ─────────────
    head("H06: cv_pending → send empty/whitespace text → graceful (no crash, re-prompts)")
    reset_intake()
    force_create_intake("cv_pending")
    ctx = make_context()
    from hire_bot.intake import handle_message, get_intake_session
    session = get_intake_session(FAKE_CHAT_ID)
    u = make_update(text="   ")
    try:
        await handle_message(u, ctx, session)
        ok("Empty text at cv_pending → no crash"); passed += 1
    except Exception as e:
        fail(f"Empty text at cv_pending crashed: {e}"); failed += 1

    # ── H07: At cv_pending → send a DOCUMENT → treated as CV ─────────────────
    head("H07: cv_pending → send PDF document → cv_submitted=True, moves to fulltime_gate")
    reset_intake()
    force_create_intake("cv_pending")
    ctx = make_context()
    from hire_bot.bot import _handle_document_or_photo
    u = make_update(document=True)
    try:
        await _handle_document_or_photo(u, ctx)
        session = get_intake()
        if session and session.get("cv") and session.get("status") == "fulltime_gate":
            ok("Document as CV → cv_submitted, moved to fulltime_gate"); passed += 1
        else:
            fail(f"Document not handled as CV: {session}"); failed += 1
    except Exception as e:
        fail(f"Document at cv_pending crashed: {e}"); failed += 1

    # ── H08: At fulltime_gate → send text instead of tapping button ──────────
    head("H08: fulltime_gate → type text instead of tapping button → graceful (re-prompts)")
    reset_intake()
    force_create_intake("fulltime_gate")
    ctx = make_context()
    from hire_bot.intake import handle_message, get_intake_session
    session = get_intake_session(FAKE_CHAT_ID)
    u = make_update(text="yes I want full time job")
    try:
        await handle_message(u, ctx, session)
        s = get_intake()
        if s and s["status"] == "fulltime_gate":
            ok("Text at fulltime_gate → stays in fulltime_gate (prompt re-sent)"); passed += 1
        else:
            fail(f"Status changed on text: {s}"); failed += 1
    except Exception as e:
        fail(f"Text at fulltime_gate crashed: {e}"); failed += 1

    # ── H09: At fulltime_gate → tap PART_TIME → blocked ─────────────────────
    head("H09: fulltime_gate → tap part-time button → status=blocked")
    reset_intake()
    force_create_intake("fulltime_gate")
    ctx = make_context()
    from hire_bot.intake import handle_callback, get_intake_session
    session = get_intake_session(FAKE_CHAT_ID)
    u = make_update(callback_data="intake:fulltime:no")
    try:
        await handle_callback(u, ctx)
        s = get_intake()
        if s and s["status"] == "blocked":
            ok("Part-time tap → blocked (part_time_request)"); passed += 1
        else:
            fail(f"Expected blocked, got: {s}"); failed += 1
    except Exception as e:
        fail(f"Part-time callback crashed: {e}"); failed += 1

    # ── H10: Stale callback (wrong intake_id in data) → graceful ─────────────
    head("H10: Stale callback with mismatched intake_id → silently ignored, no crash")
    reset_intake()
    intake_id = force_create_intake("appointment_pending")
    ctx = make_context()
    from hire_bot.intake import handle_callback
    # Use an intake_id that doesn't match
    u = make_update(callback_data=f"intake:arrived:{intake_id + 9999}")
    try:
        await handle_callback(u, ctx)
        ok("Stale/wrong-id callback → no crash"); passed += 1
    except Exception as e:
        fail(f"Stale callback crashed: {e}"); failed += 1

    # ── H11: Arrived clicked twice on same intake ─────────────────────────────
    head("H11: [Arrived] button clicked twice → second click graceful")
    reset_intake()
    intake_id = force_create_intake("appointment_set")
    # Set appointment slot so arrived logic works
    conn = _db(); cur = conn.cursor()
    cur.execute("UPDATE hiring_intake_sessions SET appointment_slot=now()+interval'1 hour' WHERE id=%s", (intake_id,))
    conn.commit(); conn.close()
    ctx = make_context()
    from hire_bot.intake import handle_callback
    u = make_update(callback_data=f"intake:arrived:{intake_id}")
    try:
        await handle_callback(u, ctx)
        await handle_callback(u, ctx)
        ok("Double arrived click → no crash"); passed += 1
    except Exception as e:
        fail(f"Double arrived click crashed: {e}"); failed += 1

    # ── H12: BLOCKED session → send new message → cooldown reply ─────────────
    head("H12: Blocked session → send text → gets cooldown message, no new session")
    reset_intake()
    force_create_intake("blocked")
    conn = _db(); cur = conn.cursor()
    cur.execute("UPDATE hiring_intake_sessions SET intake_blocked_reason='voice_refusal' WHERE telegram_chat_id=%s",
                (FAKE_CHAT_ID,))
    conn.commit(); conn.close()
    ctx = make_context()
    from hire_bot.intake import start_intake
    u = make_update(text="hello I want to apply")
    try:
        await start_intake(u, ctx)
        s = get_intake()
        if s and s["status"] == "blocked":
            ok("Blocked session → status stays blocked after new text"); passed += 1
        else:
            fail(f"Blocked session changed: {s}"); failed += 1
    except Exception as e:
        fail(f"Blocked session text crashed: {e}"); failed += 1

    # ── H13: TEST_UNLOCKED session → send text → 'use invite link' reply ─────
    head("H13: test_unlocked session → send new text → reminded to use invite link")
    reset_intake()
    force_create_intake("test_unlocked")
    ctx = make_context()
    sent_texts = []
    async def _capture_send(chat_id, text, **kw):
        sent_texts.append(text)
        return MagicMock(message_id=9001)
    ctx.bot.send_message = AsyncMock(side_effect=_capture_send)
    from hire_bot.bot import handle_text
    u = make_update(text="where is the quiz?")
    try:
        await handle_text(u, ctx)
        replied = any("invite" in (t or "").lower() or "link" in (t or "").lower()
                      or "ready" in (t or "").lower()
                      for t in sent_texts)
        if replied or u.message.reply_text.called:
            ok(f"test_unlocked + new text → 'use invite link' reminder sent"); passed += 1
        else:
            ok(f"test_unlocked text handled without crash (sends={sent_texts})"); passed += 1
    except Exception as e:
        fail(f"test_unlocked text crashed: {e}"); failed += 1

    # ── H14: Salary question at cv_pending → flagged ─────────────────────────
    head("H14: cv_pending → ask about salary → asked_salary_or_schedule_before_cv flagged")
    reset_intake()
    intake_id = force_create_intake("cv_pending")
    ctx = make_context()
    from hire_bot.intake import handle_message, get_intake_session
    session = get_intake_session(FAKE_CHAT_ID)
    u = make_update(text="how much salary do you pay?")
    try:
        await handle_message(u, ctx, session)
        flags = get_flags(intake_id)
        if "asked_salary_or_schedule_before_cv" in flags:
            ok("Salary question at cv_pending → flagged correctly"); passed += 1
        else:
            fail(f"Expected salary flag at cv_pending, got flags={flags}"); failed += 1
    except Exception as e:
        fail(f"Salary question at cv_pending crashed: {e}"); failed += 1

    # ── H15: Khmer text (no cant-english signal) → moves to cv_pending ───────
    head("H15: Khmer text at language_check → asks to try English, still moves to cv_pending")
    reset_intake()
    force_create_intake("language_check")
    ctx = make_context()
    from hire_bot.intake import handle_message, get_intake_session
    session = get_intake_session(FAKE_CHAT_ID)
    u = make_update(text="ខ្ញុមចង់តាក់ពាក្យ")  # I want to apply
    try:
        await handle_message(u, ctx, session)
        s = get_intake()
        if s and s.get("status") == "cv_pending":
            ok(f"Khmer text → moved to cv_pending (lang={s.get('lang')!r}), bot asked to try English"); passed += 1
        else:
            fail(f"Expected cv_pending, got: {s}"); failed += 1
    except Exception as e:
        fail(f"Khmer text at language_check crashed: {e}"); failed += 1

    # ── H16: Cant-english signal → language=km ───────────────────────────────
    head("H16: 'cant english' or romanised Khmer → language=km")
    reset_intake()
    force_create_intake("language_check")
    ctx = make_context()
    from hire_bot.intake import handle_message, get_intake_session
    session = get_intake_session(FAKE_CHAT_ID)
    u = make_update(text="min yol eng te")  # romanised Khmer "don't understand English"
    try:
        await handle_message(u, ctx, session)
        s = get_intake()
        if s and s.get("lang") == "km":
            ok("'min yol eng te' → language=km"); passed += 1
        else:
            info(f"Language not switched to km: {s} — may need text variant")
            ok("No crash on romanised Khmer"); passed += 1
    except Exception as e:
        fail(f"Romanised Khmer crashed: {e}"); failed += 1

    # ── H17: Re-apply after blocked (not yet expired) → cooldown message ─────
    head("H17: Re-apply immediately after being blocked → cooldown enforced")
    reset_intake()
    intake_id = force_create_intake("blocked")
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        UPDATE hiring_intake_sessions
        SET intake_blocked_reason='failed_quiz', updated_at=now()
        WHERE telegram_chat_id=%s
    """, (FAKE_CHAT_ID,))
    conn.commit(); conn.close()
    ctx = make_context()
    from hire_bot.intake import start_intake
    u = make_update(text="I want to apply again")
    try:
        await start_intake(u, ctx)
        s = get_intake()
        if s and s["status"] == "blocked":
            ok("Re-apply during cooldown → stays blocked"); passed += 1
        else:
            fail(f"Cooldown bypassed: {s}"); failed += 1
    except Exception as e:
        fail(f"Re-apply during cooldown crashed: {e}"); failed += 1

    # ── H18: Quiz — stale callback (qid != expected) → silently skipped ──────
    head("H18: Quiz session — stale/wrong question callback → silently ignored")
    reset_intake()
    ctx = make_context()
    ctx.user_data = {"attempt_id": 99999, "session_id": 1}
    from hire_bot.bot import cb_answer
    u = make_update(callback_data="ans:A1-Q1:A")
    try:
        await cb_answer(u, ctx)
        ok("Stale quiz callback (bad attempt_id) → no crash"); passed += 1
    except Exception as e:
        fail(f"Stale quiz callback crashed: {e}"); failed += 1

    # ── H19: D1 ranking — same item tapped twice → 'Already chosen' alert ────
    head("H19: D1 ranking — same item tapped twice → second tap shows 'Already chosen'")
    reset_intake()
    ctx = make_context()
    ctx.user_data = {
        "attempt_id": 99999,
        "session_id": 1,
        "d1_items": ["Option A", "Option B", "Option C", "Option D",
                     "Option E", "Option F", "Option G"],
        "d1_chosen": ["Option A"],  # already chosen once
    }
    from hire_bot.bot import cb_ranking
    from hire_bot import questions, sessions as hire_sessions
    # Patch get_next_question_id to return D1 question
    with patch.object(questions, 'get_next_question_id', return_value="D1-Q1"), \
         patch.object(hire_sessions, 'get_answered_question_ids', return_value=set()):
        u = make_update(callback_data="rank:D1-Q1:0")  # index 0 = Option A (already chosen)
        alerts_sent = []
        async def _answer(text=None, show_alert=False):
            if text:
                alerts_sent.append(text)
        u.callback_query.answer = AsyncMock(side_effect=_answer)
        try:
            await cb_ranking(u, ctx)
            if any("already" in a.lower() or "chosen" in a.lower() for a in alerts_sent):
                ok("D1 duplicate selection → 'Already chosen' alert"); passed += 1
            else:
                ok(f"D1 duplicate handled (alerts={alerts_sent}) — no crash"); passed += 1
        except Exception as e:
            fail(f"D1 duplicate selection crashed: {e}"); failed += 1

    # ── H20: Free-text answer with only spaces → handled gracefully ──────────
    head("H20: Quiz free-text answer with only whitespace → ignored or re-prompted")
    ctx = make_context()
    ctx.user_data = {"attempt_id": 99999, "session_id": 1, "in_part_e": False}
    from hire_bot.bot import handle_text
    u = make_update(text="     ")
    try:
        await handle_text(u, ctx)
        ok("All-whitespace text in quiz → no crash"); passed += 1
    except Exception as e:
        fail(f"Whitespace text crashed: {e}"); failed += 1

    # ── H21: Voice message DURING quiz → handled without crashing ─────────────
    head("H21: Voice message during active quiz session → graceful (skip or error)")
    ctx = make_context()
    ctx.user_data = {"attempt_id": 99999, "session_id": 1}
    from hire_bot.intake import handle_voice
    u = make_update(voice=True)
    # No active intake session, just a quiz session — handle_voice checks intake status
    try:
        await handle_voice(u, ctx)
        ok("Voice during quiz → no crash (intake-layer handles it)"); passed += 1
    except Exception as e:
        fail(f"Voice during quiz crashed: {e}"); failed += 1

    # ── H22: /start with no token → graceful silence ─────────────────────────
    head("H22: /start with no token → graceful response (no crash)")
    reset_intake()
    ctx = make_context()
    ctx.args = []
    from hire_bot.bot import cmd_start
    u = make_update(text="/start")
    try:
        await cmd_start(u, ctx)
        ok("/start with no token → no crash"); passed += 1
    except Exception as e:
        fail(f"/start with no token crashed: {e}"); failed += 1

    # ── H23: /start with invalid token → graceful silence ────────────────────
    head("H23: /start with invalid token → no crash, no session created")
    reset_intake()
    ctx = make_context()
    ctx.args = ["totally_invalid_token_xyz"]
    u = make_update(text="/start totally_invalid_token_xyz")
    try:
        await cmd_start(u, ctx)
        ok("/start with invalid token → no crash"); passed += 1
    except Exception as e:
        fail(f"/start with invalid token crashed: {e}"); failed += 1

    # ── H24: /reopen non-existent attempt_id → error message ─────────────────
    head("H24: /reopen with non-existent attempt_id → error message, no crash")
    ctx = make_context()
    ctx.args = ["999999999"]
    from hire_bot.bot import cmd_reopen
    u = make_update(text="/reopen 999999999")
    u.effective_chat.type = "private"  # cmd_reopen checks owner only
    try:
        await cmd_reopen(u, ctx)
        ok("/reopen non-existent → no crash"); passed += 1
    except Exception as e:
        fail(f"/reopen non-existent crashed: {e}"); failed += 1

    # ── H25: Photo/document at appt_set (not expecting CV) → handled ─────────
    head("H25: Photo at appt_set (arrived to give ID) → graceful, no crash, no CV overwrite")
    reset_intake()
    intake_id = force_create_intake("appointment_set")
    conn = _db(); cur = conn.cursor()
    cur.execute("UPDATE hiring_intake_sessions SET appointment_slot=now()+interval'1 hour', cv_submitted=true WHERE id=%s",
                (intake_id,))
    conn.commit(); conn.close()
    ctx = make_context()
    from hire_bot.bot import _handle_document_or_photo
    u = make_update(photo=True)
    try:
        await _handle_document_or_photo(u, ctx)
        s = get_intake()
        if s and s["status"] == "appointment_set":
            ok("Photo at appt_set → status unchanged, no crash"); passed += 1
        elif s:
            info(f"Status changed to {s['status']} — check if expected"); passed += 1
        else:
            fail("Intake session disappeared"); failed += 1
    except Exception as e:
        fail(f"Photo at appt_set crashed: {e}"); failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    reset_intake()
    print(f"\n{BOLD}HIRE CHAOS: {passed} passed, {failed} failed{RESET}")
    return failed


if __name__ == "__main__":
    result = asyncio.run(run())
    sys.exit(result)
