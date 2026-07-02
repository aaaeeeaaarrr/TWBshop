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
from hire_bot import sessions, questions, intake, correction_flow, offer_flow
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

    await _notify_owner_quiz(context.bot, chat_id, attempt_id, outcome="abandoned")


# ── End of quiz ───────────────────────────────────────────────────────────────

async def _send_part_e_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                attempt_id: int, qid: str) -> None:
    """Send a Part E question. Uses same rendering as main quiz questions."""
    q = questions.get_question(qid)
    if not q:
        logger.error("_send_part_e_question: unknown question %s", qid)
        return

    triggered = context.user_data.get("part_e_triggered", [])
    progress = questions.get_part_e_progress(qid, triggered)
    section = questions.SECTION_LABEL.get(qid, "Part E — Hiring Facts")
    header = f"[{progress}] {section}\n\n"

    text = header + q["en"]
    if q["km"]:
        text += "\n\n" + q["km"]

    answer_type = q["answer_type"]
    if answer_type == "single_choice":
        opts = questions.parse_b_options(q)
        kb = _kb_single_choice(qid, opts)
        msg = await context.bot.send_message(chat_id, text, reply_markup=kb)
    else:
        instruction = "\n\n✍️ Type your answer below.\nវាយចម្លើយរបស់ប្អូនខាងក្រោម។"
        msg = await context.bot.send_message(chat_id, text + instruction)

    context.user_data["last_q_msg_id"] = msg.message_id
    context.user_data["current_qid"] = qid
    _schedule_timeout(context, chat_id, attempt_id, qid)


async def _advance_part_e(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                          session_id: int, attempt_id: int, just_answered: str) -> None:
    """Called after recording a Part E answer. Compute triggers after E-A5, then advance."""
    e_answered: set = context.user_data.get("part_e_answered", set())
    e_answered.add(just_answered)
    context.user_data["part_e_answered"] = e_answered

    # Evaluate triggers once — after the last always-asked question so all inputs are
    # available. Store in DB so a restart can reload without re-evaluating.
    if just_answered == questions.PART_E_ALWAYS[-1] and context.user_data.get("part_e_triggered") is None:
        triggered = questions.evaluate_e_triggers(attempt_id)
        context.user_data["part_e_triggered"] = triggered
        sessions.store_part_e_triggers(attempt_id, triggered)
        logger.info("_advance_part_e: triggers=%s attempt=%s", triggered, attempt_id)

    triggered = context.user_data.get("part_e_triggered") or []
    next_qid = questions.get_next_part_e_question(e_answered, triggered)

    if next_qid:
        await _send_part_e_question(context, chat_id, attempt_id, next_qid)
    else:
        await _finish_quiz(context, chat_id, session_id, attempt_id)


async def _enter_part_e(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                        attempt_id: int, session_id: int) -> None:
    """Transition from main quiz to Part E. Only called when Part E has not started."""
    context.user_data["in_part_e"] = True
    context.user_data["part_e_answered"] = set()
    context.user_data["part_e_triggered"] = None  # None = not yet evaluated (evaluated after E-A5)

    await context.bot.send_message(
        chat_id,
        "Almost done.\n"
        "ជិតបញ្ចប់ហើយ។\n\n"
        "A few short questions about your schedule and availability.\n"
        "សំណួរខ្លីៗចំនួនមួយចំនួនអំពីកាលវិភាគ និងភាពអាចប្រើប្រាស់របស់ប្អូន។"
    )

    first_qid = questions.get_next_part_e_question(set(), [])
    if first_qid:
        await _send_part_e_question(context, chat_id, attempt_id, first_qid)
    else:
        await _finish_quiz(context, chat_id, session_id, attempt_id)


