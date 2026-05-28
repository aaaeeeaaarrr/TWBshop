"""
Automated integration test for hire_bot intake funnel.
Uses Telethon (listener account) to simulate an applicant messaging the bot.
Stops the listener for the duration, restarts it after.
Run: python run_test_intake.py
"""

import asyncio
import subprocess
import sys
import os

sys.path.insert(0, '/root/TWBshop')

import psycopg2
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


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)

def get_intake(user_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT id, intake_status, language, cv_submitted,
               voice_warning_sent, voice_strike_count,
               appointment_slot, intake_blocked_reason
        FROM hiring_intake_sessions
        WHERE telegram_user_id = %s
        ORDER BY created_at DESC LIMIT 1
    """, (user_id,))
    row = cur.fetchone(); conn.close()
    if row:
        return dict(zip(['id','status','lang','cv','warn','strikes','slot','blocked'], row))
    return None

def get_flags(intake_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT flag FROM hiring_intake_flags WHERE intake_id = %s", (intake_id,))
    flags = [r[0] for r in cur.fetchall()]; conn.close()
    return flags

def reset_intake(user_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("DELETE FROM hiring_intake_sessions WHERE telegram_user_id = %s", (user_id,))
    conn.commit(); conn.close()
    info(f"DB reset for user_id={user_id}")

def fake_arrival_db(intake_id):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        UPDATE hiring_intake_sessions
        SET intake_status = 'test_unlocked', arrived = true, updated_at = now()
        WHERE id = %s
    """, (intake_id,))
    conn.commit(); conn.close()
    ok(f"DB: intake_id={intake_id} → test_unlocked, arrived=true")


# ── Telethon helpers ──────────────────────────────────────────────────────────

async def wait_reply(client, bot, after_id, timeout=10):
    for _ in range(timeout * 4):
        await asyncio.sleep(0.25)
        msgs = await client.get_messages(bot, limit=5)
        for m in msgs:
            if m.id > after_id and not m.out:
                return m
    return None

async def last_in_id(client, bot):
    msgs = await client.get_messages(bot, limit=10)
    ids = [m.id for m in msgs if not m.out]
    return max(ids) if ids else 0

async def send_wait(client, bot, text, timeout=10):
    sent = await client.send_message(bot, text)
    return await wait_reply(client, bot, after_id=sent.id, timeout=timeout)

async def click_cb(client, bot, cb_data: str, timeout=10):
    """Find latest bot message with buttons and click by callback_data."""
    msgs = await client.get_messages(bot, limit=10)
    for m in msgs:
        if not m.out and m.reply_markup:
            try:
                await m.click(data=cb_data.encode())
                return await wait_reply(client, bot, after_id=m.id, timeout=timeout)
            except Exception as e:
                fail(f"click({cb_data}) error: {e}")
                return None
    fail(f"No message with buttons to click {cb_data}")
    return None

async def send_voice(client, bot):
    voice_path = '/tmp/test_voice.ogg'
    if not os.path.exists(voice_path):
        subprocess.run(
            ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=8000:cl=mono',
             '-t', '1', '-c:a', 'libopus', voice_path],
            capture_output=True
        )
    sent = await client.send_file(bot, voice_path, voice_note=True)
    return await wait_reply(client, bot, after_id=sent.id, timeout=10)


# ── Scenarios ─────────────────────────────────────────────────────────────────

async def s1_cook_have(client, bot, uid):
    head("SCENARIO 1: 'cook have?' — intent gap check")
    reset_intake(uid)

    last = await last_in_id(client, bot)
    await client.send_message(bot, "cook have?")
    await asyncio.sleep(4)
    reply = await wait_reply(client, bot, after_id=last, timeout=5)

    if reply is None:
        fail("Bot silent — 'cook have?' not detected as job intent")
        info("GAP: 'cook' not in _EN_INTENT. Anyone messaging from a job-ad link IS an applicant.")
        info("RECOMMENDATION: catch ALL first messages on this bot, not keyword-gated.")
    else:
        ok(f"Bot responded: {reply.text[:80]}")


