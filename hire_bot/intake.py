"""
Intake funnel for public-ad applicants.

State machine:
  language_check      → first greeting sent, waiting for reply
  cv_pending          → language settled, asking for CV / work history
  fulltime_gate       → CV received, showing full-time confirmation button
  appointment_pending → full-time confirmed, showing slot buttons
  appointment_set     → slot confirmed, waiting for arrival day
  blocked             → voice refusal or part-time request
  test_unlocked       → owner confirmed arrival, quiz started

Rules:
  - No Claude/Anthropic API calls at any stage before test_unlocked.
  - Voice notes: warning + 3 strikes = blocked.
  - Part-time: hard gate, close politely.
  - Salary/schedule questions before CV: redirect once, record flag.
  - Language: start English. If applicant can't do English, switch to Khmer.
  - Appointment slots: fixed buttons (8am/10am/12pm/2pm/4pm), PP time.
  - Arrival confirmed by owner via private-chat button.
"""

import logging
import sys
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError

sys.path.insert(0, '/root/TWBshop')
import config

logger = logging.getLogger(__name__)

PP_TZ = ZoneInfo("Asia/Phnom_Penh")
SLOT_HOURS = [8, 10, 12, 14, 16]  # displayed as 8am/10am/12pm/2pm/4pm
COOLDOWN_HOURS = 48  # hours before a blocked/completed person can restart

# Status constants
S_LANGUAGE_CHECK    = "language_check"
S_CV_PENDING        = "cv_pending"
S_FULLTIME_GATE     = "fulltime_gate"
S_APPOINTMENT       = "appointment_pending"
S_APPT_SET          = "appointment_set"
S_BLOCKED           = "blocked"
S_TEST_UNLOCKED     = "test_unlocked"

ACTIVE_STATUSES = {S_LANGUAGE_CHECK, S_CV_PENDING, S_FULLTIME_GATE, S_APPOINTMENT, S_APPT_SET}

# Job-intent keywords (English + Khmer)
_EN_INTENT = [
    "job", "work", "hire", "hiring", "apply", "application", "position", "vacancy",
    "cv", "resume", "staff", "employ", "interview", "salary", "opening", "join",
]
_KM_INTENT = [
    "ការងារ", "ធ្វើការ", "ជ្រើសរើស", "ដាក់ពាក្យ", "បុគ្គលិក",
    "ចង់ធ្វើ", "ចំណាប់អារម្មណ៍", "ស្វែងរក", "cv", "CV",
]

_SALARY_SCHEDULE_KW = [
    "salary", "pay", "wage", "money", "how much", "schedule", "shift", "hour",
    "time", "morning", "evening", "night", "afternoon", "ប្រាក់ខែ", "ម៉ោង",
    "ផ្លាស", "ព្រឹក", "ល្ងាច", "យប់", "រសៀល",
]

_CANT_ENGLISH = [
    "can't speak english", "dont speak english", "don't speak english", "no english",
    "cannot speak english", "not speak", "weak english", "poor english",
    "ot cheh angkles", "ot mean angkles", "angkles ot ban", "ot niyeay",
    "អត់ចេះ", "អត់ mean", "ot ban",
]


# ── DB ────────────────────────────────────────────────────────────────────────

