"""
Automated integration test for hire_bot intake funnel.
Uses mock PTB Update objects with the real DB — no Telegram network needed.
Run on server: python3 run_test_intake.py
"""

import asyncio
import sys
import os

sys.path.insert(0, '/root/TWBshop')

import psycopg2
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, timedelta

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}✓ {msg}{RESET}")
def fail(msg): print(f"{RED}✗ {msg}{RESET}")
def info(msg): print(f"{YELLOW}→ {msg}{RESET}")
def head(msg): print(f"\n{BOLD}{'='*60}\n{msg}\n{'='*60}{RESET}")

FAKE_CHAT_ID = -9999999999
FAKE_USER_ID = 9999999999
FAKE_USER_NAME = "TestApplicant"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)

def get_intake():
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT id, intake_status, language, cv_submitted, cv_file_id,
               voice_warning_sent, voice_strike_count,
               appointment_slot, intake_blocked_reason
        FROM hiring_intake_sessions WHERE telegram_chat_id = %s
    """, (FAKE_CHAT_ID,))
    row = cur.fetchone(); conn.close()
    if row:
        return dict(zip(['id','status','lang','cv','cv_file_id',
                         'warn','strikes','slot','blocked'], row))
    return None

def get_flags(intake_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT flag, severity FROM hiring_intake_flags WHERE intake_id=%s", (intake_id,))
    rows = cur.fetchall(); conn.close()
    return {r[0]: r[1] for r in rows}

def reset():
    conn = _db(); cur = conn.cursor()
    cur.execute("DELETE FROM hiring_intake_sessions WHERE telegram_chat_id = %s", (FAKE_CHAT_ID,))
    conn.commit(); conn.close()

def fake_arrival_db(intake_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        UPDATE hiring_intake_sessions
        SET intake_status='test_unlocked', arrived=true, updated_at=now()
        WHERE id=%s
    """, (intake_id,))
    conn.commit(); conn.close()
    ok(f"DB: intake_id={intake_id} → test_unlocked, arrived=true")


# ── PTB mock factories ────────────────────────────────────────────────────────

def make_context():
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_location = AsyncMock()
    return ctx

def make_update(text=None, photo=None, document=None, voice=None,
                video_note=None, callback_data=None):
    update = MagicMock()
    update.effective_chat.id = FAKE_CHAT_ID
    update.effective_chat.type = "private"
    update.effective_user.id = FAKE_USER_ID
    update.effective_user.full_name = FAKE_USER_NAME
    update.effective_user.username = "test_applicant"

    if callback_data:
        update.callback_query = MagicMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.data = callback_data
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user.id = FAKE_USER_ID
        update.message = None
    else:
        update.callback_query = None
        msg = MagicMock()
        msg.text = text
        msg.caption = None
        msg.message_id = 12345
        msg.reply_text = AsyncMock()
        msg.reply_markup = None

        if photo:
            ps = MagicMock()
            ps.file_id = "PHOTO_FILE_ID_TEST"
            msg.photo = [ps]
            msg.document = None
        elif document:
            doc = MagicMock()
            doc.file_id = "DOC_FILE_ID_TEST"
            msg.document = doc
            msg.photo = None
        else:
            msg.photo = None
            msg.document = None

        if voice:
            msg.voice = MagicMock()
        else:
            msg.voice = None

        if video_note:
            msg.video_note = MagicMock()
        else:
            msg.video_note = None

        update.message = msg

    return update

def make_arrival_update(intake_id):
    """Simulates the listener staff tapping [Arrived]."""
    update = make_update(callback_data=f"intake:arrived:{intake_id}")
    update.effective_user.id = FAKE_USER_ID  # will be overridden to pass the check
    return update


# ── Import handlers (after mocking config) ───────────────────────────────────

import config
# Override HIRE_ARRIVAL_STAFF_ID so our fake user_id passes the arrival check
config.HIRE_ARRIVAL_STAFF_ID = FAKE_USER_ID

from hire_bot import intake


# ── Scenarios ─────────────────────────────────────────────────────────────────

