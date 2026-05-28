"""
Hiring bot — Telegram interview bot with disappearing questions.

Staff commands (in private chat with bot):
  /create [Full Name]   — generate a one-time invite link for a candidate
  /reopen [attempt_id]  — allow a second resume after staff review

Candidate flow (private chat only, via deep link):
  /start TOKEN          — verify token, show identity confirm
  [I confirm / ខ្ញុំបញ្ជាក់]   — open session, show intro block
  [Ready / ចូលបញ្ចប់]  — send first question
  Answer buttons / text  — record answer, delete both messages, send next
  ... all 111 questions ...
  Auto-grade → follow-ups (up to 5) → end screen
  Owner notified on completion.

Design rules:
  - Only accept answer for the currently expected question (computed from DB).
    Stale/duplicate callbacks are logged and ignored.
  - Message deletion is best-effort — bot never crashes on delete failure.
  - Resume: first abandon = free resume; second = staff reopen required.
  - All state transitions go through sessions.py with DB transactions.
"""

import json
import logging
import time
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError

import config
from hire_bot import sessions, questions
from hire_bot.followups import get_followups_for_triggers
from hire_bot.scorer import auto_grade

logger = logging.getLogger(__name__)

# ── Intro block text ──────────────────────────────────────────────────────────

INTRO_EN = (
    "Welcome to the TWB Staff Interview Test.\n\n"
    "Rules:\n"
    "1. Answer every question honestly — there are no trick questions.\n"
    "2. Each question disappears after you answer. This is normal.\n"
    "3. If you go inactive for 10 minutes, your session will pause.\n"
    "4. You may resume once. After that, you need staff approval.\n"
    "5. Do not share your answers with anyone during the test.\n\n"
    "Take your time. Read carefully before answering."
)

INTRO_KM = (
    "សូមស្វាគមន៍មកកាន់ការធ្វើតេស្តសម្ភាសន៍បុគ្គលិក TWB។\n\n"
    "ច្បាប់:\n"
    "១. ឆ្លើយគ្រប់សំណួរដោយស្មោះត្រង់ — គ្មានសំណួរបញ្ឆោតទេ។\n"
    "២. សំណួរនីមួយៗនឹងបាត់ក្រោយប្អូនឆ្លើយ។ នេះជារឿងធម្មតា។\n"
    "៣. បើប្អូនឈប់ឆ្លើយ ១០ នាទី វគ្គរបស់ប្អូននឹងផ្អាក។\n"
    "៤. ប្អូនអាចបន្តម្តង។ ក្រោយមក ប្អូនត្រូវការការអនុញ្ញាតពីបុគ្គលិក។\n"
    "៥. កុំចែករំលែកចម្លើយជាមួយនរណាម្នាក់ ក្នុងអំឡុងពេលធ្វើតេស្ត។\n\n"
    "ចំណាយពេល។ អានដោយយកចិត្តទុកដាក់ មុននឹងឆ្លើយ។"
)


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _kb_identity(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"Yes, I am {name}  /  បាទ/ចាស ខ្ញុំជា {name}", callback_data="id_ok"),
    ]])


def _kb_ready() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("I am ready to start  /  ខ្ញុំខ្លួនរួចរាល់", callback_data="start_quiz"),
    ]])


def _kb_yes_no(qid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes  /  បាទ/ចាស", callback_data=f"ans:{qid}:yes")],
        [InlineKeyboardButton("No  /  ទេ", callback_data=f"ans:{qid}:no")],
        [InlineKeyboardButton("Not sure  /  មិនច្បាស់", callback_data=f"ans:{qid}:not_sure")],
    ])


def _kb_single_choice(qid: str, opts: dict[str, str]) -> InlineKeyboardMarkup:
    rows = []
    for letter, text in sorted(opts.items()):
        label = f"{letter}. {text[:60]}{'…' if len(text) > 60 else ''}"
        rows.append([InlineKeyboardButton(label, callback_data=f"ans:{qid}:{letter}")])
    return InlineKeyboardMarkup(rows)


def _kb_ranking(qid: str, items: list[str], chosen: list[str]) -> InlineKeyboardMarkup:
    """Show remaining unchosen items as buttons. chosen = labels already placed."""
    rows = []
    for idx, item in enumerate(items):
        if item not in chosen:
            short = item[:55] + "…" if len(item) > 55 else item
            rows.append([InlineKeyboardButton(short, callback_data=f"rank:{qid}:{idx}")])
    return InlineKeyboardMarkup(rows)