async def _after_main_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                           session_id: int, attempt_id: int) -> None:
    """
    Called when all 111 main quiz questions are answered.
    Checks DB for any Part E answers already recorded — handles bot restart / resume
    without relying on in-memory user_data.
    """
    e_answered = sessions.get_answered_part_e_ids(attempt_id)

    if e_answered:
        # Part E already started (even if bot restarted and user_data was cleared)
        context.user_data["in_part_e"] = True
        context.user_data["part_e_answered"] = e_answered

        # Load triggers from DB; recompute if E-A5 was answered but triggers not stored yet
        triggered = sessions.load_part_e_triggers(attempt_id)
        if triggered is None and questions.PART_E_ALWAYS[-1] in e_answered:
            triggered = questions.evaluate_e_triggers(attempt_id)
            sessions.store_part_e_triggers(attempt_id, triggered)
        context.user_data["part_e_triggered"] = triggered  # may still be None if E-A5 not reached

        triggered_for_seq = triggered or []
        next_qid = questions.get_next_part_e_question(e_answered, triggered_for_seq)
        if next_qid:
            await _send_part_e_question(context, chat_id, attempt_id, next_qid)
        else:
            await _finish_quiz(context, chat_id, session_id, attempt_id)
    else:
        await _enter_part_e(context, chat_id, attempt_id, session_id)


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