async def s2_happy_path(client, bot, uid):
    head("SCENARIO 2: Happy path — unorthodox Khmer-mix, photo CV, slot pick, faked arrival")
    reset_intake(uid)

    # Trigger via salary keyword (also job intent)
    info("Msg: 'salary how much b, work here can?'")
    reply = await send_wait(client, bot, "salary how much b, work here can?")
    if reply:
        ok(f"Greeting ({len(reply.text)} chars)")
    else:
        fail("No greeting"); return

    s = get_intake(uid)
    assert s and s['status'] == 'language_check', f"Expected language_check, got {s}"
    ok(f"DB: {s['status']}")

    # Khmer reply without explaining → one English nudge
    info("Msg: 'ខ្ញុំ​ចង់​ធ្វើ​ការ​ b'  (Khmer, no explanation)")
    reply = await send_wait(client, bot, "ខ្ញុំ​ចង់​ធ្វើ​ការ​ b")
    if reply and ("english" in reply.text.lower() or "អង់គ្លេស" in reply.text):
        ok("Got English nudge")
    else:
        info(f"Response: {reply.text[:100] if reply else 'none'}")

    # Can't do English (romanised Khmer — how real people type it)
    info("Msg: 'ot cheh angkles b sory'")
    reply = await send_wait(client, bot, "ot cheh angkles b sory")
    if reply and ("CV" in reply.text or "ប្រវត្ត" in reply.text):
        ok("Switched to Khmer, CV requested")
    else:
        info(f"Response: {reply.text[:100] if reply else 'none'}")

    s = get_intake(uid)
    ok(f"DB: status={s['status']}, lang={s['lang']}")

    # Photo CV
    info("Sending photo as fake CV (caption: 'ចេញ b cv ណា')")
    sent_photo = await client.send_file(
        bot, '/root/TWBshop/photos/shop_qr.jpg', caption='ចេញ b cv ណា'
    )
    reply = await wait_reply(client, bot, after_id=sent_photo.id, timeout=12)
    s = get_intake(uid)
    if s and s['cv']:
        ok(f"CV stored: cv_submitted=True, status={s['status']}")
    else:
        fail(f"CV not stored: {s}")
    if reply and reply.reply_markup:
        ok("Full-time gate with buttons received")
    else:
        info(f"Full-time response: {reply.text[:80] if reply else 'none'}")

    # Yes full-time
    info("Clicking: Yes full-time")
    reply = await click_cb(client, bot, "intake:fulltime:yes")
    s = get_intake(uid)
    ok(f"DB: status={s['status']}")

    # Another day → 7 days out → 10am
    info("Clicking: Another day picker")
    reply = await click_cb(client, bot, "intake:pickday")

    target = (date.today() + timedelta(days=7)).isoformat()
    info(f"Clicking day: {target}")
    reply = await click_cb(client, bot, f"intake:day:{target}")

    slot_cb = f"intake:slot:{target}T10:00"
    info(f"Clicking slot: {slot_cb}")
    reply = await click_cb(client, bot, slot_cb)

    await asyncio.sleep(3)
    s = get_intake(uid)
    if s and s['status'] == 'appointment_set':
        ok(f"DB: appointment_set, slot={s['slot']}")
    else:
        fail(f"Expected appointment_set, got {s}")

    # Check confirmation msg + location pin
    msgs = await client.get_messages(bot, limit=8)
    confirm = next((m for m in msgs if not m.out and m.text and
                    ("confirm" in m.text.lower() or "បញ្ជាក់" in m.text or "Wine Bakery" in m.text)), None)
    location = next((m for m in msgs if not m.out and m.geo), None)

    if confirm:
        ok(f"Appointment confirmation: '{confirm.text[:80]}'")
    else:
        fail("No confirmation message found")
    if location:
        ok(f"Location pin: ({location.geo.lat:.4f}, {location.geo.long:.4f})")
    else:
        fail("No location pin")

    # FAKE ARRIVAL via DB
    info("Faking arrival via DB...")
    fake_arrival_db(s['id'])

    # Send quiz intro directly via bot token
    from secrets import HIRE_BOT_TOKEN
    from telegram import Bot as TGBot
    from hire_bot.bot import INTRO_EN, INTRO_KM, _kb_ready
    tg_bot = TGBot(token=HIRE_BOT_TOKEN)
    await tg_bot.send_message(uid, INTRO_EN + "\n\n───\n\n" + INTRO_KM, reply_markup=_kb_ready())
    await tg_bot.close()
    ok("Quiz intro sent → test_unlocked simulation complete")


async def s3_voice_strikes(client, bot, uid):
    head("SCENARIO 3: Voice notes — warning then 3 strikes → blocked")
    reset_intake(uid)

    await send_wait(client, bot, "i want apply job here")

    # Voice 1 → warning (no strike yet)
    info("Voice note 1 — should get warning")
    reply = await send_voice(client, bot)
    s = get_intake(uid)
    if s and s['warn'] and s['strikes'] == 0:
        ok(f"Warning sent, strikes=0 (correct)")
    else:
        info(f"warn={s['warn'] if s else '?'}, strikes={s['strikes'] if s else '?'}")
    if reply: info(f"Bot: '{reply.text[:80]}'")

    # Voice 2 → strike 1
    info("Voice note 2 — strike 1")
    reply = await send_voice(client, bot)
    s = get_intake(uid)
    ok(f"strikes={s['strikes'] if s else '?'}")
    if reply: info(f"Bot: '{reply.text[:60]}'")

    # Voice 3 → strike 2
    info("Voice note 3 — strike 2")
    reply = await send_voice(client, bot)
    s = get_intake(uid)
    ok(f"strikes={s['strikes'] if s else '?'}")
    if reply: info(f"Bot: '{reply.text[:60]}'")

    # Voice 4 → strike 3 → blocked
    info("Voice note 4 — strike 3 → should block")
    reply = await send_voice(client, bot)
    s = get_intake(uid)
    if s and s['status'] == 'blocked' and s['blocked'] == 'voice_refusal':
        ok(f"BLOCKED: reason=voice_refusal ✓")
    else:
        fail(f"status={s['status'] if s else '?'}, blocked={s['blocked'] if s else '?'}")
    if reply: ok(f"Block msg: '{reply.text[:80]}'")

    flags = get_flags(s['id']) if s else []
    ok(f"Flags set: {flags}")