def _kb_resume() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Continue where I left off  /  បន្តពីកន្លែងដែលខ្ញុំឈប់",
                             callback_data="do_resume"),
    ]])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _delete(msg) -> None:
    """Best-effort delete — never raises."""
    try:
        await msg.delete()
    except TelegramError:
        pass


async def _send_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                         attempt_id: int, qid: str) -> None:
    """Send the question for qid and schedule the inactivity timeout."""
    q = questions.get_question(qid)
    if not q:
        logger.error("_send_question: unknown question %s", qid)
        return

    progress = questions.get_progress(qid)
    section = questions.SECTION_LABEL.get(qid, "")
    header = f"[{progress}] {section}\n\n" if section else f"[{progress}]\n\n"

    text = header + q["en"]
    if q["km"]:
        text += "\n\n" + q["km"]

    answer_type = q["answer_type"]

    if answer_type == "yes_no_not_sure":
        kb = _kb_yes_no(qid)
        msg = await context.bot.send_message(chat_id, text, reply_markup=kb)

    elif answer_type == "single_choice":
        opts = questions.parse_b_options(q)
        kb = _kb_single_choice(qid, opts)
        msg = await context.bot.send_message(chat_id, text, reply_markup=kb)

    elif answer_type == "ranking":
        items = questions.parse_d1_items(q)
        context.user_data["d1_items"] = items
        context.user_data["d1_chosen"] = []
        kb = _kb_ranking(qid, items, [])
        rank_header = (
            "Tap items IN ORDER — tap what to do FIRST, then second, etc.\n"
            "ចុចធាតុតាមលំដាប់ — ចុចអ្វីត្រូវធ្វើជាដំបូង បន្ទាប់មកទីពីរ ។ល។\n\n"
        )
        msg = await context.bot.send_message(chat_id, rank_header + text, reply_markup=kb)

    else:
        # free_text, rewrite — no buttons
        instruction = (
            "\n\n✍️ Type your answer below.\n"
            "វាយចម្លើយរបស់ប្អូនខាងក្រោម។"
        )
        msg = await context.bot.send_message(chat_id, text + instruction)

    # Store message ID for best-effort deletion on next answer
    context.user_data["last_q_msg_id"] = msg.message_id
    context.user_data["current_qid"] = qid

    # Schedule 10-minute inactivity timeout
    _schedule_timeout(context, chat_id, attempt_id, qid)


def _schedule_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                      attempt_id: int, qid: str) -> None:
    """Cancel any existing timeout, then schedule a new one."""
    job_name = f"timeout_{chat_id}"
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()

    session_id = context.user_data.get("session_id")
    context.job_queue.run_once(
        _timeout_callback,
        sessions.INACTIVITY_TIMEOUT_SECONDS,
        name=job_name,
        data={"chat_id": chat_id, "attempt_id": attempt_id,
              "session_id": session_id, "qid": qid},
    )


def _cancel_timeout(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    for job in context.job_queue.get_jobs_by_name(f"timeout_{chat_id}"):
        job.schedule_removal()


async def _timeout_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    chat_id = data["chat_id"]
    attempt_id = data["attempt_id"]
    session_id = data["session_id"]
    qid = data["qid"]

    try:
        sessions.mark_abandoned(attempt_id, session_id, qid)
    except Exception as e:
        logger.error("timeout mark_abandoned failed: %s", e)

    try:
        await context.bot.send_message(
            chat_id,
            "Your session has paused due to inactivity.\n"
            "វគ្គរបស់ប្អូនបានផ្អាក ដោយសារគ្មានសកម្មភាព។\n\n"
            "Use your original invite link to continue.\n"
            "ប្រើតំណផ្ញើអញ្ជើញដើមរបស់ប្អូន ដើម្បីបន្ត។"
        )
    except TelegramError:
        pass


# ── End of quiz ───────────────────────────────────────────────────────────────

async def _finish_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                       session_id: int, attempt_id: int) -> None:
    """Run auto_grade, select follow-ups, or go straight to end screen."""
    _cancel_timeout(context, chat_id)

    try:
        result = auto_grade(attempt_id)
    except Exception as e:
        logger.error("auto_grade failed for attempt %s: %s", attempt_id, e)
        await _end_screen(context, chat_id, session_id, attempt_id)
        return

    triggers = result.get("triggers", [])
    followups = get_followups_for_triggers(triggers)

    if followups:
        context.user_data["followup_queue"] = followups
        context.user_data["followup_index"] = 0
        await _send_followup(context, chat_id, attempt_id)
    else:
        await _end_screen(context, chat_id, session_id, attempt_id)