async def _notify_owner_quiz(bot, chat_id: int, attempt_id: int,
                             outcome: str = "completed") -> None:
    """
    Send owner a private message with full quiz outcome, scores, Part E, pros/cons.
    Idempotent: sends once per outcome per attempt. HTML-safe: escapes all user text.
    """
    import html
    import json as _json
    import psycopg2
    from shared.database import raw_connect

    try:
        conn = raw_connect()
        cur  = conn.cursor()

        # Idempotency check
        cur.execute("""
            SELECT quiz_owner_notified_at, quiz_owner_notified_outcome
            FROM hiring_quiz_attempts WHERE id = %s
        """, (attempt_id,))
        idem = cur.fetchone()
        if idem and idem[0] and idem[1] == outcome:
            conn.close()
            return

        # Attempt + candidate info
        cur.execute("""
            SELECT a.attempt_status, a.score_summary, a.risk_profile,
                   a.abandoned_at_question_id, a.part_e_triggered, a.resume_count,
                   c.name, c.position,
                   s.telegram_username, s.telegram_user_id
            FROM hiring_quiz_attempts a
            JOIN hiring_sessions s ON s.id = a.session_id
            JOIN hiring_candidates c ON c.id = a.candidate_id
            WHERE a.id = %s
        """, (attempt_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return
        (attempt_status, score_summary_raw, risk_profile_raw,
         abandoned_qid, part_e_triggered_raw, resume_count,
         cand_name, position,
         tg_username, tg_user_id) = row

        score_summary    = score_summary_raw if isinstance(score_summary_raw, dict) else (_json.loads(score_summary_raw) if score_summary_raw else {})
        risk_profile     = risk_profile_raw if isinstance(risk_profile_raw, dict) else (_json.loads(risk_profile_raw) if risk_profile_raw else {})
        part_e_triggered = part_e_triggered_raw or []

        # Part E answers
        cur.execute("""
            SELECT question_id, raw_answer FROM hiring_quiz_answers
            WHERE attempt_id = %s AND question_id LIKE 'E-%%'
            ORDER BY question_id
        """, (attempt_id,))
        part_e_answers = {r[0]: r[1] for r in cur.fetchall()}

        conn.close()
        # (notified_at marked AFTER successful send — see below)

        # Safe HTML
        def esc(v): return html.escape(str(v)) if v else ""

        if tg_username:
            user_ref = f"@{esc(tg_username)}"
        elif tg_user_id:
            user_ref = f'<a href="tg://user?id={tg_user_id}">{esc(cand_name)}</a>'
        else:
            user_ref = esc(cand_name)

        icon        = "✅" if outcome == "completed" else "⚠️"
        abandoned   = f" — abandoned at {esc(abandoned_qid)}" if abandoned_qid else ""
        resume_note = f" (resumed {resume_count}×)" if resume_count else ""

        lines = [
            f"{icon} <b>Quiz {outcome.title()}</b> — {user_ref}",
            f"Candidate: {esc(cand_name)} | Position: {esc(position or '?')}",
            f"Attempt #{attempt_id}{resume_note}{abandoned}",
            "",
        ]

        # Scores
        if score_summary:
            a  = score_summary.get("score_a",    score_summary.get("a_pct",   "?"))
            b  = score_summary.get("score_b",    score_summary.get("b_pct",   "?"))
            w  = score_summary.get("written_pct", "?")
            ov = score_summary.get("overall_pct", score_summary.get("overall", "?"))
            lines += [f"📊 <b>Scores:</b> A={a}% B={b}% Written={w}% Overall={ov}%", ""]

        # Risk profile pros/cons
        if risk_profile:
            pros  = risk_profile.get("strengths", risk_profile.get("pros", []))
            cons  = risk_profile.get("red_flags", risk_profile.get("cons", []))
            flags = risk_profile.get("flags", [])
            if pros:
                lines.append("✅ <b>Pros:</b>")
                for p in (pros if isinstance(pros, list) else [pros])[:4]:
                    lines.append(f"  • {esc(p)}")
            if cons or flags:
                lines.append("⚠️ <b>Flags / Cons:</b>")
                for c in ((cons or []) + (flags or []))[:4]:
                    lines.append(f"  • {esc(c)}")
            lines.append("")

        # Part E — corrected labels matching questions.py
        def _pe(qid, label):
            ans = part_e_answers.get(qid)
            if ans:
                try:
                    raw = _json.loads(ans)
                    val = raw.get("answer", ans) if isinstance(raw, dict) else ans
                except Exception:
                    val = ans
                lines.append(f"  • {label}: {esc(val)}")

        if part_e_answers or part_e_triggered:
            lines.append("📋 <b>Part E — Practical facts:</b>")
            _pe("E-A1a", "Can start within 3 days?")
            _pe("E-A1",  "First available start date")
            _pe("E-A2",  "30-day availability")
            _pe("E-A3a", "Currently studying?")
            if "E-T1" in part_e_triggered:
                _pe("E-T1", "Study / exam details")
            _pe("E-A3b", "Currently working elsewhere?")
            if "E-T2" in part_e_triggered:
                _pe("E-T2", "Current job / last working day / salary breakdown")
            if "E-T3" in part_e_triggered:
                _pe("E-T3", "Delayed start — reason")
            _pe("E-A4",    "Known leave or exams next 30 days")
            _pe("E-A5",    "Transport / backup plan")
            _pe("E-Final", "First-3-days commitment")
            lines.append("")
            lines.append("<i>(Salary in E-T2 is applicant's current salary, not our offer)</i>")

        lines += ["", f"🔗 Attempt ID: <code>{attempt_id}</code> | Chat: <code>{chat_id}</code>"]

        await bot.send_message(
            config.OWNER_TELEGRAM_ID,
            "\n".join(lines),
            parse_mode="HTML",
        )
        # Send succeeded — now mark as notified
        try:
            from shared.database import raw_connect
            conn2 = raw_connect()
            cur2  = conn2.cursor()
            cur2.execute("""
                UPDATE hiring_quiz_attempts
                SET quiz_owner_notified_at=now(), quiz_owner_notified_outcome=%s
                WHERE id=%s
            """, (outcome, attempt_id))
            conn2.commit()
            conn2.close()
        except Exception as mark_exc:
            logger.warning("_notify_owner_quiz mark failed: %s", mark_exc)

    except Exception as exc:
        logger.error("_notify_owner_quiz failed attempt=%s: %s", attempt_id, exc)


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

    await _notify_owner_quiz(context.bot, chat_id, attempt_id, outcome="completed")

    # Run Opus assessment pipeline in background — quiz completion is never blocked
    try:
        from hire_bot.assessment_pipeline import run_full_assessment
        await run_full_assessment(context.bot, attempt_id, session_id)
    except Exception as e:
        logger.error("Assessment pipeline failed for attempt %s: %s", attempt_id, e)


# ── Correction / offer private helpers ───────────────────────────────────────

async def _handle_correction_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Applicant typed their question after tapping [I have a question]."""
    attempt_id = context.user_data.get("attempt_id")
    context.user_data["awaiting_correction_question"] = False
    try:
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"Applicant correction question (attempt #{attempt_id}):\n\n{update.message.text}",
        )
    except Exception as e:
        logger.error("_handle_correction_question owner fwd failed: %s", e)
        # observability law: we promise the applicant a reply below — a lost forward must leave a
        # durable trace (the gm sweep re-raises undelivered sink alarms to the owner within ~30 min).
        try:
            from gm_bot.alarms import log_alarm
            log_alarm("hire_question_lost",
                      "Hire bot: applicant question (attempt #%s) FAILED to forward to you: %.300s"
                      % (attempt_id, update.message.text))
        except Exception:
            pass
    await update.message.reply_text(
        "Thank you. We will review your question and get back to you.\n\n"
        "អរគុណ។ យើងនឹងពិនិត្យ ហើយឆ្លើយតបប្អូន។",
        reply_markup=correction_flow.AGREE_KEYBOARD,
    )


async def _handle_offer_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Applicant typed a question about the offer."""
    attempt_id = (context.user_data.get("attempt_id") or
                  (context.user_data.get("pending_offer") or {}).get("attempt_id"))
    context.user_data["awaiting_offer_question"] = False
    try:
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"Applicant offer question (attempt #{attempt_id}):\n\n{update.message.text}",
        )
    except Exception as e:
        logger.error("_handle_offer_question owner fwd failed: %s", e)
        try:
            from gm_bot.alarms import log_alarm
            log_alarm("hire_question_lost",
                      "Hire bot: applicant OFFER question (attempt #%s) FAILED to forward to you: %.300s"
                      % (attempt_id, update.message.text))
        except Exception:
            pass
    await update.message.reply_text(
        "Thank you. We will reply to you directly.\n\n"
        "អរគុណ។ យើងនឹងឆ្លើយតបប្អូនដោយផ្ទាល់។"
    )


async def _handle_owner_e_t2_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner typed the E-T2 last working day clarification."""
    attempt_id        = context.user_data.pop("awaiting_e_t2_for_attempt", None)
    applicant_user_id = context.user_data.pop("pending_approve_applicant_id", None)
    suggested_offer   = context.user_data.pop("pending_approve_suggested_offer", {})
    details           = context.user_data.pop("pending_approve_details", {})
    clarification     = update.message.text.strip()

    if not applicant_user_id or not suggested_offer:
        await update.message.reply_text("State lost — retry /approve or use the button again.")
        return

    await offer_flow.send_offer_message(context.bot, applicant_user_id, suggested_offer, start_date=None)
    context.application.user_data[applicant_user_id]["pending_offer"] = {
        "suggested_offer": suggested_offer,
        "candidate_id":    details.get("candidate_id"),
        "intake_id":       details.get("intake_id"),
        "attempt_id":      attempt_id,
        "assessment_id":   details.get("assessment_id"),
        "e_t2_note":       clarification,
    }
    await update.message.reply_text(
        f"✅ Offer sent to applicant (attempt #{attempt_id}).\nE-T2 note stored: {clarification}"
    )


# ── Correction callbacks ──────────────────────────────────────────────────────

async def cb_correction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle correction:* button taps from the applicant."""
    await correction_flow.handle_correction_callback(update, context)


# ── Owner offer callbacks ─────────────────────────────────────────────────────

async def cb_owner_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner taps [Approve trial — send offer]. Checks E-T2 then sends offer."""
    query = update.callback_query
    await query.answer()

    attempt_id = int(query.data.split(":", 2)[2])

    if offer_flow.is_already_approved(attempt_id):
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"Attempt #{attempt_id} was already approved."
        )
        return

    offer_flow.approve_trial_in_db(attempt_id)
    await query.edit_message_reply_markup(reply_markup=None)

    details = offer_flow.get_attempt_details(attempt_id)
    if not details or not details.get("applicant_user_id"):
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"Could not load applicant for attempt #{attempt_id}."
        )
        return

    applicant_user_id = details["applicant_user_id"]
    suggested_offer   = details["suggested_offer"]

    if offer_flow.check_e_t2_partial(attempt_id):
        context.user_data["awaiting_e_t2_for_attempt"]      = attempt_id
        context.user_data["pending_approve_applicant_id"]    = applicant_user_id
        context.user_data["pending_approve_suggested_offer"] = suggested_offer
        context.user_data["pending_approve_details"]         = details
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"E-T2 is incomplete — last working day is missing.\n"
            f"Please type the candidate's last working day (e.g. 'June 15') "
            f"or 'skip' to proceed without it."
        )
        return

    await offer_flow.send_offer_message(context.bot, applicant_user_id, suggested_offer, start_date=None)
    context.application.user_data[applicant_user_id]["pending_offer"] = {
        "suggested_offer": suggested_offer,
        "candidate_id":    details["candidate_id"],
        "intake_id":       details["intake_id"],
        "attempt_id":      attempt_id,
        "assessment_id":   details["assessment_id"],
    }
    await context.bot.send_message(
        config.OWNER_TELEGRAM_ID,
        f"✅ Offer sent to applicant (attempt #{attempt_id})."
    )
    logger.info("cb_owner_approve: offer sent attempt=%s applicant=%s", attempt_id, applicant_user_id)


async def cb_owner_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner taps [Reject — close]. Marks attempt rejected, no offer sent."""
    query = update.callback_query
    await query.answer()

    attempt_id = int(query.data.split(":", 2)[2])
    offer_flow.reject_trial_in_db(attempt_id)
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        config.OWNER_TELEGRAM_ID,
        f"Attempt #{attempt_id} rejected. No offer will be sent."
    )
    logger.info("cb_owner_reject: attempt=%s rejected", attempt_id)