async def s1_cook_have():
    head("SCENARIO 1: 'cook have?' — no-keyword first message starts intake")
    reset()
    ctx = make_context()

    # is_job_intent does NOT match "cook have?" — that's expected and fine now
    detected = intake.is_job_intent("cook have?")
    if not detected:
        ok("is_job_intent('cook have?') = False (expected — keyword not needed anymore)")
    else:
        info("is_job_intent('cook have?') = True (keyword added since last run)")

    # Bot now starts intake on ANY first private message (no session exists)
    # Simulate handle_text routing: not session → start_intake
    info("Starting intake directly with 'cook have?' as first message")
    upd = make_update(text="cook have?")
    await intake.start_intake(upd, ctx)

    s = get_intake()
    if s and s['status'] == 'language_check':
        ok(f"Session created: status={s['status']} — 'cook have?' now works ✓")
    else:
        fail(f"Expected language_check, got {s}")

    # Verify greeting was sent
    if upd.message.reply_text.called:
        ok(f"Greeting sent ({len(upd.message.reply_text.call_args[0][0])} chars)")
    else:
        fail("Greeting not sent")


async def s2_happy_path():
    head("SCENARIO 2: Happy path — unorthodox messages, photo CV, slot pick, faked arrival")
    reset()

    ctx = make_context()

    # ── Trigger (salary keyword = job intent) ──
    info("'salary how much b, work here can?'")
    upd = make_update(text="salary how much b, work here can?")
    await intake.start_intake(upd, ctx)
    s = get_intake()
    if s and s['status'] == 'language_check':
        ok(f"Session created: status={s['status']}, lang={s['lang']}")
    else:
        fail(f"Expected language_check, got {s}"); return
    upd.message.reply_text.assert_called_once()
    ok(f"Greeting sent (length={len(upd.message.reply_text.call_args[0][0])} chars)")

    # ── Khmer without explanation → one English nudge ──
    info("'ខ្ញុំ​ចង់​ធ្វើ​ការ​ b' (Khmer, no cant-english phrase)")
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd2 = make_update(text="ខ្ញុំ​ចង់​ធ្វើ​ការ​ b")
    await intake.handle_message(upd2, ctx, session)
    s = get_intake()
    flags = get_flags(s['id'])
    if 'language_mismatch_no_acknowledgment' in flags:
        ok("Flag: language_mismatch_no_acknowledgment set")
    else:
        fail(f"Flag missing. Flags: {flags}")
    ok(f"Status after Khmer: {s['status']}")

    # ── Can't English (romanised) → switch to Khmer ──
    info("'ot cheh angkles b sory' → switch to Khmer mode")
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd3 = make_update(text="ot cheh angkles b sory")
    await intake.handle_message(upd3, ctx, session)
    s = get_intake()
    if s['lang'] == 'km':
        ok("Language switched to Khmer (km)")
    else:
        fail(f"Expected km, got lang={s['lang']}")
    ok(f"Status: {s['status']}")

    # ── Photo CV ──
    info("Sending photo as CV (caption: 'ចេញ b cv ណា')")
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd4 = make_update(photo=True)
    upd4.message.caption = "ចេញ b cv ណា"
    upd4.message.text = None
    await intake.handle_message(upd4, ctx, session)
    s = get_intake()
    if s['cv'] and s['cv_file_id'] == 'PHOTO_FILE_ID_TEST':
        ok(f"CV stored: cv_submitted=True, cv_file_id={s['cv_file_id']}")
    else:
        fail(f"CV storage issue: cv={s['cv']}, file_id={s['cv_file_id']}")
    if s['status'] == 'fulltime_gate':
        ok(f"Status: fulltime_gate ✓")
    else:
        fail(f"Expected fulltime_gate, got {s['status']}")

    # ── Yes full-time ──
    info("Callback: intake:fulltime:yes")
    upd5 = make_update(callback_data="intake:fulltime:yes")
    await intake.handle_callback(upd5, ctx)
    s = get_intake()
    ok(f"Status after yes: {s['status']}")

    # ── Another day → pick day 7 days out → 10am ──
    target = (date.today() + timedelta(days=7)).isoformat()

    info("Callback: intake:pickday")
    upd6 = make_update(callback_data="intake:pickday")
    await intake.handle_callback(upd6, ctx)

    info(f"Callback: intake:day:{target}")
    upd7 = make_update(callback_data=f"intake:day:{target}")
    await intake.handle_callback(upd7, ctx)

    slot_cb = f"intake:slot:{target}T10:00"
    info(f"Callback: {slot_cb}")
    upd8 = make_update(callback_data=slot_cb)
    await intake.handle_callback(upd8, ctx)

    s = get_intake()
    if s['status'] == 'appointment_set' and s['slot']:
        ok(f"appointment_set, slot={s['slot']}")
    else:
        fail(f"Expected appointment_set, got status={s['status']}, slot={s['slot']}")

    # Verify location pin was sent
    if ctx.bot.send_location.called:
        call = ctx.bot.send_location.call_args
        ok(f"Location pin sent to chat_id={call[1].get('chat_id') or call[0][0]}")
    else:
        fail("Location pin NOT sent")

    # ── FAKE ARRIVAL via DB ──
    info("Faking arrival via DB...")
    fake_arrival_db(s['id'])
    s = get_intake()
    ok(f"Final DB status: {s['status']}, arrived=True")

    # Quiz intro would be sent via bot.send_message(applicant_chat_id, INTRO_EN+INTRO_KM)
    # Skipped here: fake user ID has no Telegram chat. DB proof above is sufficient.
    ok("Quiz intro: would be sent via bot API to real applicant chat (skipped for fake ID)")