async def _send_followup(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                          attempt_id: int) -> None:
    queue = context.user_data.get("followup_queue", [])
    idx = context.user_data.get("followup_index", 0)

    if idx >= len(queue):
        session_id = context.user_data.get("session_id")
        await _end_screen(context, chat_id, session_id, attempt_id)
        return

    fu = queue[idx]
    total = len(queue)
    header = f"[Follow-up {idx + 1}/{total}]\n\n"
    text = header + fu["en"] + "\n\n" + fu["km"]

    # Follow-ups are always free-text (candidate types their answer)
    context.user_data["in_followup"] = True
    context.user_data["current_followup_callback"] = fu["callback"]

    instruction = "\n\n✍️ Type your answer below.\nវាយចម្លើយរបស់ប្អូនខាងក្រោម។"
    msg = await context.bot.send_message(chat_id, text + instruction)
    context.user_data["last_q_msg_id"] = msg.message_id


async def _end_screen(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                       session_id: int, attempt_id: int) -> None:
    try:
        sessions.complete_session(session_id, attempt_id)
    except Exception as e:
        logger.error("complete_session failed: %s", e)

    context.user_data.clear()

    await context.bot.send_message(
        chat_id,
        "Thank you. Your test is complete.\n"
        "អរគុណ។ ការធ្វើតេស្តរបស់ប្អូនបានបញ្ចប់។\n\n"
        "The management team will review your answers and contact you soon.\n"
        "ក្រុមការងារនឹងពិនិត្យមើលចម្លើយរបស់ប្អូន ហើយទាក់ទងប្អូនក្នុងពេលឆាប់ៗ។\n\n"
        "This chat is now closed.\n"
        "ការជជែករបស់ប្អូនបានបិទហើយ។"
    )

    # Notify owner
    try:
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"✅ Candidate completed interview test.\n"
            f"Attempt ID: {attempt_id} | Session: {session_id}\n"
            f"Run auto_grade + draft_rubric_scores to score."
        )
    except TelegramError as e:
        logger.error("owner notification failed: %s", e)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point — either staff command or candidate deep link."""
    if update.message.chat.type != "private":
        return

    args = context.args
    user = update.effective_user
    chat_id = update.effective_chat.id

    # No token → check for active session (bot restart recovery)
    if not args:
        sess = sessions.get_active_session(user.id)
        if sess and sess.get("attempt_id"):
            answered = sessions.get_answered_question_ids(sess["attempt_id"])
            next_qid = questions.get_next_question_id(answered)
            if next_qid:
                context.user_data["session_id"] = sess["session_id"]
                context.user_data["attempt_id"] = sess["attempt_id"]
                name = sess["candidate_name"]
                await update.message.reply_text(
                    f"Welcome back, {name}.\nសូមស្វាគមន៍មកវិញ {name}។\n\n"
                    "Continuing from where you left off.\nបន្តពីកន្លែងដែលប្អូនឈប់។",
                    reply_markup=_kb_resume()
                )
                return
        await update.message.reply_text(
            "Please use your invite link to start the test.\n"
            "សូមប្រើតំណផ្ញើអញ្ជើញ ដើម្បីចាប់ផ្តើមធ្វើតេស្ត។"
        )
        return

    token = args[0]
    sess_data = sessions.get_session_by_token(token)

    if not sess_data:
        await update.message.reply_text(
            "This invite link is not valid or has expired.\n"
            "តំណនេះមិនត្រឹមត្រូវ ឬបានផុតកំណត់ហើយ។"
        )
        return

    status = sess_data["status"]
    if status == "completed":
        await update.message.reply_text(
            "This test has already been completed.\n"
            "ការធ្វើតេស្តនេះបានបញ្ចប់ហើយ។"
        )
        return
    if status in ("cancelled", "expired"):
        await update.message.reply_text(
            "This invite link is no longer active.\n"
            "តំណផ្ញើអញ្ជើញនេះលែងដំណើរការហើយ។"
        )
        return

    bound_uid = sess_data.get("bound_telegram_user_id")
    if bound_uid and bound_uid != user.id:
        await update.message.reply_text(
            "This invite link was used by a different account.\n"
            "Please contact management.\n"
            "តំណនេះត្រូវបានប្រើដោយគណនីផ្សេង។ សូមទាក់ទងការគ្រប់គ្រង។"
        )
        return

    # Store token-derived session ID for the confirm button
    context.user_data["pending_session_id"] = sess_data["session_id"]
    name = sess_data["candidate_name"]

    await update.message.reply_text(
        f"Hello. This interview is for: {name}\n"
        f"សួស្តី។ ការសម្ភាសន៍នេះសម្រាប់: {name}\n\n"
        "Are you this person?\n"
        "តើប្អូនជាមនុស្សនេះទេ?",
        reply_markup=_kb_identity(name)
    )


async def cb_identity_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Candidate confirms identity → open session, show intro."""
    query = update.callback_query
    await query.answer()

    session_id = context.user_data.get("pending_session_id")
    if not session_id:
        await query.edit_message_text("Session expired. Please use your invite link again.\n"
                                      "វគ្គផុតកំណត់។ សូមប្រើតំណម្តងទៀត។")
        return

    user = update.effective_user
    try:
        attempt_id, is_resume = sessions.open_session(
            session_id, user.id, user.username)
    except ValueError as e:
        error_map = {
            "session_expired": "Your invite link has expired. Please contact management.\n"
                               "តំណផ្ញើអញ្ជើញផុតកំណត់ហើយ។ សូមទាក់ទងការគ្រប់គ្រង។",
            "session_completed": "This test has already been completed.\n"
                                 "ការធ្វើតេស្តបានបញ្ចប់ហើយ។",
            "session_cancelled": "This invite has been cancelled. Contact management.\n"
                                 "ការផ្ញើអញ្ជើញត្រូវបានលុបចោល។ ទាក់ទងការគ្រប់គ្រង។",
            "token_already_used": "This link was used from a different Telegram account.\n"
                                  "Contact management.\n"
                                  "តំណនេះត្រូវបានប្រើពីគណនី Telegram ផ្សេង។",
            "resume_needs_staff": "You need staff approval to continue.\n"
                                  "Please contact management to reopen your session.\n"
                                  "ប្អូនត្រូវការការអនុញ្ញាតពីបុគ្គលិក ដើម្បីបន្ត។\n"
                                  "សូមទាក់ទងការគ្រប់គ្រងដើម្បីបើកវគ្គម្តងទៀត។",
        }
        msg = error_map.get(str(e), "Something went wrong. Contact management.\n"
                             "មានអ្វីមួយខុស។ ទាក់ទងការគ្រប់គ្រង។")
        await query.edit_message_text(msg)
        return

    context.user_data["session_id"] = session_id
    context.user_data["attempt_id"] = attempt_id
    context.user_data.pop("pending_session_id", None)

    if is_resume:
        answered = sessions.get_answered_question_ids(attempt_id)
        next_qid = questions.get_next_question_id(answered)
        count = len(answered)
        await query.edit_message_text(
            f"Welcome back. You have answered {count} questions so far.\n"
            f"សូមស្វាគមន៍មកវិញ។ ប្អូនបានឆ្លើយ {count} សំណួររួចហើយ។",
            reply_markup=_kb_ready()
        )
    else:
        await query.edit_message_text(
            INTRO_EN + "\n\n───\n\n" + INTRO_KM,
            reply_markup=_kb_ready()
        )