# ── Applicant offer callbacks ─────────────────────────────────────────────────

async def cb_offer_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Applicant taps [Yes, I accept]. Creates hiring_offers row."""
    query = update.callback_query
    await query.answer()

    if context.user_data.get("offer_accepted"):
        await query.edit_message_reply_markup(reply_markup=None)
        return

    pending = context.user_data.get("pending_offer")
    if not pending:
        await query.edit_message_text(
            "Something went wrong. Please contact management.\n\n"
            "មានបញ្ហា។ សូមទំនាក់ទំនងការគ្រប់គ្រង។"
        )
        return

    attempt_id = pending.get("attempt_id")
    try:
        offer_id = offer_flow.record_offer_accepted(
            candidate_id   = pending["candidate_id"],
            intake_id      = pending.get("intake_id"),
            attempt_id     = attempt_id,
            assessment_id  = pending.get("assessment_id"),
            suggested_offer= pending["suggested_offer"],
            start_date     = None,
            reason         = "applicant_accepted_via_bot",
        )
        context.user_data["offer_accepted"] = True
        context.user_data.pop("pending_offer", None)
    except Exception as e:
        logger.error("cb_offer_accept record_offer_accepted failed attempt=%s: %s", attempt_id, e)
        await query.edit_message_text(
            "Error recording acceptance. Please contact management.\n\n"
            "មានបញ្ហា។ សូមទំនាក់ទំនងការគ្រប់គ្រង។"
        )
        return

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        update.effective_chat.id,
        "✅ Your acceptance has been recorded.\n"
        "We will contact you with the next steps shortly.\n\n"
        "✅ ការយល់ព្រមរបស់ប្អូនត្រូវបានកត់ត្រា។\n"
        "យើងនឹងទំនាក់ទំនងប្អូន ជាមួយជំហានបន្ទាប់ ក្នុងពេលឆាប់ៗ។"
    )
    try:
        await context.bot.send_message(
            config.OWNER_TELEGRAM_ID,
            f"✅ <b>Offer accepted</b> — Attempt #{attempt_id} | Offer #{offer_id}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("cb_offer_accept owner notify failed: %s", e)


async def cb_offer_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Applicant taps [I have a question] on the offer."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    context.user_data["awaiting_offer_question"] = True
    await context.bot.send_message(
        update.effective_chat.id,
        "Please type your question. We will get back to you soon.\n\n"
        "សូមវាយសំណួររបស់ប្អូន។ យើងនឹងឆ្លើយតបក្នុងពេលឆាប់ៗ។"
    )


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point — either staff command or candidate deep link."""
    if update.message.chat.type != "private":
        return

    args = context.args
    user = update.effective_user
    chat_id = update.effective_chat.id

    # No token → check for active quiz session (bot restart recovery)
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
        # No quiz session — route to intake (public ad entry point)
        await intake.start_intake(update, context)
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
        await _after_main_quiz(context, update.effective_chat.id, session_id, attempt_id)


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
        await _after_main_quiz(context, update.effective_chat.id, session_id, attempt_id)