def _conn():
    from secrets import DATABASE_URL
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def get_intake_session(chat_id: int) -> dict | None:
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, telegram_user_id, sender_name, intake_status, language,
                   cv_submitted, cv_format, voice_warning_sent, voice_strike_count,
                   appointment_slot, intake_blocked_reason, arrived, no_show, created_at
            FROM hiring_intake_sessions
            WHERE telegram_chat_id = %s
        """, (chat_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = ["id", "telegram_user_id", "sender_name", "intake_status", "language",
                "cv_submitted", "cv_format", "voice_warning_sent", "voice_strike_count",
                "appointment_slot", "intake_blocked_reason", "arrived", "no_show", "created_at"]
        return dict(zip(cols, row))
    finally:
        cur.close()
        conn.close()


def _create_session(chat_id: int, user_id: int, sender_name: str) -> int:
    conn = _conn()
    cur = conn.cursor()
    try:
        # Upsert: if an old blocked/unlocked session exists for this chat, replace it
        cur.execute("""
            INSERT INTO hiring_intake_sessions
                (telegram_chat_id, telegram_user_id, sender_name,
                 intake_status, language,
                 voice_warning_sent, voice_strike_count,
                 cv_submitted, no_show)
            VALUES (%s, %s, %s, %s, 'en', false, 0, false, false)
            ON CONFLICT (telegram_chat_id) DO UPDATE
                SET telegram_user_id   = EXCLUDED.telegram_user_id,
                    sender_name        = EXCLUDED.sender_name,
                    intake_status      = EXCLUDED.intake_status,
                    language           = EXCLUDED.language,
                    voice_warning_sent = EXCLUDED.voice_warning_sent,
                    voice_strike_count = EXCLUDED.voice_strike_count,
                    cv_submitted       = EXCLUDED.cv_submitted,
                    cv_format          = NULL,
                    appointment_slot   = NULL,
                    appointment_confirmed_at = NULL,
                    arrived            = NULL,
                    no_show            = false,
                    intake_blocked_reason = NULL,
                    updated_at         = now(),
                    created_at         = now()
            RETURNING id
        """, (chat_id, user_id, sender_name, S_LANGUAGE_CHECK))
        intake_id = cur.fetchone()[0]
        conn.commit()
        return intake_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _update(intake_id: int, **fields) -> None:
    if not fields:
        return
    conn = _conn()
    cur = conn.cursor()
    try:
        set_clause = ", ".join(f"{k} = %s" for k in fields)
        values = list(fields.values()) + [intake_id]
        cur.execute(
            f"UPDATE hiring_intake_sessions SET {set_clause}, updated_at = now() WHERE id = %s",
            values
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _flag(intake_id: int, flag: str, severity: str = "gap_low") -> None:
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_intake_flags (intake_id, flag, severity)
            VALUES (%s, %s, %s)
            ON CONFLICT (intake_id, flag) DO NOTHING
        """, (intake_id, flag, severity))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _get_pending_arrivals() -> list[dict]:
    """Return intake sessions with appointment_slot in the next 35 minutes (PP time)."""
    conn = _conn()
    cur = conn.cursor()
    try:
        pp_now = datetime.now(PP_TZ)
        cur.execute("""
            SELECT id, telegram_chat_id, sender_name, appointment_slot, language
            FROM hiring_intake_sessions
            WHERE intake_status = %s
              AND appointment_slot BETWEEN %s AND %s
        """, (S_APPT_SET, pp_now, pp_now + timedelta(minutes=35)))
        cols = ["id", "telegram_chat_id", "sender_name", "appointment_slot", "language"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


# ── Text helpers ──────────────────────────────────────────────────────────────

def _t(lang: str, en: str, km: str) -> str:
    """Bilingual (en+km) when language='en'; Khmer-only when language='km'."""
    if lang == "km":
        return km
    return f"{en}\n\n{km}"


def _is_khmer(text: str) -> bool:
    if not text:
        return False
    khmer = sum(1 for c in text if 'ក' <= c <= '៿')
    return khmer > 2 or (len(text) > 0 and khmer / max(len(text), 1) > 0.2)


def _implies_cant_english(text: str) -> bool:
    t = text.lower()
    for p in _CANT_ENGLISH:
        if p in t:
            return True
    return False


def _is_salary_schedule(text: str) -> bool:
    t = text.lower()
    for kw in _SALARY_SCHEDULE_KW:
        if kw.lower() in t:
            return True
    return False


def is_job_intent(text: str) -> bool:
    if not text:
        return False
    tl = text.lower()
    for kw in _EN_INTENT:
        if kw in tl:
            return True
    for kw in _KM_INTENT:
        if kw in text:
            return True
    return False


# ── Appointment slot helpers ──────────────────────────────────────────────────

def _pp_now() -> datetime:
    return datetime.now(PP_TZ)


def _slot_label(h: int) -> str:
    if h == 12:
        return "12:00pm"
    elif h < 12:
        return f"{h}:00am"
    else:
        return f"{h - 12}:00pm"


def _slot_dt(d: date, h: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, 0, tzinfo=PP_TZ)


def _today_available(pp_now: datetime) -> list[int]:
    """Hours available today: slot must be at least 1 hour away."""
    cutoff = pp_now + timedelta(hours=1)
    return [h for h in SLOT_HOURS if _slot_dt(pp_now.date(), h) > cutoff]


def kb_appointment() -> InlineKeyboardMarkup:
    pp_now = _pp_now()
    today = pp_now.date()
    tomorrow = today + timedelta(days=1)
    rows = []

    for h in _today_available(pp_now):
        rows.append([InlineKeyboardButton(
            f"Today {_slot_label(h)}",
            callback_data=f"intake:slot:{today.isoformat()}T{h:02d}:00",
        )])

    rows.append([InlineKeyboardButton(
        "Tomorrow ➜",
        callback_data=f"intake:day:{tomorrow.isoformat()}",
    )])
    rows.append([InlineKeyboardButton(
        "Another day ➜",
        callback_data="intake:pickday",
    )])
    return InlineKeyboardMarkup(rows)


def kb_day_slots(target_date: date) -> InlineKeyboardMarkup:
    day_label = target_date.strftime("%-d %b")  # "28 May"
    rows = []
    for h in SLOT_HOURS:
        rows.append([InlineKeyboardButton(
            f"{day_label} {_slot_label(h)}",
            callback_data=f"intake:slot:{target_date.isoformat()}T{h:02d}:00",
        )])
    rows.append([InlineKeyboardButton("◀ Back", callback_data="intake:appt_back")])
    return InlineKeyboardMarkup(rows)


def kb_pick_day() -> InlineKeyboardMarkup:
    today = _pp_now().date()
    rows = []
    for i in range(1, 8):
        d = today + timedelta(days=i)
        label = d.strftime("%-d %b")  # "29 May"
        rows.append([InlineKeyboardButton(label, callback_data=f"intake:day:{d.isoformat()}")])
    rows.append([InlineKeyboardButton("◀ Back", callback_data="intake:appt_back")])
    return InlineKeyboardMarkup(rows)


def kb_fulltime(lang: str) -> InlineKeyboardMarkup:
    if lang == "km":
        yes_label = "បាទ/ចាស ខ្ញុំអាចធ្វើការពេញម៉ោង"
        no_label  = "ទេ ខ្ញុំត្រូវការពាក់កណ្តាលម៉ោង"
    else:
        yes_label = "Yes, I can work full-time  /  បាទ/ចាស ខ្ញុំអាច"
        no_label  = "No, I need part-time  /  ទេ ខ្ញុំត្រូវការ part-time"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes_label, callback_data="intake:fulltime:yes")],
        [InlineKeyboardButton(no_label,  callback_data="intake:fulltime:no")],
    ])