async def s4_salary_before_cv(client, bot, uid):
    head("SCENARIO 4: Salary/schedule before CV → redirect + flag")
    reset_intake(uid)

    await send_wait(client, bot, "vacancy have for baker?")

    info("Msg: 'b salary morning how much?' (salary before CV)")
    reply = await send_wait(client, bot, "b salary morning how much?")
    if reply and ("cv" in reply.text.lower() or "CV" in reply.text or "ប្រវត្ត" in reply.text):
        ok(f"Redirected to CV: '{reply.text[:80]}'")
    else:
        fail(f"Expected redirect, got: {reply.text[:80] if reply else 'none'}")

    s = get_intake(uid)
    flags = get_flags(s['id']) if s else []
    if 'asked_salary_or_schedule_before_cv' in flags:
        ok("Flag: asked_salary_or_schedule_before_cv ✓")
    else:
        fail(f"Flag missing. Flags: {flags}")

    # Second salary ask — still redirects, not escalated
    info("Msg: 'but afternoon shift how many hour?' (schedule again)")
    reply = await send_wait(client, bot, "but afternoon shift how many hour?")
    info(f"Bot: '{reply.text[:80] if reply else 'none'}'")

    # Now actually send a CV to move on
    info("Sending text CV (>30 chars) to proceed")
    reply = await send_wait(client, bot,
        "my name is Dara, i work at Lucky mart before as cashier 1 year", timeout=12)
    s = get_intake(uid)
    if s and s['status'] == 'fulltime_gate':
        ok(f"CV accepted, status=fulltime_gate")
    else:
        info(f"Status: {s['status'] if s else 'none'}")


async def s5_parttime(client, bot, uid):
    head("SCENARIO 5: Part-time tap → polite close")
    reset_intake(uid)

    await send_wait(client, bot, "work here got vacancy?")
    await asyncio.sleep(1)

    info("Text CV: 'Sreymom, Star Mart cashier 2 years, can start soon'")
    reply = await send_wait(client, bot,
        "Sreymom, Star Mart cashier 2 years, can start soon", timeout=12)
    if reply and reply.reply_markup:
        ok("Full-time gate appeared")
    else:
        info(f"Response: {reply.text[:80] if reply else 'none'}")

    info("Clicking: No, part-time")
    reply = await click_cb(client, bot, "intake:fulltime:no")
    await asyncio.sleep(2)

    s = get_intake(uid)
    if s and s['status'] == 'blocked' and s['blocked'] == 'part_time_request':
        ok("CLOSED: reason=part_time_request ✓")
    else:
        fail(f"status={s['status'] if s else '?'}, blocked={s['blocked'] if s else '?'}")

    msgs = await client.get_messages(bot, limit=5)
    close = next((m for m in msgs if not m.out and m.text and
                  ("full-time" in m.text.lower() or "ពេញម៉ោង" in m.text or "schedule" in m.text.lower())), None)
    if close:
        ok(f"Close message: '{close.text[:100]}'")
    else:
        fail("Close message not found in recent messages")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    from secrets import TELETHON_API_ID, TELETHON_API_HASH, TELETHON_PHONE
    from telethon import TelegramClient

    head("HIRE BOT INTAKE — AUTOMATED INTEGRATION TEST")

    # Stop listener to free the session file
    info("Stopping listener...")
    subprocess.run(['pkill', '-f', 'run_listener.py'])
    await asyncio.sleep(2)

    client = TelegramClient('/root/TWBshop/ops_listener', TELETHON_API_ID, TELETHON_API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        fail("Telethon session not authorized — run listener interactively first")
        await client.disconnect()
        return

    me = await client.get_me()
    uid = me.id
    info(f"Authenticated as user_id={uid} (@{me.username or me.first_name})")

    bot = await client.get_entity("@HR_twb_bot")
    info(f"Bot: @HR_twb_bot (id={bot.id})\n")

    try:
        await s1_cook_have(client, bot, uid)
        await s2_happy_path(client, bot, uid)
        await s3_voice_strikes(client, bot, uid)
        await s4_salary_before_cv(client, bot, uid)
        await s5_parttime(client, bot, uid)
    finally:
        reset_intake(uid)
        await client.disconnect()

        # Restart listener
        info("\nRestarting listener...")
        subprocess.Popen(
            ['python3', 'run_listener.py'],
            stdout=open('logs/listener.log', 'a'),
            stderr=subprocess.STDOUT,
            cwd='/root/TWBshop'
        )
        await asyncio.sleep(3)
        result = subprocess.run(['pgrep', '-f', 'run_listener.py'], capture_output=True)
        if result.returncode == 0:
            ok("Listener restarted")
        else:
            fail("Listener may not have restarted — check manually")

        head("TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
