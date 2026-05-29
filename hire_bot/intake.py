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


_MEDIA_LIMIT = 10          # soft cap on CV files per applicant
_DEFLECT_AI_CHECK = 3      # Haiku deflection check fires after this many deflections
_DEFLECT_MAX = 5           # hard close after this many deflections regardless


def _store_media(intake_id: int, update) -> None:
    """Insert one row in hiring_intake_media for every photo/document received."""
    message = update.message
    chat_id = update.effective_chat.id
    user_id = getattr(update.effective_user, "id", None)

    file_id = file_unique_id = media_type = filename = mime_type = caption = None
    file_size = media_group_id = None
    caption = message.caption

    if message.photo:
        photo = message.photo[-1]
        file_id        = photo.file_id
        raw_unique     = getattr(photo, "file_unique_id", None)
        file_unique_id = raw_unique if isinstance(raw_unique, (str, type(None))) else None
        media_type     = "photo"
        raw_size       = getattr(photo, "file_size", None)
        file_size      = raw_size if isinstance(raw_size, (int, type(None))) else None
    elif message.document:
        doc            = message.document
        file_id        = doc.file_id
        raw_unique     = getattr(doc, "file_unique_id", None)
        file_unique_id = raw_unique if isinstance(raw_unique, (str, type(None))) else None
        media_type     = "document"
        raw_fn         = getattr(doc, "file_name", None)
        filename       = raw_fn if isinstance(raw_fn, (str, type(None))) else None
        raw_mime       = getattr(doc, "mime_type", None)
        mime_type      = raw_mime if isinstance(raw_mime, (str, type(None))) else None
        raw_size       = getattr(doc, "file_size", None)
        file_size      = raw_size if isinstance(raw_size, (int, type(None))) else None
    else:
        return

    raw_group_id  = getattr(message, "media_group_id", None)
    media_group_id = raw_group_id if isinstance(raw_group_id, (str, type(None))) else None
    raw_caption   = message.caption
    caption        = raw_caption if isinstance(raw_caption, (str, type(None))) else None

    conn = _conn(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_intake_media
                (intake_id, telegram_chat_id, telegram_user_id, telegram_message_id,
                 telegram_file_id, telegram_file_unique_id, media_group_id,
                 media_type, original_filename, mime_type, file_size, caption,
                 purpose, include_for_review, received_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'unknown', true, now())
            ON CONFLICT (intake_id, telegram_message_id) DO NOTHING
        """, (intake_id, chat_id, user_id, message.message_id,
              file_id, file_unique_id, media_group_id,
              media_type, filename, mime_type, file_size, caption))
        conn.commit()
    except Exception as exc:
        logger.error("_store_media failed intake_id=%s: %s", intake_id, exc)
        conn.rollback()
    finally:
        cur.close(); conn.close()


def get_intake_media_count(intake_id: int) -> int:
    conn = _conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM hiring_intake_media WHERE intake_id = %s", (intake_id,))
        return cur.fetchone()[0]
    finally:
        cur.close(); conn.close()


def get_intake_media(intake_id: int) -> list[dict]:
    conn = _conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, media_type, telegram_file_id, original_filename,
                   mime_type, purpose, received_at
            FROM hiring_intake_media WHERE intake_id = %s
            ORDER BY received_at
        """, (intake_id,))
        cols = ["id","media_type","file_id","filename","mime_type","purpose","received_at"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        cur.close(); conn.close()


def _log_ai_event(intake_id: int, stage: str, model: str, prompt_version: str,
                  input_text: str, output_json: dict,
                  intent: str | None, confidence: float | None,
                  action_taken: str) -> None:
    import json as _json
    conn = _conn(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hiring_intake_ai_events
                (intake_id, stage, model, prompt_version, input_text,
                 output_json, intent, confidence, action_taken, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        """, (intake_id, stage, model, prompt_version, input_text[:2000],
              _json.dumps(output_json), intent, confidence, action_taken))
        conn.commit()
    except Exception as exc:
        logger.warning("_log_ai_event failed: %s", exc)
        conn.rollback()
    finally:
        cur.close(); conn.close()


def _get_recent_deflection_messages(intake_id: int, limit: int = 5) -> list[str]:
    """Fetch the last N input_text values from ai_events for deflection context."""
    conn = _conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT input_text FROM hiring_intake_ai_events
            WHERE intake_id = %s AND stage = 'cv_extraction'
            ORDER BY created_at DESC LIMIT %s
        """, (intake_id, limit))
        rows = cur.fetchall()
        return [r[0] for r in reversed(rows)]
    finally:
        cur.close(); conn.close()


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


# ── Date/time format helpers (cross-platform, no %-d Linux flag) ─────────────

def _fmt_day(d) -> str:
    """'28 May'"""
    return f"{d.day} {d.strftime('%b')}"

def _fmt_day_long(d) -> str:
    """'28 May' using full month"""
    return f"{d.day} {d.strftime('%B')}"

def _fmt_time(dt) -> str:
    """'2:00 PM'"""
    h = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{h}:{dt.minute:02d} {ampm}"


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
    day_label = _fmt_day(target_date)
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
        label = _fmt_day(d)
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


def kb_media_done(lang: str) -> InlineKeyboardMarkup:
    label = (
        "✅ Done sending files  /  ផ្ញើរួចហើយ"
        if lang != "km" else
        "✅ ផ្ញើ CV រួចហើយ  /  Done sending files"
    )
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="intake:media_done")]])


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

    # Store every photo/document silently regardless of state — no AI, just reference.
    # cv_pending handles the media count + Done-button flow explicitly below.
    if update.message and (update.message.photo or update.message.document):
        if status not in (S_CV_PENDING,):  # cv_pending stores inside its handler
            _store_media(session["id"], update)

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

    # intake:media_done — applicant finished sending CV files
    if parts[1] == "media_done":
        if not session.get("cv_submitted"):
            await query.answer(_t(lang,
                en="Please send at least one file first.",
                km="សូមផ្ញើឯកសារមួយជាមុន។"
            ), show_alert=True)
            return
        _update(intake_id, intake_status=S_FULLTIME_GATE)
        count = get_intake_media_count(intake_id)
        await query.edit_message_text(_t(lang,
            en=f"Thank you — received {count} file{'s' if count != 1 else ''}. "
               "We have received your application.\n\n"
               "We offer 9-hour or 12-hour shifts — 12 hours earns a higher salary, "
               "and we prefer staff who are fully committed to one workplace. "
               "We do not hire part-time.\n\n"
               "Can you commit to full-time work?",
            km=f"អរគុណ — បានទទួល {count} ឯកសារ។ "
               "យើងបានទទួលពាក្យស្នើរបស់ប្អូន។\n\n"
               "យើងមានម៉ោង ៩ ឬ ១២ ម៉ោងក្នុងមួយថ្ងៃ — ១២ ម៉ោង ប្រាក់ខែខ្ពស់ជាង "
               "ហើយយើងចូលចិត្តបុគ្គលិកដែលលះបង់ពេញម៉ោងជាមួយយើង។ "
               "យើងមិនជ្រើសរើស part-time ទេ។\n\n"
               "ប្អូនអាចធ្វើការពេញម៉ោងបានទេ?"
        ), reply_markup=kb_fulltime(lang))
        logger.info("intake media_done chat=%s count=%s", chat_id, count)
        return

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
        slot_str = ":".join(parts[2:])  # rejoin — colon in time splits into extra parts
        try:
            slot_naive = datetime.strptime(slot_str, "%Y-%m-%dT%H:%M")
            slot_dt = slot_naive.replace(tzinfo=PP_TZ)
        except ValueError:
            logger.error("intake bad slot format: %s", slot_str)
            return
        _update(intake_id, intake_status=S_APPT_SET,
                appointment_slot=slot_dt,
                appointment_confirmed_at=datetime.now(PP_TZ))
        day_str  = _fmt_day_long(slot_dt)
        time_str = _fmt_time(slot_dt)
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
        day_label = _fmt_day_long(target)
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
    has_media = bool(update.message.document or update.message.photo)
    intake_id = session["id"]
    lang = session["language"]

    # Photo/document — they're applying; skip intent check, process as CV directly
    if has_media:
        _update(intake_id, intake_status=S_CV_PENDING)
        await _handle_cv_pending(update, context, dict(session, intake_status=S_CV_PENDING))
        return

    # ── Haiku intent classification ───────────────────────────────────────────
    from shared.ai_client import classify_intake_intent, _INTAKE_HAIKU, _INTENT_PROMPT_VERSION
    result = await classify_intake_intent(text)
    intent     = result["intent"]
    confidence = result["confidence"]
    ai_lang    = result["language"]

    _log_ai_event(intake_id, "intent_check", _INTAKE_HAIKU, _INTENT_PROMPT_VERSION,
                  text, result, intent, confidence, "")

    # Detect language from Haiku result (supplement existing rule-based detection)
    if ai_lang == "km" or _is_khmer(text):
        _update(intake_id, language="km")
        lang = "km"

    # ── Route by intent ───────────────────────────────────────────────────────
    if intent in ("clear_refusal", "wrong_number") and confidence >= 0.75:
        _update(intake_id, intake_status=S_BLOCKED,
                intake_blocked_reason=f"ai_{intent}")
        _flag(intake_id, f"ai_{intent}", "gap_low")
        _log_ai_event(intake_id, "intent_check", _INTAKE_HAIKU, _INTENT_PROMPT_VERSION,
                      text, result, intent, confidence, "close")
        await update.message.reply_text(_t(lang,
            en="Thank you for your message. We don't think you are looking for a job "
               "right now — if you change your mind, feel free to message us again.",
            km="អរគុណសម្រាប់សាររបស់ប្អូន។ ប្រសិនបើប្អូនចង់ដាក់ពាក្យនៅពេលណាមួយ "
               "សូមមកទំនាក់ទំនងយើងម្តងទៀត។"
        ))
        logger.info("intake closed by ai intent=%s conf=%.2f chat=%s", intent, confidence, intake_id)
        return

    if intent == "confused":
        _log_ai_event(intake_id, "intent_check", _INTAKE_HAIKU, _INTENT_PROMPT_VERSION,
                      text, result, intent, confidence, "reprompt")
        await update.message.reply_text(_t(lang,
            en="Please leave your CV here to apply for joining The Wine Bakery.\n\n"
               "សូមផ្ញើ CV របស់ប្អូន ដើម្បីដាក់ពាក្យចូលធ្វើការ The Wine Bakery។",
            km="សូមផ្ញើ CV របស់ប្អូន ដើម្បីដាក់ពាក្យចូលធ្វើការ The Wine Bakery។\n\n"
               "Please leave your CV here to apply for joining The Wine Bakery."
        ))
        return

    # intent == "applying" (or fallback from error) — move to CV step
    _log_ai_event(intake_id, "intent_check", _INTAKE_HAIKU, _INTENT_PROMPT_VERSION,
                  text, result, intent, confidence, "continue")
    _update(intake_id, intake_status=S_CV_PENDING)
    await update.message.reply_text(_t(lang,
        en="Please leave your CV here to apply for joining The Wine Bakery.\n\n"
           "You can send a photo, document, or describe your work experience in writing.\n\n"
           "———\n\n"
           "សូមផ្ញើ CV របស់ប្អូន ដើម្បីដាក់ពាក្យចូលធ្វើការ The Wine Bakery។\n\n"
           "ប្អូនអាចផ្ញើរូបភាព ឯកសារ ឬពណ៌នាប្រវត្តិការងាររបស់ប្អូនជាអក្សរ។",
        km="សូមផ្ញើ CV របស់ប្អូន ដើម្បីដាក់ពាក្យចូលធ្វើការ The Wine Bakery។\n\n"
           "ប្អូនអាចផ្ញើរូបភាព ឯកសារ ឬពណ៌នាប្រវត្តិការងាររបស់ប្អូនជាអក្សរ។\n\n"
           "———\n\n"
           "Please leave your CV here to apply for joining The Wine Bakery.\n\n"
           "You can send a photo, document, or describe your work experience in writing."
    ))