def kb_arrived(intake_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Arrived",        callback_data=f"intake:arrived:{intake_id}"),
        InlineKeyboardButton("❌ Didn't come",    callback_data=f"intake:noshow:{intake_id}"),
    ]])


# ── Public entry point ────────────────────────────────────────────────────────

async def start_intake(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Called when a new user sends a job-intent message (or /start with no token).
    Creates or resets an intake session and sends the opening greeting.
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    existing = get_intake_session(chat_id)

    if existing:
        status = existing["intake_status"]
        # Still active — resume from current state
        if status in ACTIVE_STATUSES:
            await _resume_state(update, context, existing)
            return
        # Blocked recently — enforce cooldown
        if status == S_BLOCKED:
            age_hours = (datetime.now(PP_TZ) - existing["created_at"].astimezone(PP_TZ)).total_seconds() / 3600
            if age_hours < COOLDOWN_HOURS:
                remaining = int(COOLDOWN_HOURS - age_hours)
                await update.message.reply_text(
                    f"Your previous application was closed. "
                    f"Please wait {remaining} more hour(s) before applying again.\n\n"
                    f"ការដាក់ពាក្យមុនរបស់ប្អូនត្រូវបានបិទ។ "
                    f"សូមរង់ចាំ {remaining} ម៉ោងទៀត មុននឹងដាក់ពាក្យម្តងទៀត។"
                )
                return

    _create_session(chat_id, user.id, user.full_name or user.username or "Applicant")

    await update.message.reply_text(
        "Hello! Thank you for your interest in joining The Wine Bakery. 🙏\n\n"
        "This is our official application process. Please read carefully and reply "
        "in writing — voice messages are not accepted.\n\n"
        "Please tell us your name and what position you are interested in.\n\n"
        "———\n\n"
        "ជំរាបសួរ! អរគុណដែលប្អូនចាប់អារម្មណ៍ចង់ចូលរួមជាមួយ The Wine Bakery។ 🙏\n\n"
        "នេះជាដំណើរការដាក់ពាក្យផ្លូវការរបស់យើង។ សូមអានដោយយកចិត្តទុកដាក់ "
        "ហើយឆ្លើយតបជាអក្សរ — យើងមិនទទួលសារសំឡេងទេ។\n\n"
        "សូមប្រាប់ឈ្មោះរបស់ប្អូន និងតំណែងដែលប្អូនចាប់អារម្មណ៍។"
    )


# ── Main message router ───────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         session: dict) -> None:
    """Route a text/photo/document message within an active intake session."""
    status = session["intake_status"]

    if status == S_LANGUAGE_CHECK:
        await _handle_language_check(update, context, session)
    elif status == S_CV_PENDING:
        await _handle_cv_pending(update, context, session)
    elif status == S_FULLTIME_GATE:
        await _prompt_button(update, session)
    elif status == S_APPOINTMENT:
        await _prompt_button(update, session)
    elif status == S_APPT_SET:
        await _remind_slot(update, session)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Intercepts voice notes at any point (group=-1, fires before quiz handlers).
    Applies escalating warnings; blocks after 3 strikes post-warning.
    """
    if update.effective_chat.type != "private":
        return

    chat_id = update.effective_chat.id
    session = get_intake_session(chat_id)

    if session is None:
        # Not in intake — generic warning, no tracking
        await update.message.reply_text(
            "Please type your message. Voice messages are not accepted.\n\n"
            "សូមវាយជាអក្សរ។ យើងមិនទទួលសារសំឡេងទេ។"
        )
        return

    if session["intake_status"] in (S_BLOCKED, S_TEST_UNLOCKED):
        return

    intake_id = session["id"]
    lang = session["language"]

    if not session["voice_warning_sent"]:
        _update(intake_id, voice_warning_sent=True)
        _flag(intake_id, "voice_warning_1", "gap_low")
        await update.message.reply_text(_t(lang,
            en="Please type your message. Voice messages are not accepted for job applications. "
               "This is part of how we evaluate applicants.",
            km="សូមវាយសារជាអក្សរ។ យើងមិនទទួលសារសំឡេងសម្រាប់ការដាក់ពាក្យ។ "
               "នេះជាផ្នែកមួយនៃការវាយតម្លៃ។"
        ))
        return

    strike = session["voice_strike_count"] + 1
    _update(intake_id, voice_strike_count=strike)

    if strike == 1:
        _flag(intake_id, "voice_strike_1", "gap_medium")
        await update.message.reply_text(_t(lang,
            en="We already asked you to type. Please write your message. "
               "We want you to succeed — please follow the instruction.",
            km="យើងបានប្រាប់រួចហើយឲ្យវាយជាអក្សរ។ "
               "យើងចង់ឲ្យប្អូនជោគជ័យ — សូមអនុវត្តតាមការណែនាំ។"
        ))
    elif strike == 2:
        _flag(intake_id, "voice_strike_2", "gap_high")
        await update.message.reply_text(_t(lang,
            en="This is your second reminder. Please write your message — "
               "if you cannot do this, we cannot continue the application.",
            km="នេះជាការរំឭកទី ២ ។ សូមវាយជាអក្សរ — "
               "បើប្អូនមិនអាច យើងមិនអាចបន្តការដាក់ពាក្យ។"
        ))
    else:
        _update(intake_id, intake_status=S_BLOCKED, intake_blocked_reason="voice_refusal")
        _flag(intake_id, "intake_blocked_voice", "gap_high")
        await update.message.reply_text(_t(lang,
            en="Instructions were not followed. This application cannot continue.\n\n"
               "You are welcome to apply again in the future.",
            km="ការណែនាំមិនត្រូវបានអនុវត្ត។ ការដាក់ពាក្យនេះមិនអាចបន្ត។\n\n"
               "ប្អូនអាចដាក់ពាក្យម្តងទៀតនៅពេលអនាគត។"
        ))
        logger.info("intake blocked (voice) chat=%s", chat_id)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all intake: callback_data patterns."""
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "intake:fulltime:yes"
    chat_id = update.effective_chat.id
    session = get_intake_session(chat_id)

    if not session or session["intake_status"] not in ACTIVE_STATUSES:
        return

    intake_id = session["id"]
    lang = session["language"]
    parts = data.split(":")

    # intake:fulltime:yes / intake:fulltime:no
    if parts[1] == "fulltime" and len(parts) == 3:
        if parts[2] == "yes":
            _update(intake_id, intake_status=S_APPOINTMENT)
            await query.edit_message_text(_t(lang,
                en="Great. Please choose a time to come in for your interview:",
                km="ល្អណាស់។ សូមជ្រើសម៉ោងមកសម្ភាសន៍:"
            ), reply_markup=kb_appointment())
        else:
            _update(intake_id, intake_status=S_BLOCKED, intake_blocked_reason="part_time_request")
            _flag(intake_id, "requested_part_time", "gap_low")
            await query.edit_message_text(_t(lang,
                en="We only hire full-time staff (9 or 12-hour shifts). "
                   "Thank you for your time — please apply again if your schedule changes.",
                km="យើងជ្រើសរើសបុគ្គលិកពេញម៉ោងប៉ុណ្ណោះ (ម៉ោង ៩ ឬ ១២)។ "
                   "អរគុណ — ប្អូនអាចដាក់ពាក្យម្តងទៀតបើកាលវិភាគប្អូនផ្លាស់ប្ដូរ។"
            ))

    # intake:slot:YYYY-MM-DDTHH:00
    elif parts[1] == "slot" and len(parts) >= 3:
        slot_str = parts[2]  # "2026-05-28T14:00"
        try:
            slot_naive = datetime.strptime(slot_str, "%Y-%m-%dT%H:%M")
            slot_dt = slot_naive.replace(tzinfo=PP_TZ)
        except ValueError:
            logger.error("intake bad slot format: %s", slot_str)
            return
        _update(intake_id, intake_status=S_APPT_SET,
                appointment_slot=slot_dt,
                appointment_confirmed_at=datetime.now(PP_TZ))
        day_str = slot_dt.strftime("%-d %B")   # "28 May"
        time_str = slot_dt.strftime("%-I:%M %p")  # "2:00 PM"
        await query.edit_message_text(_t(lang,
            en=f"Confirmed. Please come to The Wine Bakery on {day_str} at {time_str}.\n\n"
               f"Please be on time. See you soon! 🙏",
            km=f"បានបញ្ជាក់។ សូមមក The Wine Bakery នៅថ្ងៃ {day_str} ម៉ោង {time_str}។\n\n"
               f"សូមមកទាន់ម៉ោង។ ជួបគ្នា! 🙏"
        ))
        await context.bot.send_location(chat_id, latitude=config.BAKERY_LAT,
                                        longitude=config.BAKERY_LNG)
        logger.info("intake slot set chat=%s slot=%s", chat_id, slot_dt)

    # intake:day:YYYY-MM-DD  → show times for that day
    elif parts[1] == "day" and len(parts) == 3:
        try:
            target = date.fromisoformat(parts[2])
        except ValueError:
            return
        day_label = target.strftime("%-d %B")
        await query.edit_message_text(_t(lang,
            en=f"Choose a time on {day_label}:",
            km=f"ជ្រើសម៉ោងនៅថ្ងៃ {day_label}:"
        ), reply_markup=kb_day_slots(target))

    # intake:pickday  → show 7-day picker
    elif parts[1] == "pickday":
        await query.edit_message_text(_t(lang,
            en="Choose a day:",
            km="ជ្រើសថ្ងៃ:"
        ), reply_markup=kb_pick_day())

    # intake:appt_back  → return to main appointment keyboard
    elif parts[1] == "appt_back":
        await query.edit_message_text(_t(lang,
            en="Please choose a time to come in for your interview:",
            km="សូមជ្រើសម៉ោងមកសម្ភាសន៍:"
        ), reply_markup=kb_appointment())

    # intake:arrived:ID  (listener staff taps — only valid from their chat)
    elif parts[1] == "arrived" and len(parts) == 3:
        if update.effective_user.id != config.HIRE_ARRIVAL_STAFF_ID:
            return
        await _confirm_arrival(int(parts[2]), context, query)

    # intake:noshow:ID  (listener staff taps)
    elif parts[1] == "noshow" and len(parts) == 3:
        if update.effective_user.id != config.HIRE_ARRIVAL_STAFF_ID:
            return
        await _confirm_noshow(int(parts[2]), context, query)


# ── State-specific handlers ───────────────────────────────────────────────────

async def _handle_language_check(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  session: dict) -> None:
    text = update.message.text or update.message.caption or ""
    intake_id = session["id"]
    lang = session["language"]

    if _is_khmer(text):
        if _implies_cant_english(text):
            # Graceful: they told us they can't do English
            _update(intake_id, language="km", intake_status=S_CV_PENDING)
            await update.message.reply_text(
                "យល់ហើយ! យើងនឹងប្រាស្រ័យជាភាសាខ្មែរ។\n\n"
                "សូមផ្ញើ CV ឬពណ៌នាប្រវត្តិការងាររបស់ប្អូន។"
            )
        else:
            # Replied in Khmer without explaining — ask once to try English
            _flag(intake_id, "language_mismatch_no_acknowledgment", "gap_low")
            await update.message.reply_text(
                "We are writing to you in English because English is useful for this role. "
                "Can you please reply in English?\n\n"
                "If you cannot, please let us know and we will switch to Khmer.\n\n"
                "———\n\n"
                "យើងសរសេរជាអង់គ្លេស ព្រោះអង់គ្លេសសំខាន់សម្រាប់ការងារ។ "
                "ប្អូនអាចតបជាអង់គ្លេសបានទេ?\n\n"
                "បើអត់, ប្រាប់យើង ហើយយើងនឹងប្ដូរជាខ្មែរ។"
            )
            # Move to CV pending anyway — if they reply Khmer again, we accept it
            _update(intake_id, intake_status=S_CV_PENDING)
    else:
        # English (or close enough) — move to CV
        _update(intake_id, intake_status=S_CV_PENDING)
        await update.message.reply_text(_t(lang,
            en="Thank you. Please send us your CV or describe your work experience.",
            km="អរគុណ។ សូមផ្ញើ CV ឬពណ៌នាប្រវត្តិការងាររបស់ប្អូន។"
        ))


async def _handle_cv_pending(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              session: dict) -> None:
    message = update.message
    text = message.text or message.caption or ""
    has_media = bool(message.document or message.photo)
    intake_id = session["id"]
    lang = session["language"]

    # Detect language switch (Khmer after English start)
    if lang == "en" and _is_khmer(text) and not has_media:
        if _implies_cant_english(text):
            _update(intake_id, language="km")
            lang = "km"
        else:
            _flag(intake_id, "continued_khmer_no_explanation", "gap_low")
            _update(intake_id, language="km")
            lang = "km"

    # Salary/schedule question before CV
    if _is_salary_schedule(text) and not has_media and not session["cv_submitted"]:
        _flag(intake_id, "asked_salary_or_schedule_before_cv", "gap_medium")
        await message.reply_text(_t(lang,
            en="Please send your CV or work history first. "
               "We discuss position, schedule, and salary when you come in — not before the application is complete.",
            km="សូមផ្ញើ CV ឬប្រវត្តិការងាររបស់ប្អូនជាមុន។ "
               "យើងនឹងពិភាក្សាអំពីតំណែង ម៉ោងធ្វើការ និងប្រាក់ខែ នៅពេលប្អូនមក — មិនមែនមុន។"
        ))
        return

    # Accept: document, photo, or descriptive text (>30 chars)
    if has_media or len(text) > 30:
        cv_format = "document" if message.document else ("photo" if message.photo else "text")
        _update(intake_id, cv_submitted=True, cv_format=cv_format,
                intake_status=S_FULLTIME_GATE)
        if cv_format == "text":
            _flag(intake_id, "cv_submitted_as_text", "gap_low")
        await message.reply_text(_t(lang,
            en="Thank you. We have received your application.\n\n"
               "We offer 9-hour or 12-hour shifts — 12 hours earns a higher salary, "
               "and we prefer staff who are fully committed to one workplace. "
               "We do not hire part-time.\n\n"
               "Can you commit to full-time work?",
            km="អរគុណ។ យើងបានទទួលពាក្យស្នើរបស់ប្អូន។\n\n"
               "យើងមានម៉ោង ៩ ឬ ១២ ម៉ោងក្នុងមួយថ្ងៃ — ១២ ម៉ោង ប្រាក់ខែខ្ពស់ជាង "
               "ហើយយើងចូលចិត្តបុគ្គលិកដែលលះបង់ពេញម៉ោងជាមួយយើង។ "
               "យើងមិនជ្រើសរើស part-time ទេ។\n\n"
               "ប្អូនអាចធ្វើការពេញម៉ោងបានទេ?"
        ), reply_markup=kb_fulltime(lang))
    else:
        # Too short / unclear — ask again
        _flag(intake_id, "cv_deflection", "gap_low")
        await message.reply_text(_t(lang,
            en="Please send your CV, or describe your work experience clearly "
               "(name, previous jobs, skills).",
            km="សូមផ្ញើ CV ឬពណ៌នាប្រវត្តិការងាររបស់ប្អូន (ឈ្មោះ ការងារមុន ជំនាញ)។"
        ))


async def _prompt_button(update: Update, session: dict) -> None:
    """User typed instead of tapping button — redirect."""
    lang = session["language"]
    await update.message.reply_text(_t(lang,
        en="Please use the buttons to answer.",
        km="សូមប្រើប៊ូតុងដើម្បីឆ្លើយ។"
    ))


async def _remind_slot(update: Update, session: dict) -> None:
    lang = session["language"]
    slot = session["appointment_slot"]
    if slot:
        slot_pp = slot.astimezone(PP_TZ)
        day_str = slot_pp.strftime("%-d %B")
        time_str = slot_pp.strftime("%-I:%M %p")
        await update.message.reply_text(_t(lang,
            en=f"Your interview is scheduled for {day_str} at {time_str} "
               f"at The Wine Bakery. We look forward to seeing you.",
            km=f"ការសម្ភាសន៍របស់ប្អូននៅថ្ងៃ {day_str} ម៉ោង {time_str} "
               f"នៅ The Wine Bakery។ យើងរង់ចាំជួបប្អូន។"
        ))


async def _resume_state(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        session: dict) -> None:
    """Re-send the appropriate prompt for the current stage."""
    status = session["intake_status"]
    lang = session["language"]

    if status == S_LANGUAGE_CHECK:
        await update.message.reply_text(_t(lang,
            en="Please tell us your name and what position you are interested in.",
            km="សូមប្រាប់ឈ្មោះ និងតំណែងដែលប្អូនចាប់អារម្មណ៍។"
        ))
    elif status == S_CV_PENDING:
        await update.message.reply_text(_t(lang,
            en="Please send your CV or describe your work experience.",
            km="សូមផ្ញើ CV ឬពណ៌នាប្រវត្តិការងារ។"
        ))
    elif status == S_FULLTIME_GATE:
        await update.message.reply_text(_t(lang,
            en="Can you commit to full-time work (9 or 12-hour shifts)?",
            km="ប្អូនអាចធ្វើការពេញម៉ោងបានទេ (ម៉ោង ៩ ឬ ១២)?"
        ), reply_markup=kb_fulltime(lang))
    elif status == S_APPOINTMENT:
        await update.message.reply_text(_t(lang,
            en="Please choose a time to come in for your interview:",
            km="សូមជ្រើសម៉ោងមកសម្ភាសន៍:"
        ), reply_markup=kb_appointment())
    elif status == S_APPT_SET:
        await _remind_slot(update, session)


# ── Arrival confirmation ──────────────────────────────────────────────────────

async def notify_owner_arrival(bot: Bot, intake_id: int, applicant_chat_id: int,
                               applicant_name: str, slot: datetime) -> None:
    """Send arrival confirmation button to the owner's private chat."""
    slot_pp = slot.astimezone(PP_TZ)
    slot_str = slot_pp.strftime("%-d %B %-I:%M %p")
    try:
        await bot.send_message(
            config.HIRE_ARRIVAL_STAFF_ID,
            f"📋 Applicant for interview:\n\n"
            f"Name: {applicant_name}\n"
            f"Scheduled: {slot_str}\n\n"
            f"Are they here?",
            reply_markup=kb_arrived(intake_id),
        )
    except TelegramError as e:
        logger.error("notify_owner_arrival failed: %s", e)


async def _confirm_arrival(intake_id: int, context: ContextTypes.DEFAULT_TYPE,
                           query) -> None:
    """Owner tapped [Arrived] — unlock the test."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT telegram_chat_id, sender_name, language
            FROM hiring_intake_sessions WHERE id = %s
        """, (intake_id,))
        row = cur.fetchone()
        if not row:
            await query.edit_message_text("Session not found.")
            return
        applicant_chat_id, applicant_name, lang = row

        cur.execute("""
            UPDATE hiring_intake_sessions
            SET intake_status = %s, arrived = true, updated_at = now()
            WHERE id = %s
        """, (S_TEST_UNLOCKED, intake_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    await query.edit_message_text(
        f"✅ {applicant_name} marked as arrived. Test unlocked."
    )

    # Create hiring_sessions entry and start quiz
    from hire_bot import sessions as quiz_sessions
    try:
        _token, session_id = quiz_sessions.create_session(
            candidate_name=applicant_name,
            created_by_staff_id=config.HIRE_ARRIVAL_STAFF_ID,
        )
        # Bind session to applicant's Telegram user
        conn2 = _conn()
        cur2 = conn2.cursor()
        try:
            # Get applicant's user_id from intake
            cur2.execute("SELECT telegram_user_id FROM hiring_intake_sessions WHERE id = %s",
                         (intake_id,))
            r = cur2.fetchone()
            if r:
                cur2.execute("""
                    UPDATE hiring_sessions
                    SET telegram_user_id = %s, status = 'active'
                    WHERE id = %s
                """, (r[0], session_id))
                conn2.commit()
        finally:
            cur2.close()
            conn2.close()
    except Exception as e:
        logger.error("confirm_arrival: failed to create quiz session: %s", e)
        await context.bot.send_message(
            applicant_chat_id,
            "We're ready for you. Please wait — staff will start the test shortly.",
        )
        return

    # Send the test intro directly to the applicant
    from hire_bot.bot import INTRO_EN, INTRO_KM, _kb_ready
    intro = INTRO_EN + "\n\n" + INTRO_KM
    await context.bot.send_message(applicant_chat_id, intro, reply_markup=_kb_ready())
    logger.info("intake test_unlocked chat=%s session=%s", applicant_chat_id, session_id)


async def _confirm_noshow(intake_id: int, context: ContextTypes.DEFAULT_TYPE,
                          query) -> None:
    """Owner tapped [Didn't come] — mark no-show."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE hiring_intake_sessions
            SET no_show = true, arrived = false, updated_at = now()
            WHERE id = %s
            RETURNING telegram_chat_id, sender_name, language
        """, (intake_id,))
        row = cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    if not row:
        await query.edit_message_text("Session not found.")
        return

    applicant_chat_id, applicant_name, lang = row
    _flag(intake_id, "no_show", "gap_high")

    await query.edit_message_text(f"❌ {applicant_name} marked as no-show.")
    try:
        await context.bot.send_message(
            applicant_chat_id,
            _t(lang,
               en="We didn't see you for your appointment. "
                  "If you'd like to reschedule, please message us again.",
               km="យើងមិនឃើញប្អូនមកសម្ភាសន៍។ "
                  "បើប្អូនចង់កំណត់ម៉ោងម្តងទៀត សូមផ្ញើសារមកយើង។"
            )
        )
    except TelegramError:
        pass
    logger.info("intake no-show chat=%s", applicant_chat_id)


# ── Day-of reminder job ───────────────────────────────────────────────────────

async def send_arrival_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job that runs every 10 minutes.
    Sends a location pin reminder to applicants whose slot is within 30 minutes.
    Also pings the owner to watch for the arrival.
    """
    pending = _get_pending_arrivals()
    for s in pending:
        chat_id = s["telegram_chat_id"]
        slot = s["appointment_slot"].astimezone(PP_TZ)
        time_str = slot.strftime("%-I:%M %p")
        lang = s["language"]
        try:
            await context.bot.send_message(
                chat_id,
                _t(lang,
                   en=f"Reminder: your interview is at {time_str} today at The Wine Bakery. "
                      f"Please head over now.",
                   km=f"រំឭក: ការសម្ភាសន៍របស់ប្អូននៅម៉ោង {time_str} ថ្ងៃនេះ "
                      f"នៅ The Wine Bakery។ សូមមកឥឡូវ។"
                )
            )
            await context.bot.send_location(chat_id, latitude=config.BAKERY_LAT,
                                            longitude=config.BAKERY_LNG)
            await notify_owner_arrival(
                context.bot, s["id"], chat_id,
                s["sender_name"] or "Applicant", s["appointment_slot"]
            )
            # Mark as notified by temporarily updating status (optional — prevents double-notify)
            # We don't change status here so owner can still tap buttons
        except TelegramError as e:
            logger.error("arrival reminder failed chat=%s: %s", chat_id, e)