async def cb_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle yes/no/not_sure and single-choice callbacks.
    Format: ans:QUESTION_ID:VALUE
    Part E and main quiz use separate expected-question sources to avoid false rejects.
    """
    query = update.callback_query
    _, qid, value = query.data.split(":", 2)

    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        await query.answer("Session not found. Use your invite link.")
        return

    session_id = context.user_data.get("session_id")
    chat_id = update.effective_chat.id

    # ── Part E button answer (E-A3a, E-A3b are single_choice; E-T1 is single_choice) ──
    if context.user_data.get("in_part_e"):
        e_answered: set = context.user_data.get("part_e_answered", set())
        triggered: list = context.user_data.get("part_e_triggered", [])
        expected = questions.get_next_part_e_question(e_answered, triggered)
        if qid != expected:
            logger.info("cb_answer(E): stale qid=%s expected=%s attempt=%s",
                        qid, expected, attempt_id)
            await query.answer()
            return
        await query.answer()
        await _delete(query.message)
        sessions.record_answer(attempt_id, qid, {"answer": value})
        _cancel_timeout(context, chat_id)
        await _advance_part_e(context, chat_id, session_id, attempt_id, qid)
        return

    # ── Main quiz button answer ────────────────────────────────────────────────
    answered = sessions.get_answered_question_ids(attempt_id)
    expected = questions.get_next_question_id(answered)
    if qid != expected:
        logger.info("cb_answer: stale qid=%s expected=%s attempt=%s",
                    qid, expected, attempt_id)
        await query.answer()
        return

    await query.answer()
    await _delete(query.message)
    sessions.record_answer(attempt_id, qid, {"answer": value})
    _cancel_timeout(context, chat_id)

    answered.add(qid)
    next_qid = questions.get_next_question_id(answered)
    if next_qid:
        await _send_question(context, chat_id, attempt_id, next_qid)
    else:
        await _after_main_quiz(context, chat_id, session_id, attempt_id)


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
            await _after_main_quiz(context, update.effective_chat.id, session_id, attempt_id)
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
    Routes to intake if no active quiz session.
    """
    if update.message.chat.type != "private":
        return

    # ── Owner states (before quiz routing — owner has no quiz attempt) ──────────
    if update.effective_user.id == config.OWNER_TELEGRAM_ID:
        if context.user_data.get("awaiting_e_t2_for_attempt"):
            await _handle_owner_e_t2_answer(update, context)
            return

    # ── Correction / offer free-text states ─────────────────────────────────
    if context.user_data.get("awaiting_open_check"):
        attempt_id_for_check = context.user_data.get("attempt_id")
        result = await correction_flow.handle_open_check_answer(
            update, context,
            targeted_message_id=context.user_data.get("correction_message_id"),
            attempt_id=attempt_id_for_check,
        )
        # Path A: send owner the offer approval button (verbal retest happens in person)
        primary = (result or {}).get("primary", "")
        if primary in ("correction_understood", "correction_understood_with_qualifier"):
            try:
                details = offer_flow.get_attempt_details(attempt_id_for_check)
                if details:
                    await offer_flow.request_owner_approval(
                        bot=context.bot,
                        attempt_id=attempt_id_for_check,
                        assessment_id=details.get("assessment_id"),
                        candidate_name=details.get("candidate_name", "Applicant"),
                        suggested_offer=details.get("suggested_offer", {}),
                        correction_classification=primary,
                        open_check_answer=update.message.text,
                    )
            except Exception as e:
                logger.error("request_owner_approval after open_check failed: %s", e)
        return

    if context.user_data.get("awaiting_correction_question"):
        await _handle_correction_question(update, context)
        return

    if context.user_data.get("awaiting_offer_question"):
        await _handle_offer_question(update, context)
        return

    attempt_id = context.user_data.get("attempt_id")
    if not attempt_id:
        # Route to intake funnel
        chat_id = update.effective_chat.id
        session = intake.get_intake_session(chat_id)
        if session and session["intake_status"] in intake.ACTIVE_STATUSES:
            await intake.handle_message(update, context, session)
        elif not session or session["intake_status"] == intake.S_BLOCKED:
            # Bot is ad-linked — any first message is a job inquiry; no keyword gate needed.
            # S_BLOCKED: start_intake handles cooldown check and resets when expired.
            await intake.start_intake(update, context)
        elif session["intake_status"] == intake.S_TEST_UNLOCKED:
            await update.message.reply_text(
                "Your interview quiz is ready. Please use your invite link to begin the test.\n\n"
                "ការធ្វើតេស្តរបស់ប្អូនបានបើក។ សូមប្រើតំណផ្ញើអញ្ជើញ ដើម្បីចាប់ផ្ដើម។"
            )
        return

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

    session_id = context.user_data.get("session_id")

    # Part E free-text answer
    if context.user_data.get("in_part_e"):
        expected = context.user_data.get("current_qid")
        if not expected:
            return
        q = questions.get_question(expected)
        if not q or q["answer_type"] not in ("free_text", "rewrite"):
            return
        last_q = context.user_data.get("last_q_msg_id")
        if last_q:
            try:
                await context.bot.delete_message(chat_id, last_q)
            except TelegramError:
                pass
        await _delete(update.message)
        sessions.record_answer(attempt_id, expected, {"text": user_text})
        _cancel_timeout(context, chat_id)
        await _advance_part_e(context, chat_id, session_id, attempt_id, expected)
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
        await _after_main_quiz(context, chat_id, session_id, attempt_id)


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