async def cb_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume from bot-restart recovery (candidate tapped /start with no token)."""
    query = update.callback_query
    await query.answer()
    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        await query.edit_message_text("Session not found. Please use your invite link.\n"
                                      "រកមិនឃើញវគ្គ។ សូមប្រើតំណផ្ញើអញ្ជើញ។")
        return
    await query.edit_message_text("Continuing…\nកំពុងបន្ត…")
    answered = sessions.get_answered_question_ids(attempt_id)
    next_qid = questions.get_next_question_id(answered)
    if next_qid:
        await _send_question(context, update.effective_chat.id, attempt_id, next_qid)
    else:
        session_id = context.user_data.get("session_id")
        await _finish_quiz(context, update.effective_chat.id, session_id, attempt_id)


async def cb_start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Candidate taps 'I am ready' — send first question."""
    query = update.callback_query
    await query.answer()
    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        await query.edit_message_text("Session not found. Please use your invite link.\n"
                                      "រកមិនឃើញវគ្គ។ សូមប្រើតំណផ្ញើអញ្ជើញ។")
        return
    await _delete(query.message)
    answered = sessions.get_answered_question_ids(attempt_id)
    next_qid = questions.get_next_question_id(answered)
    if next_qid:
        await _send_question(context, update.effective_chat.id, attempt_id, next_qid)
    else:
        session_id = context.user_data.get("session_id")
        await _finish_quiz(context, update.effective_chat.id, session_id, attempt_id)