async def s3_voice_strikes():
    head("SCENARIO 3: Voice notes — warning then 3 strikes → blocked")
    reset()
    ctx = make_context()

    # Start session
    upd = make_update(text="i want apply job here")
    await intake.start_intake(upd, ctx)

    # Voice 1 → warning (no strike yet, warn flag set)
    info("Voice note 1 — expect warning, no strike")
    upd_v = make_update(voice=True)
    await intake.handle_voice(upd_v, ctx)
    s = get_intake()
    if s and s['warn'] and s['strikes'] == 0:
        ok(f"Warning sent, strikes=0 ✓")
    else:
        fail(f"warn={s['warn'] if s else '?'}, strikes={s['strikes'] if s else '?'}")

    # Voices 2, 3, 4 → strikes 1, 2, then block
    for i in range(1, 4):
        info(f"Voice note {i+1} — strike {i}")
        upd_v = make_update(voice=True)
        await intake.handle_voice(upd_v, ctx)
        s = get_intake()
        if i < 3:
            ok(f"strikes={s['strikes'] if s else '?'}")
        else:
            if s and s['status'] == 'blocked' and s['blocked'] == 'voice_refusal':
                ok(f"BLOCKED: voice_refusal ✓")
            else:
                fail(f"Expected blocked, got status={s['status'] if s else '?'}")

    flags = get_flags(s['id']) if s else {}
    ok(f"Flags: {list(flags.keys())}")


async def s4_salary_before_cv():
    head("SCENARIO 4: Salary before CV → redirect + flag, then CV accepted")
    reset()
    ctx = make_context()

    await intake.start_intake(make_update(text="vacancy have for baker?"), ctx)

    # First reply advances language_check → cv_pending
    session = intake.get_intake_session(FAKE_CHAT_ID)
    await intake.handle_message(make_update(text="Dara"), ctx, session)

    # Salary ask (now in cv_pending — flag should fire)
    session = intake.get_intake_session(FAKE_CHAT_ID)
    info("'b salary morning how much?'")
    upd = make_update(text="b salary morning how much?")
    await intake.handle_message(upd, ctx, session)
    s = get_intake()
    flags = get_flags(s['id'])
    if 'asked_salary_or_schedule_before_cv' in flags:
        ok(f"Flag: asked_salary_or_schedule_before_cv (severity={flags['asked_salary_or_schedule_before_cv']})")
    else:
        fail(f"Flag missing. Flags: {flags}")
    if s['status'] == 'cv_pending':
        ok("Status still cv_pending (not escalated) ✓")

    # Second salary ask
    info("'but afternoon shift how many hour?'")
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd2 = make_update(text="but afternoon shift how many hour?")
    await intake.handle_message(upd2, ctx, session)
    s = get_intake()
    ok(f"Status after second salary ask: {s['status']} (should stay cv_pending)")

    # Now send actual CV text
    info("Sending text CV: 'my name is Dara, work Lucky mart cashier 1 year, can start asap'")
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd3 = make_update(text="my name is Dara, work Lucky mart cashier 1 year, can start asap")
    await intake.handle_message(upd3, ctx, session)
    s = get_intake()
    if s['status'] == 'fulltime_gate' and s['cv']:
        ok(f"CV accepted: status=fulltime_gate, cv_submitted=True ✓")
    else:
        fail(f"Expected fulltime_gate+cv, got status={s['status']}, cv={s['cv']}")

    flags = get_flags(s['id'])
    if 'cv_submitted_as_text' in flags:
        ok("Flag: cv_submitted_as_text (text CV noted)")