async def _backup_recorder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Backup recorder for the two listener-blind senior groups (session 28).
    The GM bot is the primary writer; both bots see the SAME per-chat message_ids, so
    ON CONFLICT DO NOTHING makes dual writing naturally duplicate-free. The hire bot is
    rarely redeployed, so its uptime barely correlates with the GM's — real redundancy.
    Requires: bot added to the groups + BotFather privacy mode DISABLED."""
    msg = update.message or update.edited_message
    if not msg or msg.chat_id not in (config.SUPERVISORS_CHAT_ID, config.MANAGEMENT_CHAT_ID):
        return
    try:
        from shared.database import save_ops_message
        media = ("photo" if msg.photo else "video" if msg.video else
                 "document" if msg.document else None)
        save_ops_message(msg.chat_id, msg.message_id, msg.chat.title or None,
                         msg.from_user.id if msg.from_user else None,
                         msg.from_user.full_name if msg.from_user else None,
                         msg.text or msg.caption or "", media,
                         msg.date.isoformat() if msg.date else None)
    except Exception:
        logger.exception("backup recorder failed")


# ── Application builder ───────────────────────────────────────────────────────

def build_application(token: str) -> Application:
    questions.load_all_questions()

    app = Application.builder().token(token).build()
    from shared.error_handler import make_error_handler
    app.add_error_handler(make_error_handler("Hire"))   # crashes are never silent

    # Backup recorder for the senior groups — its own handler group, never interferes
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, _backup_recorder), group=-2)

    # Intake handlers (group=-1 = higher priority than quiz handlers)
    app.add_handler(
        MessageHandler(filters.VOICE | filters.VIDEO_NOTE, intake.handle_voice),
        group=-1,
    )
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL) & filters.ChatType.PRIVATE,
            _handle_document_or_photo,
        ),
        group=-1,
    )
    app.add_handler(
        CallbackQueryHandler(intake.handle_callback, pattern="^intake:"),
        group=-1,
    )

    # Quiz handlers (group=0, default)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("create", cmd_create))
    app.add_handler(CommandHandler("reopen", cmd_reopen))

    app.add_handler(CallbackQueryHandler(cb_identity_ok, pattern="^id_ok$"))
    app.add_handler(CallbackQueryHandler(cb_start_quiz, pattern="^start_quiz$"))
    app.add_handler(CallbackQueryHandler(cb_resume, pattern="^do_resume$"))
    app.add_handler(CallbackQueryHandler(cb_ranking, pattern="^rank:"))
    app.add_handler(CallbackQueryHandler(cb_answer, pattern="^ans:"))

    # Correction flow (applicant)
    app.add_handler(CallbackQueryHandler(cb_correction, pattern="^correction:"))

    # Offer flow — owner approval
    app.add_handler(CallbackQueryHandler(cb_owner_approve, pattern=r"^offer:owner_approve:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_owner_reject,  pattern=r"^offer:owner_reject:\d+$"))

    # Offer flow — applicant response
    app.add_handler(CallbackQueryHandler(cb_offer_accept,   pattern="^offer:accept$"))
    app.add_handler(CallbackQueryHandler(cb_offer_question, pattern="^offer:question$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Day-of arrival reminder — runs every 10 minutes
    app.job_queue.run_repeating(
        intake.send_arrival_reminders,
        interval=600,
        first=60,
    )

    return app


async def _handle_document_or_photo(update: Update,
                                    context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route photo/document to intake if in intake state; otherwise ignore."""
    chat_id = update.effective_chat.id
    attempt_id = context.user_data.get("attempt_id")
    if attempt_id:
        return  # In quiz — quiz doesn't use photos, just ignore
    session = intake.get_intake_session(chat_id)
    if session and session["intake_status"] in intake.ACTIVE_STATUSES:
        await intake.handle_message(update, context, session)
    elif not session or session["intake_status"] == intake.S_BLOCKED:
        # First contact via photo CV (or re-applying after cooldown) — start intake first,
        # then route the photo: _handle_language_check skips to CV processing when media present
        await intake.start_intake(update, context)
        session = intake.get_intake_session(chat_id)
        if session and session["intake_status"] in intake.ACTIVE_STATUSES:
            await intake.handle_message(update, context, session)
    elif session["intake_status"] == intake.S_TEST_UNLOCKED:
        await update.message.reply_text(
            "Your interview quiz is ready. Please use your invite link to begin the test.\n\n"
            "ការធ្វើតេស្តរបស់ប្អូនបានបើក។ សូមប្រើតំណផ្ញើអញ្ជើញ ដើម្បីចាប់ផ្ដើម។"
        )