async def cb_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle yes/no/not_sure and single-choice callbacks.
    Format: ans:QUESTION_ID:VALUE
    Validates that this callback is for the currently expected question.
    """
    query = update.callback_query
    _, qid, value = query.data.split(":", 2)

    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        await query.answer("Session not found. Use your invite link.")
        return

    # Validate: is this callback for the expected question?
    answered = sessions.get_answered_question_ids(attempt_id)
    expected = questions.get_next_question_id(answered)
    if qid != expected:
        logger.info("cb_answer: stale callback qid=%s expected=%s attempt=%s",
                    qid, expected, attempt_id)
        await query.answer()  # Silently ignore stale/duplicate click
        return

    await query.answer()

    # Delete question message (best-effort)
    await _delete(query.message)

    # Record answer
    sessions.record_answer(attempt_id, qid, {"answer": value})
    _cancel_timeout(context, update.effective_chat.id)

    # Advance
    answered.add(qid)
    next_qid = questions.get_next_question_id(answered)
    if next_qid:
        await _send_question(context, update.effective_chat.id, attempt_id, next_qid)
    else:
        session_id = context.user_data.get("session_id")
        await _finish_quiz(context, update.effective_chat.id, session_id, attempt_id)


async def cb_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle D1 ranking button taps.
    Format: rank:QUESTION_ID:ITEM_INDEX
    """
    query = update.callback_query
    _, qid, idx_str = query.data.split(":", 2)
    item_idx = int(idx_str)

    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        await query.answer("Session not found.")
        return

    # Validate this is the expected question
    answered = sessions.get_answered_question_ids(attempt_id)
    expected = questions.get_next_question_id(answered)
    if qid != expected:
        await query.answer()
        return

    await query.answer()

    items = context.user_data.get("d1_items") or []
    if not items:
        q = questions.get_question(qid)
        items = questions.parse_d1_items(q) if q else []
        context.user_data["d1_items"] = items

    if item_idx >= len(items):
        return

    chosen_labels = context.user_data.get("d1_chosen", [])
    new_label = items[item_idx]

    if new_label in chosen_labels:
        await query.answer("Already chosen.")
        return

    chosen_labels.append(new_label)
    context.user_data["d1_chosen"] = chosen_labels

    # Save partial state to DB
    sessions.upsert_partial_ranking(attempt_id, qid, chosen_labels)

    if len(chosen_labels) == 7:
        # All 7 ranked — finalize
        await _delete(query.message)
        _cancel_timeout(context, update.effective_chat.id)
        answered.add(qid)
        next_qid = questions.get_next_question_id(answered)
        if next_qid:
            await _send_question(context, update.effective_chat.id, attempt_id, next_qid)
        else:
            session_id = context.user_data.get("session_id")
            await _finish_quiz(context, update.effective_chat.id, session_id, attempt_id)
    else:
        # Update keyboard — remove chosen item
        q = questions.get_question(qid)
        progress_text = f"Ranked so far / ជ្រើសរើសរួចហើយ:\n"
        for i, label in enumerate(chosen_labels, 1):
            progress_text += f"  {i}. {label}\n"

        kb = _kb_ranking(qid, items, chosen_labels)
        try:
            await query.edit_message_reply_markup(reply_markup=kb)
        except TelegramError:
            pass
        # Send progress update as separate message (best-effort)
        try:
            await context.bot.send_message(update.effective_chat.id, progress_text)
        except TelegramError:
            pass


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle free-text answers (Part C, D2, D3, D4, D-Final, and follow-ups).
    Only processes if the current expected question accepts free text.
    """
    if update.message.chat.type != "private":
        return

    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        return  # No active session — ignore

    user_text = update.message.text.strip()
    if not user_text:
        return

    chat_id = update.effective_chat.id

    # Follow-up answer?
    if context.user_data.get("in_followup"):
        callback_key = context.user_data.get("current_followup_callback", "unknown")

        # Delete question + answer messages (best-effort)
        last_q = context.user_data.get("last_q_msg_id")
        if last_q:
            try:
                await context.bot.delete_message(chat_id, last_q)
            except TelegramError:
                pass
        await _delete(update.message)

        sessions.store_followup_answer(attempt_id, callback_key, user_text)

        context.user_data["in_followup"] = False
        context.user_data["followup_index"] = context.user_data.get("followup_index", 0) + 1
        await _send_followup(context, chat_id, attempt_id)
        return

    # Main quiz free-text answer
    answered = sessions.get_answered_question_ids(attempt_id)
    expected = questions.get_next_question_id(answered)
    if not expected:
        return

    q = questions.get_question(expected)
    if not q or q["answer_type"] not in ("free_text", "rewrite"):
        return  # Not expecting text right now — ignore

    # Delete question + answer (best-effort)
    last_q = context.user_data.get("last_q_msg_id")
    if last_q:
        try:
            await context.bot.delete_message(chat_id, last_q)
        except TelegramError:
            pass
    await _delete(update.message)

    sessions.record_answer(attempt_id, expected, {"text": user_text})
    _cancel_timeout(context, chat_id)

    answered.add(expected)
    next_qid = questions.get_next_question_id(answered)
    if next_qid:
        await _send_question(context, chat_id, attempt_id, next_qid)
    else:
        session_id = context.user_data.get("session_id")
        await _finish_quiz(context, chat_id, session_id, attempt_id)


# ── Staff commands ────────────────────────────────────────────────────────────

async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /create Full Name  — generate a one-time invite link for a candidate.
    Must be used in private chat with the bot.
    """
    if update.message.chat.type != "private":
        await update.message.reply_text("Use this command in a private chat with me.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /create Full Name\n"
            "Example: /create Sokha Chan"
        )
        return

    name = " ".join(context.args)
    staff_id = update.effective_user.id

    try:
        token, session_id = sessions.create_session(name, staff_id)
    except Exception as e:
        logger.error("cmd_create failed: %s", e)
        await update.message.reply_text(f"Failed to create session: {e}")
        return

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start={token}"

    await update.message.reply_text(
        f"✅ Session created for: {name}\n"
        f"Session ID: {session_id}\n\n"
        f"Send this link to the candidate (link expires in 2 hours):\n"
        f"{deep_link}\n\n"
        f"⚠️ This message will not be repeated — copy the link now."
    )
    logger.info("cmd_create: session=%s name=%s created_by=%s", session_id, name, staff_id)


async def cmd_reopen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reopen ATTEMPT_ID — allow a second resume after staff review."""
    if update.message.chat.type != "private":
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /reopen ATTEMPT_ID")
        return

    attempt_id = int(context.args[0])
    staff_name = update.effective_user.full_name or str(update.effective_user.id)

    try:
        sessions.reopen_by_staff(attempt_id, staff_name)
        await update.message.reply_text(
            f"✅ Attempt {attempt_id} reopened. "
            f"Candidate can now use their invite link to continue."
        )
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")


# ── Application builder ───────────────────────────────────────────────────────

def build_application(token: str) -> Application:
    questions.load_all_questions()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("create", cmd_create))
    app.add_handler(CommandHandler("reopen", cmd_reopen))

    app.add_handler(CallbackQueryHandler(cb_identity_ok, pattern="^id_ok$"))
    app.add_handler(CallbackQueryHandler(cb_start_quiz, pattern="^start_quiz$"))
    app.add_handler(CallbackQueryHandler(cb_resume, pattern="^do_resume$"))
    app.add_handler(CallbackQueryHandler(cb_ranking, pattern="^rank:"))
    app.add_handler(CallbackQueryHandler(cb_answer, pattern="^ans:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