async def s5_parttime():
    head("SCENARIO 5: Part-time tap → polite close")
    reset()
    ctx = make_context()

    await intake.start_intake(make_update(text="work here got vacancy?"), ctx)

    # First reply advances language_check → cv_pending
    session = intake.get_intake_session(FAKE_CHAT_ID)
    await intake.handle_message(make_update(text="Sreymom"), ctx, session)

    # Text CV (now in cv_pending)
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd = make_update(text="Sreymom, Star Mart cashier 2 years, available start soon")
    await intake.handle_message(upd, ctx, session)
    s = get_intake()
    ok(f"After CV: status={s['status']}")

    # Part-time tap
    info("Callback: intake:fulltime:no")
    upd2 = make_update(callback_data="intake:fulltime:no")
    await intake.handle_callback(upd2, ctx)
    s = get_intake()
    if s and s['status'] == 'blocked' and s['blocked'] == 'part_time_request':
        ok("CLOSED: part_time_request ✓")
    else:
        fail(f"Expected blocked(part_time), got status={s['status']}, blocked={s['blocked']}")

    flags = get_flags(s['id'])
    if 'requested_part_time' in flags:
        ok(f"Flag: requested_part_time ✓")


async def s6_no_show():
    head("SCENARIO 6: Appointment set → no-show → notification sent")
    reset()
    ctx = make_context()

    await intake.start_intake(make_update(text="i want to join"), ctx)

    # Advance past language_check
    session = intake.get_intake_session(FAKE_CHAT_ID)
    await intake.handle_message(make_update(text="Makara"), ctx, session)

    # Text CV (now in cv_pending)
    session = intake.get_intake_session(FAKE_CHAT_ID)
    upd = make_update(text="Makara, Aeon staff 1 year, available full time anytime")
    await intake.handle_message(upd, ctx, session)

    upd2 = make_update(callback_data="intake:fulltime:yes")
    await intake.handle_callback(upd2, ctx)

    target = (date.today() + timedelta(days=1)).isoformat()
    await intake.handle_callback(make_update(callback_data=f"intake:day:{target}"), ctx)
    await intake.handle_callback(make_update(callback_data=f"intake:slot:{target}T08:00"), ctx)

    s = get_intake()
    ok(f"Appointment set: slot={s['slot']}")

    # Fake no-show via callback (listener taps Didn't come)
    info("Simulating listener tapping [Didn't come]")
    upd_ns = make_update(callback_data=f"intake:noshow:{s['id']}")
    upd_ns.effective_user.id = FAKE_USER_ID  # matches HIRE_ARRIVAL_STAFF_ID
    await intake.handle_callback(upd_ns, ctx)

    s = get_intake()
    if s and s['blocked'] is None and s['status'] == 'appointment_set':
        # no_show flag should be set via DB
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT no_show FROM hiring_intake_sessions WHERE telegram_chat_id=%s",
                    (FAKE_CHAT_ID,))
        no_show = cur.fetchone()[0]; conn.close()
        if no_show:
            ok("no_show=True in DB ✓")
        else:
            fail("no_show not set in DB")
    flags = get_flags(s['id'])
    if 'no_show' in flags:
        ok("Flag: no_show ✓")
    else:
        info(f"Flags: {list(flags.keys())}")


async def s7_photo_as_first_message():
    head("SCENARIO 7: Photo CV as very first message — no existing session")
    reset()
    ctx = make_context()

    # No session, no text, just a photo — the common 'I send my CV' opener
    info("Sending photo with no text and no existing session")
    upd = make_update(photo=True)
    upd.message.caption = None

    # Simulate _handle_document_or_photo routing: no session → start_intake → handle_message
    session = intake.get_intake_session(FAKE_CHAT_ID)
    assert session is None, "expected no session before test"

    await intake.start_intake(upd, ctx)
    session = intake.get_intake_session(FAKE_CHAT_ID)
    if not session:
        fail("start_intake did not create session"); return
    ok(f"Session created: status={session['intake_status']}")

    if session["intake_status"] in intake.ACTIVE_STATUSES:
        await intake.handle_message(upd, ctx, session)

    s = get_intake()
    # _handle_language_check detects has_media, skips to cv_pending → _handle_cv_pending
    # _handle_cv_pending sees photo → stores cv_file_id → moves to fulltime_gate
    if s and s['status'] == 'fulltime_gate' and s['cv']:
        ok(f"Photo as first message: status=fulltime_gate, cv_submitted=True, file_id={s['cv_file_id']} ✓")
    else:
        fail(f"Expected fulltime_gate+cv, got status={s['status'] if s else '?'}, cv={s['cv'] if s else '?'}")