async def _handle_cv_pending(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              session: dict) -> None:
    message = update.message
    text = message.text or message.caption or ""
    has_media = bool(message.document or message.photo)
    intake_id = session["id"]
    lang = session["language"]

    # Language switch detection (text messages only)
    if lang == "en" and not has_media:
        if _is_khmer(text) or _implies_cant_english(text):
            _update(intake_id, language="km")
            lang = "km"
            if not _implies_cant_english(text) and _is_khmer(text):
                _flag(intake_id, "continued_khmer_no_explanation", "gap_low")

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

    # ── Multi-file media handling ─────────────────────────────────────────────
    if has_media:
        _store_media(intake_id, update)
        count = get_intake_media_count(intake_id)

        if count > _MEDIA_LIMIT:
            await message.reply_text(_t(lang,
                en="We have received enough documents for your application. "
                   "Please tap Done to continue.",
                km="យើងបានទទួលឯកសារគ្រប់គ្រាន់ហើយ។ "
                   "សូមចុច Done ដើម្បីបន្ត។"
            ), reply_markup=kb_media_done(lang))
            return

        if not session["cv_submitted"]:
            # First file — set primary reference, mark submitted, stay in cv_pending
            cv_format = "document" if message.document else "photo"
            cv_file_id = (message.document.file_id if message.document
                          else message.photo[-1].file_id)
            _update(intake_id, cv_submitted=True, cv_format=cv_format,
                    cv_file_id=cv_file_id, cv_message_id=message.message_id)
            await message.reply_text(_t(lang,
                en=f"✅ Received file 1.\n\n"
                   "You can send more CV pages, certificates, or work documents now.\n"
                   "When you are finished, tap Done.",
                km=f"✅ បានទទួលឯកសារទី ១។\n\n"
                   "ប្អូនអាចផ្ញើទំព័រ CV បន្ថែម វិញ្ញាបនបត្រ ឬឯកសារការងារផ្សេងៗ។\n"
                   "នៅពេលរួចហើយ សូមចុច Done។"
            ), reply_markup=kb_media_done(lang))
        else:
            # Subsequent file
            await message.reply_text(_t(lang,
                en=f"✅ Received file {count}. Send more or tap Done when finished.",
                km=f"✅ បានទទួលឯកសារទី {count}។ ផ្ញើបន្ថែម ឬចុច Done នៅពេលរួចហើយ។"
            ), reply_markup=kb_media_done(lang))
        return

    # ── Text: Haiku CV extraction ─────────────────────────────────────────────
    if text and text.strip():
        from shared.ai_client import (extract_cv_content, check_deflection_intent,
                                       _INTAKE_HAIKU, _CV_EXTRACT_PROMPT_VERSION,
                                       _DEFLECTION_PROMPT_VERSION)
        cv_result = await extract_cv_content(text)
        _log_ai_event(intake_id, "cv_extraction", _INTAKE_HAIKU, _CV_EXTRACT_PROMPT_VERSION,
                      text, cv_result, None, None, "")

        if cv_result["has_work_history"]:
            # Accept — move to fulltime gate
            _update(intake_id, cv_submitted=True, cv_format="text",
                    intake_status=S_FULLTIME_GATE)
            _flag(intake_id, "cv_submitted_as_text", "gap_low")
            _log_ai_event(intake_id, "cv_extraction", _INTAKE_HAIKU, _CV_EXTRACT_PROMPT_VERSION,
                          text, cv_result, "has_work_history", None, "continue")
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
            return

        # Not usable as CV — increment deflection counter
        new_count = (session.get("cv_deflection_count") or 0) + 1
        _update(intake_id, cv_deflection_count=new_count)
        _flag(intake_id, "cv_deflection", "gap_low")
        _log_ai_event(intake_id, "cv_extraction", _INTAKE_HAIKU, _CV_EXTRACT_PROMPT_VERSION,
                      text, cv_result, "no_work_history", None, f"deflect_{new_count}")

        # Hard close after max deflections
        if new_count >= _DEFLECT_MAX:
            _update(intake_id, intake_status=S_BLOCKED,
                    intake_blocked_reason="max_deflections")
            await message.reply_text(_t(lang,
                en="Thank you for your interest. We need your CV or work experience "
                   "to continue — please message us again when you are ready.",
                km="អរគុណ។ យើងត្រូវការ CV ឬប្រវត្តិការងាររបស់ប្អូន ដើម្បីបន្ត — "
                   "សូមទំនាក់ទំនងយើងម្តងទៀតនៅពេលប្អូនរួចរាល់។"
            ))
            return

        # After AI_CHECK deflections — ask Haiku: struggling or refusing?
        if new_count == _DEFLECT_AI_CHECK:
            recent_msgs = _get_recent_deflection_messages(intake_id, limit=5)
            deflect_result = await check_deflection_intent(recent_msgs)
            _log_ai_event(intake_id, "deflection_check", _INTAKE_HAIKU, _DEFLECTION_PROMPT_VERSION,
                          " | ".join(recent_msgs), deflect_result,
                          deflect_result.get("status"), deflect_result.get("confidence"),
                          "")
            if deflect_result["status"] == "refusing" and deflect_result["confidence"] >= 0.75:
                _update(intake_id, intake_status=S_BLOCKED,
                        intake_blocked_reason="ai_refusing")
                _log_ai_event(intake_id, "deflection_check", _INTAKE_HAIKU, _DEFLECTION_PROMPT_VERSION,
                              text, deflect_result, "refusing", deflect_result.get("confidence"),
                              "close")
                await message.reply_text(_t(lang,
                    en="Thank you for your time. If you decide to apply in the future, "
                       "feel free to message us again.",
                    km="អរគុណចំពោះពេលវេលារបស់ប្អូន។ បើប្អូនចង់ដាក់ពាក្យនៅពេលអនាគត "
                       "សូមមកទំនាក់ទំនងយើងម្តងទៀត។"
                ))
                return

    # Re-prompt (struggling, confused, or vague)
    count = session.get("cv_deflection_count") or 0
    if count >= 2:
        # More direct after repeated deflections
        await message.reply_text(_t(lang,
            en="Please send your CV as a photo or document, or write:\n"
               "• Your name\n• Your last job\n• How long you worked there",
            km="សូមផ្ញើ CV ជារូបភាព ឬឯកសារ ឬសរសេរ:\n"
               "• ឈ្មោះ\n• ការងារចុងក្រោយ\n• រយៈពេលធ្វើការ"
        ))
    else:
        await message.reply_text(_t(lang,
            en="Please send your CV, or describe your work experience "
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
        day_str  = _fmt_day_long(slot_pp)
        time_str = _fmt_time(slot_pp)
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
        if session.get("cv_submitted"):
            count = get_intake_media_count(session["id"])
            await update.message.reply_text(_t(lang,
                en=f"We have received {count} file{'s' if count != 1 else ''} so far. "
                   "Send more documents or tap Done when finished.",
                km=f"យើងបានទទួល {count} ឯកសារ។ "
                   "ផ្ញើឯកសារបន្ថែម ឬចុច Done នៅពេលរួចហើយ។"
            ), reply_markup=kb_media_done(lang))
        else:
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
    slot_str = f"{_fmt_day_long(slot_pp)} {_fmt_time(slot_pp)}"
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
        time_str = _fmt_time(slot)
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