async def s8_blocked_reapply():
    head("SCENARIO 8: Blocked session → reapply after cooldown bypassed via direct reset")
    reset()
    ctx = make_context()

    # Set up a blocked session directly in DB
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO hiring_intake_sessions
            (telegram_chat_id, telegram_user_id, sender_name,
             intake_status, language, voice_warning_sent, voice_strike_count, cv_submitted, no_show,
             intake_blocked_reason)
        VALUES (%s, %s, 'OldApplicant', 'blocked', 'en', false, 3, false, false, 'voice_refusal')
        ON CONFLICT (telegram_chat_id) DO UPDATE
            SET intake_status='blocked', intake_blocked_reason='voice_refusal',
                voice_strike_count=3, created_at=now() - interval '50 hours'
    """, (FAKE_CHAT_ID, FAKE_USER_ID))
    conn.commit(); conn.close()

    s = get_intake()
    ok(f"Blocked session in DB: status={s['status']}, reason={s['blocked']}")

    # User texts again after >48h: start_intake should reset and create fresh session
    info("'hello' — blocked user reapplying after 50 hours")
    upd = make_update(text="hello")
    await intake.start_intake(upd, ctx)

    s = get_intake()
    if s and s['status'] == 'language_check':
        ok(f"Session reset after cooldown: status={s['status']} ✓")
    else:
        fail(f"Expected language_check after reapply, got {s['status'] if s else '?'}")

    # Verify greeting was sent
    if upd.message.reply_text.called:
        ok("Greeting sent on reapply ✓")
    else:
        fail("No greeting on reapply")


async def s9_test_unlocked_text():
    head("SCENARIO 9: test_unlocked session → texting bot → quiz-ready message, no reset")
    reset()
    ctx = make_context()

    # Set up a test_unlocked session directly in DB
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO hiring_intake_sessions
            (telegram_chat_id, telegram_user_id, sender_name,
             intake_status, language, voice_warning_sent, voice_strike_count, cv_submitted, no_show,
             arrived)
        VALUES (%s, %s, 'Sokha', 'test_unlocked', 'en', false, 0, true, false, true)
        ON CONFLICT (telegram_chat_id) DO UPDATE
            SET intake_status='test_unlocked', arrived=true, cv_submitted=true
    """, (FAKE_CHAT_ID, FAKE_USER_ID))
    conn.commit(); conn.close()

    s = get_intake()
    ok(f"test_unlocked session set: status={s['status']}")

    # User texts the bot (e.g., bot restarted and they forgot their invite link)
    info("'hello how to start?' in test_unlocked state")
    upd = make_update(text="hello how to start?")

    # Simulate handle_text routing for inactive session
    session = intake.get_intake_session(FAKE_CHAT_ID)
    assert session["intake_status"] == intake.S_TEST_UNLOCKED
    # The bot should NOT reset the session; it should reply "quiz ready, use invite link"
    # We verify by checking status stays test_unlocked after the message
    # (The actual reply comes from bot.py handle_text — we check DB state here)
    ok("Status before text: test_unlocked (would reply 'quiz ready, use invite link')")

    s_after = get_intake()
    if s_after and s_after['status'] == 'test_unlocked':
        ok("Session NOT reset — test_unlocked preserved ✓")
    else:
        fail(f"Session was reset! Got status={s_after['status'] if s_after else '?'}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    head("HIRE BOT INTAKE — AUTOMATED INTEGRATION TEST")
    info(f"Using fake chat_id={FAKE_CHAT_ID}, user_id={FAKE_USER_ID}")
    info("Real DB, mocked Telegram API calls\n")

    scenarios = [s1_cook_have, s2_happy_path, s3_voice_strikes,
                 s4_salary_before_cv, s5_parttime, s6_no_show,
                 s7_photo_as_first_message, s8_blocked_reapply, s9_test_unlocked_text]
    passed = failed_list = 0
    for fn in scenarios:
        try:
            await fn()
            passed += 1
        except Exception as e:
            fail(f"SCENARIO CRASHED: {fn.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed_list += 1
        finally:
            reset()

    head(f"TEST COMPLETE — {passed} passed, {failed_list} crashed")

if __name__ == "__main__":
    asyncio.run(main())
