"""
GM Manager TWB bot — private digest to owner.
Sends operational concerns with [✓ All good] [🚨 Real issue] [📚 Teach bot] buttons.
Does NOT post to any staff group. Owner-only, private chat.
"""
import asyncio
import logging
import time
from collections import defaultdict, deque

from telegram import Bot, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters,
)

import config
from config import resolve_staff_name
from shared.database import (
    gm_get_unsent_concerns, gm_mark_sent, gm_review_concern,
    gm_get_concern_by_msg_id, gm_save_rule, init_gm_db,
    gm_get_related_photos, gm_get_unsent_by_sender, gm_get_pending_by_sender,
    gm_get_unreviewed_by_sender, gm_get_unreviewed_by_sender_name,
    gm_save_proposal, gm_get_proposal, gm_get_draft_proposals,
    gm_approve_proposal, gm_reject_proposal, gm_update_proposal_solution,
    gm_set_proposal_msg_id, gm_get_points_summary, _db,
    gm_get_approved_policy_for_type,
    gm_skip_proposal, gm_get_stale_draft_proposals, gm_purge_lower_ranked_drafts,
    gm_append_refinement_note, save_ops_message,
    init_receipt_clarifications_db, receipt_save_clarification,
    receipt_get_pending, receipt_save_answer, receipt_get_answered_examples,
    init_gm_finance_db, save_daily_report, gm_get_state, gm_set_state,
    init_gm_clarifications_db, gm_create_clarification, gm_get_active_clarifications,
    gm_get_active_clarifications_for_chat, gm_find_clarification_by_question_msg,
    gm_record_clarification_nudge, gm_set_clarification_checking,
    gm_answer_clarification, gm_escalate_clarification, gm_resolve_open_clarifications,
    init_gm_lateness_db, gm_create_lateness_case, gm_get_open_lateness_cases,
    gm_get_open_lateness_in_chat, gm_mark_lateness_group_asked, gm_resolve_lateness,
    gm_escalate_lateness, gm_get_staff_uid,
    gm_add_finance_alias, gm_get_finance_aliases,
    gm_get_lateness_cases_since, gm_get_concerns_since,
)
from shared.ai_client import (
    generate_proposals, refine_proposal_with_ai, refine_proposal_resolve_conflict,
    GM_PROPOSALS_MODEL, assess_receipt_photo, judge_clarification_answer,
    gm_compose_reply, detect_lateness_report, extract_payback_day,
    extract_daily_report_ai, generate_attendance_digest,
)
from gm_bot.analyzer import run_analysis, analyze_live_message
from gm_bot import finance, clarify, lateness, mentions
from telegram.constants import ParseMode
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

TEACH_WAITING           = 1  # ConversationHandler states
REFINE_WAITING          = 2
CONFLICT_WAITING        = 3
CONFLICT_EXPLAIN_WAITING = 4


# ─── Keyboard builders ────────────────────────────────────────────────────────

def _concern_keyboard(concern_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ All good", callback_data="gm:ok:%d" % concern_id),
        InlineKeyboardButton("🚨 Real issue", callback_data="gm:flag:%d" % concern_id),
        InlineKeyboardButton("📚 Teach bot", callback_data="gm:teach:%d" % concern_id),
    ]])


# ─── Concern sender ───────────────────────────────────────────────────────────

SEVERITY_EMOJI = {"info": "ℹ️", "warning": "⚠️", "critical": "🔴"}
TYPE_LABEL = {
    "low_stock": "Low Stock",
    "waste": "Waste/Spoilage",
    "mistake": "Mistake",
    "cleanliness": "Cleanliness",
    "staffing": "Staffing",
    "photo": "Photo Check",
}


def _format_concern(c: dict) -> str:
    emoji = SEVERITY_EMOJI.get(c["severity"], "⚠️")
    label = TYPE_LABEL.get(c["concern_type"], c["concern_type"].replace("_", " ").title())
    sender = resolve_staff_name(c.get("sender_name") or "Unknown")
    desc = c["description"]
    return "%s [%s] — %s\n%s" % (emoji, label, sender, desc)


async def _send_concern_with_photos(bot: Bot, concern: dict, file_ids: list[str]) -> int:
    """Send concern card + photo album. Returns telegram message_id of the concern card."""
    text = _format_concern(concern)
    keyboard = _concern_keyboard(concern["id"])
    file_ids = file_ids[:10]  # Telegram album cap

    if len(file_ids) == 1:
        msg = await bot.send_photo(
            chat_id=config.OWNER_TELEGRAM_ID,
            photo=file_ids[0],
            caption=text,
            reply_markup=keyboard,
        )
    elif len(file_ids) > 1:
        # Album first (no buttons), then concern card with buttons below
        media = [InputMediaPhoto(fid) for fid in file_ids]
        await bot.send_media_group(chat_id=config.OWNER_TELEGRAM_ID, media=media)
        msg = await bot.send_message(
            chat_id=config.OWNER_TELEGRAM_ID,
            text=text,
            reply_markup=keyboard,
        )
    else:
        msg = await bot.send_message(
            chat_id=config.OWNER_TELEGRAM_ID,
            text=text,
            reply_markup=keyboard,
        )
    return msg.message_id


async def send_pending_concerns(bot: Bot) -> int:
    concerns = gm_get_unsent_concerns()
    if not concerns:
        return 0
    sent = 0
    for c in concerns:
        try:
            # Try to get related photo Telegram message IDs
            tg_msg_ids = []
            key = c.get("source_msg_key", "")
            if key.startswith("msg:"):
                parts = key.split(":")
                if len(parts) >= 3:
                    try:
                        ops_id = int(parts[2])
                        tg_msg_ids = gm_get_related_photos(
                            c["source_chat_id"], ops_id, c.get("sender_name", "")
                        )
                    except (ValueError, IndexError):
                        pass

            # Send each photo (forward), then concern card — photos before card
            for tg_msg_id in tg_msg_ids[:10]:
                try:
                    await bot.forward_message(
                        chat_id=config.OWNER_TELEGRAM_ID,
                        from_chat_id=c["source_chat_id"],
                        message_id=tg_msg_id,
                    )
                    await asyncio.sleep(0.1)
                except Exception:
                    pass  # old pre-conversion messages silently skipped

            msg = await bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=_format_concern(c),
                reply_markup=_concern_keyboard(c["id"]),
            )
            gm_mark_sent(c["id"], msg.message_id)
            sent += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error("Failed to send concern %d: %s", c["id"], e)
    return sent


# ─── Scheduled job ────────────────────────────────────────────────────────────

async def _daily_analysis_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("GM: running scheduled analysis")
    try:
        new_count = await run_analysis()
        if new_count > 0:
            logger.info("GM: %d new concerns saved — owner can review with /staff", new_count)
        else:
            logger.info("GM: no new concerns")
    except Exception as e:
        logger.error("GM analysis job failed: %s", e)


async def _auto_skip_proposals_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-skip draft proposals older than 24 hours — returns concerns to pool."""
    try:
        stale = gm_get_stale_draft_proposals(hours=24)
        for p in stale:
            gm_skip_proposal(p["id"])
        if stale:
            logger.info("GM: auto-skipped %d stale proposals", len(stale))
    except Exception as e:
        logger.error("GM auto-skip job failed: %s", e)


# ─── Command handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    await update.message.reply_text(
        "GM Manager active.\n\n"
        "/check — run analysis, show new concerns by staff\n"
        "/review — resend concerns awaiting your button tap\n"
        "/proposals — AI groups all concerns + drafts solutions\n"
        "/approved — GM playbook: all approved proposals\n"
        "/points — monthly points leaderboard\n"
        "/staff <name> — send that person's concerns\n"
        "/rules — show learned suppression rules"
    )


def _staff_list_keyboard(rows: list[dict], bot_data: dict) -> InlineKeyboardMarkup:
    bot_data["staff_index"] = {str(i): r["sender_name"] for i, r in enumerate(rows)}
    buttons = []
    for i, r in enumerate(rows):
        name = resolve_staff_name(r["sender_name"] or "Unknown")
        label = "%s  (%d)" % (name, r["count"])
        buttons.append([InlineKeyboardButton(label, callback_data="ss:%d" % i)])
    return InlineKeyboardMarkup(buttons)


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return

    # Delete any previous button list still open in chat
    prev_id = context.bot_data.pop("check_list_msg_id", None)
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=config.OWNER_TELEGRAM_ID, message_id=prev_id)
        except Exception:
            pass

    msg = await update.message.reply_text("⏳ Running analysis...")
    try:
        new_count = await run_analysis()
        rows = gm_get_pending_by_sender()
        total_unsent = sum(r["count"] for r in rows)
        if new_count == 0 and total_unsent == 0:
            await msg.edit_text("✓ Nothing new.")
            return
        header = "✓ %d new concerns found.\nTap a name to review:" % new_count if new_count else "Tap a name to review:"
        await msg.edit_text(header, reply_markup=_staff_list_keyboard(rows, context.bot_data))
        context.bot_data["check_list_msg_id"] = msg.message_id
    except Exception as e:
        await msg.edit_text("Error: %s" % e)


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    sent = await send_pending_concerns(context.bot)
    if sent == 0:
        await update.message.reply_text("No pending concerns.")


async def cmd_staff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return

    args = context.args
    if not args:
        # List all staff with pending concern counts
        rows = gm_get_pending_by_sender()
        if not rows:
            await update.message.reply_text("No pending concerns for any staff.")
            return
        total = sum(r["count"] for r in rows)
        lines = ["📋 Pending concerns by staff (%d total):\n" % total]
        for r in rows:
            parts = []
            if r["mistakes"]: parts.append("%d mistakes" % r["mistakes"])
            if r["waste"]: parts.append("%d waste" % r["waste"])
            if r["low_stock"]: parts.append("%d low-stock" % r["low_stock"])
            lines.append("• %s — %s" % (resolve_staff_name(r["sender_name"] or "Unknown"), ", ".join(parts)))
        lines.append("\nUse /staff <name> to send their concerns.")
        await update.message.reply_text("\n".join(lines))
        return

    # Send concerns for a specific staff member
    query = " ".join(args)
    concerns = gm_get_unsent_by_sender(query)

    if concerns is None:
        # Multiple senders matched — list them
        from shared.database import gm_get_pending_by_sender
        all_rows = gm_get_pending_by_sender()
        matched = [r for r in all_rows if query.lower() in r["sender_name"].lower()]
        lines = ["'%s' matches multiple people — be more specific:\n" % query]
        for r in matched:
            lines.append("• %s (%d concerns)" % (resolve_staff_name(r["sender_name"]), r["count"]))
        await update.message.reply_text("\n".join(lines))
        return

    if not concerns:
        await update.message.reply_text("No pending concerns matching '%s'." % query)
        return

    sender_display = resolve_staff_name(concerns[0]["sender_name"])
    await update.message.reply_text(
        "Sending %d concerns for %s..." % (len(concerns), sender_display)
    )
    sent = 0
    for c in concerns:
        try:
            tg_msg_ids = []
            key = c.get("source_msg_key", "")
            if key.startswith("msg:"):
                parts = key.split(":")
                if len(parts) >= 3:
                    try:
                        tg_msg_ids = gm_get_related_photos(
                            c["source_chat_id"], int(parts[2]), c.get("sender_name", "")
                        )
                    except (ValueError, IndexError):
                        pass

            for tg_msg_id in tg_msg_ids[:10]:
                try:
                    await context.bot.forward_message(
                        chat_id=config.OWNER_TELEGRAM_ID,
                        from_chat_id=c["source_chat_id"],
                        message_id=tg_msg_id,
                    )
                    await asyncio.sleep(0.1)
                except Exception:
                    pass

            msg = await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=_format_concern(c),
                reply_markup=_concern_keyboard(c["id"]),
            )
            gm_mark_sent(c["id"], msg.message_id)
            sent += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error("Failed to send concern %d: %s", c["id"], e)

    await update.message.reply_text("✓ Sent %d concerns for '%s'." % (sent, query))


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List concerns already sent but not yet reviewed (button not tapped)."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return

    # Delete any previous button list still open in chat
    prev_id = context.bot_data.pop("review_list_msg_id", None)
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=config.OWNER_TELEGRAM_ID, message_id=prev_id)
        except Exception:
            pass

    rows = gm_get_unreviewed_by_sender()
    if not rows:
        await update.message.reply_text("✓ Nothing awaiting review.")
        return

    total = sum(r["count"] for r in rows)
    msg = await update.message.reply_text(
        "%d concerns sent but not reviewed yet.\nTap a name to resend:" % total,
        reply_markup=_staff_list_keyboard(rows, context.bot_data),
    )
    context.bot_data["review_list_msg_id"] = msg.message_id
    context.bot_data["review_mode"] = True


def _format_proposal(p: dict, index: int = 0, total: int = 0) -> str:
    import json as _json
    ptype = p.get("proposal_type", "correction")
    icon = "📊" if ptype == "correction" else "⭐"
    names = _json.loads(p.get("staff_names") or "[]") if isinstance(p.get("staff_names"), str) else (p.get("staff_names") or [])
    ids = _json.loads(p.get("concern_ids") or "[]") if isinstance(p.get("concern_ids"), str) else (p.get("concern_ids") or [])

    staff_str = ", ".join(names[:5])
    if len(names) > 5:
        staff_str += " (+%d)" % (len(names) - 5)

    counter = " (%d/%d)" % (index, total) if total else ""
    points_line = "\nPoints to award: +%d per person" % p["points"] if p.get("points") else ""
    ids_preview = ", ".join("#%d" % i for i in ids[:8])
    if len(ids) > 8:
        ids_preview += "..."

    return (
        "%s Proposal%s: %s\n\n"
        "Staff: %s\n"
        "Root cause: %s\n%s\n"
        "━━━━━━━━━━━━━━━\n"
        "%s\n"
        "━━━━━━━━━━━━━━━\n"
        "Recipients: %s  •  %d concerns\n"
        "Covers: %s"
    ) % (icon, counter, p["group_name"],
         staff_str or "—",
         p.get("root_cause") or "—",
         points_line,
         p.get("solution_text") or "—",
         p.get("recipients", "group"), len(ids),
         ids_preview)


def _proposal_keyboard(proposal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ Approve", callback_data="gmprop:approve:%d" % proposal_id),
        InlineKeyboardButton("✏️ Refine",  callback_data="gmprop:refine:%d" % proposal_id),
        InlineKeyboardButton("✗ Skip",    callback_data="gmprop:skip:%d" % proposal_id),
    ]])


def _approved_keyboard(proposal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Refine", callback_data="gmprop:refine:%d" % proposal_id),
    ]])


async def cmd_proposals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return

    # Purge any drafts generated by a lower-ranked model (returns their concerns to pool)
    purged = gm_purge_lower_ranked_drafts(GM_PROPOSALS_MODEL)
    if purged:
        await update.message.reply_text(
            "🔄 Replaced %d lower-quality draft(s) — concerns returned to pool." % purged
        )

    # Show existing same-model drafts if any (free resend)
    drafts = gm_get_draft_proposals()
    if drafts:
        msg = await update.message.reply_text(
            "📋 %d existing proposals. Resending now..." % len(drafts)
        )
        for i, p in enumerate(drafts, 1):
            text = _format_proposal(p, i, len(drafts))
            sent = await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=text,
                reply_markup=_proposal_keyboard(p["id"]),
            )
            gm_set_proposal_msg_id(p["id"], sent.message_id)
        await msg.delete()
        return

    # Generate new proposals
    msg = await update.message.reply_text("⏳ Analysing concerns with AI — this takes a moment...")
    try:
        # Fetch all unreviewed concerns (sent + unsent)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, concern_type, sender_name, description
                    FROM gm_concerns
                    WHERE review_action IS NULL
                    ORDER BY detected_at ASC
                """)
                concerns = [dict(r) for r in cur.fetchall()]

        if not concerns:
            await msg.edit_text("✓ No unreviewed concerns to analyse.")
            return

        # Fetch approved proposals as learned context (Option 3)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM gm_proposals WHERE status = 'approved' ORDER BY approved_at DESC")
                approved = [dict(r) for r in cur.fetchall()]

        await msg.edit_text("⏳ Analysing %d concerns — generating proposals..." % len(concerns))
        proposals = await generate_proposals(concerns, approved_proposals=approved)

        if not proposals:
            await msg.edit_text("Could not generate proposals. Check API key or try again.")
            return

        await msg.edit_text("✓ %d proposals generated. Sending now..." % len(proposals))

        for i, p in enumerate(proposals, 1):
            prop_id = gm_save_proposal(
                proposal_type=p.get("proposal_type", "correction"),
                group_name=p.get("group_name", "Unnamed"),
                concern_type=p.get("concern_type", "mixed"),
                concern_ids=p.get("concern_ids", []),
                root_cause=p.get("root_cause", ""),
                solution_text=p.get("solution_text", ""),
                recipients=p.get("recipients", "group"),
                staff_names=p.get("staff_names", []),
                points=p.get("points", 0),
                model=GM_PROPOSALS_MODEL,
            )
            p["id"] = prop_id
            text = _format_proposal(p, i, len(proposals))
            sent = await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=text,
                reply_markup=_proposal_keyboard(prop_id),
            )
            gm_set_proposal_msg_id(prop_id, sent.message_id)
            await asyncio.sleep(0.3)

        await msg.delete()

    except Exception as e:
        await msg.edit_text("Error generating proposals: %s" % e)
        logger.error("Proposals generation error: %s", e)


async def gmprop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    parts = query.data.split(":")
    action, proposal_id = parts[1], int(parts[2])
    p = gm_get_proposal(proposal_id)
    if not p:
        await query.edit_message_text("Proposal not found.")
        return ConversationHandler.END

    if action == "approve":
        gm_approve_proposal(proposal_id)
        ptype = p.get("proposal_type", "correction")
        label = "armed for future re-education" if ptype == "correction" else "recognition armed — points will be awarded"
        await query.edit_message_text(
            query.message.text + "\n\n✓ Approved — %s." % label
        )
        return ConversationHandler.END

    if action == "skip":
        gm_skip_proposal(proposal_id)
        await query.edit_message_text(
            query.message.text + "\n\n⏭️ Skipped — concerns return to pool for next /proposals run."
        )
        return ConversationHandler.END

    if action == "refine":
        context.user_data["refining_proposal_id"] = proposal_id
        import json as _json
        history = _json.loads(p.get("refinement_history") or "[]") if isinstance(p.get("refinement_history"), str) else (p.get("refinement_history") or [])
        history_text = ""
        if history:
            lines = []
            for i, h in enumerate(history, 1):
                at = h.get("at", "")[:10]
                lines.append("%d. [%s] %s" % (i, at, h.get("note", "")))
            history_text = "\n\nPrevious notes:\n%s" % "\n".join(lines)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✏️ Refining: %s\n\n"
            "Current solution:\n%s%s\n\n"
            "━━━━━━━━━━━━━━━\n"
            "Add context, corrections, or new info. AI stacks all notes and rewrites.\n"
            "If your new note conflicts with an old one, I'll ask which applies.\n\n"
            "/cancel to keep as is." % (p["group_name"], p["solution_text"], history_text)
        )
        return REFINE_WAITING

    return ConversationHandler.END


async def refine_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    feedback = update.message.text.strip()
    proposal_id = context.user_data.pop("refining_proposal_id", None)
    if not proposal_id:
        return ConversationHandler.END

    p = gm_get_proposal(proposal_id)
    if not p:
        return ConversationHandler.END

    import json as _json
    history = _json.loads(p.get("refinement_history") or "[]") if isinstance(p.get("refinement_history"), str) else (p.get("refinement_history") or [])

    thinking = await update.message.reply_text("⏳ Rewriting with AI...")
    result = await refine_proposal_with_ai(p, feedback, refinement_history=history)
    await thinking.delete()

    if result.get("conflict"):
        # Conflict detected — pause and ask owner which applies
        context.user_data["pending_conflict"] = {
            "proposal_id": proposal_id,
            "feedback": feedback,
            "conflict_desc": result["conflict"],
        }
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("New applies",   callback_data="gmprop:conflict:new:%d" % proposal_id),
            InlineKeyboardButton("Old applies",   callback_data="gmprop:conflict:old:%d" % proposal_id),
            InlineKeyboardButton("Keep both",     callback_data="gmprop:conflict:merge:%d" % proposal_id),
            InlineKeyboardButton("✏️ Explain...", callback_data="gmprop:conflict:custom:%d" % proposal_id),
        ]])
        await update.message.reply_text(
            "⚠️ Conflict in your notes:\n\n%s\n\nWhich should the AI use?" % result["conflict"],
            reply_markup=kb,
        )
        return CONFLICT_WAITING

    # No conflict — save immediately
    gm_update_proposal_solution(proposal_id, result["solution_text"])
    gm_append_refinement_note(proposal_id, feedback)

    p = gm_get_proposal(proposal_id)
    is_approved = p.get("status") == "approved"
    text = _format_proposal(p) + ("\n\n✓ Approved" if is_approved else "")
    kb = _approved_keyboard(proposal_id) if is_approved else _proposal_keyboard(proposal_id)
    sent = await context.bot.send_message(
        chat_id=config.OWNER_TELEGRAM_ID, text=text, reply_markup=kb,
    )
    gm_set_proposal_msg_id(proposal_id, sent.message_id)
    return ConversationHandler.END


async def conflict_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    parts = query.data.split(":")
    # format: gmprop:conflict:<resolution>:<id>
    resolution = parts[2]
    proposal_id = int(parts[3])

    pending = context.user_data.get("pending_conflict")
    if not pending or pending["proposal_id"] != proposal_id:
        await query.edit_message_text("Session expired — please tap Refine again.")
        return ConversationHandler.END

    if resolution == "custom":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "✏️ Tell me how to resolve it — type your instruction and I'll pass it to the AI.\n\n"
            "/cancel to keep as is."
        )
        return CONFLICT_EXPLAIN_WAITING

    context.user_data.pop("pending_conflict", None)

    p = gm_get_proposal(proposal_id)
    if not p:
        return ConversationHandler.END

    import json as _json
    history = _json.loads(p.get("refinement_history") or "[]") if isinstance(p.get("refinement_history"), str) else (p.get("refinement_history") or [])

    await query.edit_message_reply_markup(reply_markup=None)
    thinking = await query.message.reply_text("⏳ Applying your decision...")
    new_solution = await refine_proposal_resolve_conflict(
        p, pending["feedback"], history, pending["conflict_desc"], resolution
    )
    await thinking.delete()

    gm_update_proposal_solution(proposal_id, new_solution)
    gm_append_refinement_note(proposal_id, pending["feedback"])

    p = gm_get_proposal(proposal_id)
    is_approved = p.get("status") == "approved"
    text = _format_proposal(p) + ("\n\n✓ Approved" if is_approved else "")
    kb = _approved_keyboard(proposal_id) if is_approved else _proposal_keyboard(proposal_id)
    sent = await context.bot.send_message(
        chat_id=config.OWNER_TELEGRAM_ID, text=text, reply_markup=kb,
    )
    gm_set_proposal_msg_id(proposal_id, sent.message_id)
    return ConversationHandler.END


async def conflict_explain_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Owner typed a custom conflict resolution instruction."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    instruction = update.message.text.strip()
    pending = context.user_data.pop("pending_conflict", None)
    if not pending:
        return ConversationHandler.END

    p = gm_get_proposal(pending["proposal_id"])
    if not p:
        return ConversationHandler.END

    import json as _json
    history = _json.loads(p.get("refinement_history") or "[]") if isinstance(p.get("refinement_history"), str) else (p.get("refinement_history") or [])

    thinking = await update.message.reply_text("⏳ Applying your instruction...")
    new_solution = await refine_proposal_resolve_conflict(
        p, pending["feedback"], history, pending["conflict_desc"], instruction
    )
    await thinking.delete()

    gm_update_proposal_solution(pending["proposal_id"], new_solution)
    gm_append_refinement_note(pending["proposal_id"], pending["feedback"])

    p = gm_get_proposal(pending["proposal_id"])
    is_approved = p.get("status") == "approved"
    text = _format_proposal(p) + ("\n\n✓ Approved" if is_approved else "")
    kb = _approved_keyboard(pending["proposal_id"]) if is_approved else _proposal_keyboard(pending["proposal_id"])
    await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=text, reply_markup=kb)
    return ConversationHandler.END


async def refine_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("refining_proposal_id", None)
    context.user_data.pop("pending_conflict", None)
    await update.message.reply_text("Cancelled — proposal unchanged.")
    return ConversationHandler.END


async def cmd_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    rows = gm_get_points_summary(since_days=30)
    if not rows:
        await update.message.reply_text("No points recorded yet this month.")
        return
    lines = ["⭐ Points — last 30 days:\n"]
    for r in rows:
        lines.append("• %s  +%d pts" % (r["staff_name"] or "Unknown", r["good_points"]))
    await update.message.reply_text("\n".join(lines))


async def cmd_approved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all approved proposals — the GM's current playbook."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_proposals
                WHERE status = 'approved'
                ORDER BY approved_at DESC
            """)
            proposals = [dict(r) for r in cur.fetchall()]

    if not proposals:
        await update.message.reply_text(
            "No approved proposals yet.\n"
            "Run /proposals to generate and approve some."
        )
        return

    await update.message.reply_text("📋 GM Playbook — %d approved proposals:" % len(proposals))
    for p in proposals:
        ptype = p.get("proposal_type", "correction")
        icon = "✓📊" if ptype == "correction" else "✓⭐"
        import json as _json
        history = _json.loads(p.get("refinement_history") or "[]") if isinstance(p.get("refinement_history"), str) else (p.get("refinement_history") or [])
        note_line = "  (%d refinement note%s)" % (len(history), "s" if len(history) != 1 else "") if history else ""
        text = _format_proposal(p) + "\n\n%s Approved%s" % (icon, note_line)
        await context.bot.send_message(
            chat_id=config.OWNER_TELEGRAM_ID,
            text=text,
            reply_markup=_approved_keyboard(p["id"]),
        )
        await asyncio.sleep(0.3)


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    from shared.database import gm_get_rules
    rules = gm_get_rules()
    if not rules:
        await update.message.reply_text("No rules learned yet.")
        return
    lines = ["📚 Learned rules (%d):" % len(rules)]
    for r in rules[:20]:
        lines.append("• [%s] %s → %s" % (r["concern_type"] or "any", r["pattern"][:50], r["action"]))
        if r["note"]:
            lines.append("  Note: %s" % r["note"][:80])
    await update.message.reply_text("\n".join(lines))


# ─── Button callback handler ──────────────────────────────────────────────────

async def staff_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return

    idx = query.data[3:]  # numeric index
    name = context.bot_data.get("staff_index", {}).get(idx)
    if not name:
        await query.edit_message_text("Session expired — send /check or /review again.")
        return

    review_mode = context.bot_data.pop("review_mode", False)

    if review_mode:
        concerns = gm_get_unreviewed_by_sender_name(name)
    else:
        concerns = gm_get_unsent_by_sender(name)

    if not concerns:
        label = "unreviewed" if review_mode else "pending"
        await query.edit_message_text("No %s concerns for %s." % (label, name))
        return

    sender_display = concerns[0]["sender_name"]
    # Delete the button list immediately — concerns will follow
    await query.message.delete()
    context.bot_data.pop("check_list_msg_id", None)
    context.bot_data.pop("review_list_msg_id", None)

    sent = 0
    for c in concerns:
        try:
            tg_msg_ids = []
            key = c.get("source_msg_key", "")
            if key.startswith("msg:"):
                parts = key.split(":")
                if len(parts) >= 3:
                    try:
                        tg_msg_ids = gm_get_related_photos(
                            c["source_chat_id"], int(parts[2]), c.get("sender_name", "")
                        )
                    except (ValueError, IndexError):
                        pass

            for tg_msg_id in tg_msg_ids[:10]:
                try:
                    await context.bot.forward_message(
                        chat_id=config.OWNER_TELEGRAM_ID,
                        from_chat_id=c["source_chat_id"],
                        message_id=tg_msg_id,
                    )
                    await asyncio.sleep(0.1)
                except Exception:
                    pass

            msg = await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text=_format_concern(c),
                reply_markup=_concern_keyboard(c["id"]),
            )
            gm_mark_sent(c["id"], msg.message_id)
            sent += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error("Failed to send concern %d: %s", c["id"], e)

    # Refresh the appropriate list
    if review_mode:
        rows = gm_get_unreviewed_by_sender()
        if rows:
            context.bot_data["review_mode"] = True
            new_msg = await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="✓ Resent %d for %s.\nStill awaiting review:" % (sent, sender_display),
                reply_markup=_staff_list_keyboard(rows, context.bot_data),
            )
            context.bot_data["review_list_msg_id"] = new_msg.message_id
        else:
            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="✓ All caught up — nothing left to review.",
            )
    else:
        rows = gm_get_pending_by_sender()
        if rows:
            new_msg = await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="✓ Sent %d concerns for %s.\nRemaining:" % (sent, sender_display),
                reply_markup=_staff_list_keyboard(rows, context.bot_data),
            )
            context.bot_data["check_list_msg_id"] = new_msg.message_id
        else:
            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="✓ All concerns reviewed.",
            )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    data = query.data  # "gm:ok:42" | "gm:flag:42" | "gm:teach:42"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "gm":
        return ConversationHandler.END

    action, concern_id = parts[1], int(parts[2])

    if action == "ok":
        gm_review_concern(concern_id, "all_good")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(query.message.text + "\n\n✓ Marked as all good.")
        return ConversationHandler.END

    if action == "flag":
        gm_review_concern(concern_id, "real_issue")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.edit_message_text(query.message.text + "\n\n🚨 Flagged as real issue.")
        return ConversationHandler.END

    if action == "teach":
        context.user_data["teaching_concern_id"] = concern_id
        # Pull description from DB so we can show the original staff message
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT description FROM gm_concerns WHERE id = %s", (concern_id,))
                row = cur.fetchone()
        desc = row["description"] if row else query.message.text
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "📚 Teach — Concern #%d\n\n"
            "Original:\n%s\n\n"
            "━━━━━━━━━━━━━━━\n"
            "Type the phrase I should watch for in future staff messages to recognise this pattern.\n"
            "Copy a key phrase from above, or write your own. No length limit.\n\n"
            "/cancel to skip" % (concern_id, desc)
        )
        return TEACH_WAITING

    return ConversationHandler.END


async def teach_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    pattern = update.message.text.strip()  # full phrase, no truncation
    concern_id = context.user_data.get("teaching_concern_id")

    if concern_id:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT concern_type FROM gm_concerns WHERE id = %s", (concern_id,))
                row = cur.fetchone()
                ctype = row["concern_type"] if row else None

        gm_review_concern(concern_id, "teach", teaching_note=pattern)
        gm_save_rule(concern_type=ctype, pattern=pattern, action="ignore", note=pattern)
        await update.message.reply_text(
            "✓ Saved. Future messages containing this phrase will be suppressed:\n\n\"%s\"" % pattern
        )

    context.user_data.pop("teaching_concern_id", None)
    return ConversationHandler.END


async def teach_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("teaching_concern_id", None)
    context.user_data.pop("refining_proposal_id", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def _conv_interrupt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Any command typed while in a teach/refine state — exit conversation and run the command."""
    context.user_data.pop("teaching_concern_id", None)
    context.user_data.pop("refining_proposal_id", None)
    cmd = update.message.text.split()[0].lstrip("/").split("@")[0].lower()
    dispatch = {
        "check":     cmd_check,
        "review":    cmd_review,
        "proposals": cmd_proposals,
        "approved":  cmd_approved,
        "points":    cmd_points,
        "pending":   cmd_pending,
        "staff":     cmd_staff,
        "rules":     cmd_rules,
        "start":     cmd_start,
    }
    if cmd in dispatch:
        await dispatch[cmd](update, context)
    return ConversationHandler.END


async def _store_daily_report_if_any(msg, text: str) -> dict | None:
    """If a REPORT text is a daily books report, parse + store it. Returns the parsed
    'full' dict (with report_id) or None. Deterministic first; on a report-shaped
    message the free parser under-reads, Sonnet extracts the fields and we LEARN the
    new labels. The money math (recompute) is always deterministic — AI only reads."""
    extra = gm_get_finance_aliases()
    parsed = finance.parse_report_text(text, extra_aliases=extra)

    if not finance.is_daily_report(parsed):
        # AI fallback only when it looks like a report the regex parser missed.
        if config.ANTHROPIC_API_KEY and finance.looks_like_report_attempt(text, parsed):
            ai = await extract_daily_report_ai(text)
            ai_fields = ai.get("fields") or {}
            money = [k for k in ai_fields if k in finance._MONEY_FIELDS]
            if len(money) < 3:
                return None  # AI couldn't read a real report either
            parsed = {k: v for k, v in ai_fields.items() if k in finance._MONEY_FIELDS}
            if ai.get("stated_date"):
                parsed["stated_date"] = ai["stated_date"]
            parsed["fields_found"] = list(parsed.keys())
            parsed["_source"] = "ai"
            # Learn the new labels so the free parser handles them next time.
            for a in ai.get("aliases") or []:
                if a.get("field") in finance._MONEY_FIELDS and a.get("label"):
                    gm_add_finance_alias(a["field"], a["label"])
            logger.info("Daily report AI-fallback parsed %d fields; learned %d aliases",
                        len(money), len(ai.get("aliases") or []))
        else:
            return None

    posted = msg.date  # tz-aware UTC datetime
    computed = finance.recompute(parsed)
    full = {
        "business_day": finance.business_day_for(posted).isoformat(),
        "report_kind": finance.classify_report(posted),
        "raw": parsed,
        "computed": computed,
    }
    full["report_id"] = save_daily_report(
        business_day=full["business_day"],
        report_kind=full["report_kind"],
        source_chat_id=msg.chat_id,
        source_message_id=msg.message_id,
        posted_at=posted.isoformat() if posted else None,
        raw_text=text,
        raw=full["raw"],
        computed=full["computed"],
    )
    logger.info(
        "Daily report stored: id=%s day=%s kind=%s math_ok=%s source=%s",
        full["report_id"], full["business_day"], full["report_kind"],
        full["computed"].get("math_ok"), parsed.get("_source", "free"),
    )
    return full


async def _maybe_correct_report(context, msg, full: dict) -> None:
    """On a math error, send the worked-out correction. Owner-gated: goes to the owner
    privately until gm_state 'report_corrections_to_staff' is 'true', then in-group tagged."""
    computed = full["computed"]
    if computed.get("math_ok", True):
        return
    correction = finance.format_correction(full["raw"], computed)
    if not correction:
        return
    body = f"📊 Report math check — {full['business_day']} ({full['report_kind']})\n\n{correction}"
    to_staff = gm_get_state("report_corrections_to_staff") == "true"
    try:
        if to_staff:
            sent = await context.bot.send_message(
                chat_id=msg.chat_id, text=body, reply_to_message_id=msg.message_id,
            )
            # Open a clarification so the ladder nudges/escalates until staff explain.
            gm_create_clarification(
                chat_id=msg.chat_id,
                chat_title=msg.chat.title,
                topic="report_math",
                question_msg_id=sent.message_id,
                target_msg_id=msg.message_id,
                question_text=body,
                sender_name=(msg.from_user.full_name if msg.from_user else None),
                context_ref=str(full.get("report_id")),
            )
        else:
            await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body)
            try:
                await context.bot.forward_message(
                    chat_id=config.OWNER_TELEGRAM_ID,
                    from_chat_id=msg.chat_id, message_id=msg.message_id,
                )
            except Exception:
                pass
    except Exception as e:
        logger.error("_maybe_correct_report failed: %s", e)


async def _maybe_ask_lost(context, msg, full: dict) -> None:
    """When the drawer is short by more than GM_LOST_FLAG_THRESHOLD, ask the group why.
    Frames the FX context (4000 riel = $1 so the drawer should normally run a little
    OVER). Owner-gated by the same report_corrections_to_staff flag; opens a
    'cash_lost' clarification so the ladder nudges/escalates until staff explain."""
    computed = full["computed"]
    ol = computed.get("over_lost_computed")
    if not finance.lost_exceeds(ol, config.GM_LOST_FLAG_THRESHOLD):
        return
    lost_amt = -ol
    body = (
        "📉 Cash short by $%.2f on %s (%s).\n"
        "Normally the drawer should run a little OVER (we count 4000 riel = $1), "
        "so a shortfall over $%g is worth checking. "
        "Does anyone know why this amount is lost?"
    ) % (lost_amt, full["business_day"], full["report_kind"], config.GM_LOST_FLAG_THRESHOLD)
    to_staff = gm_get_state("report_corrections_to_staff") == "true"
    try:
        if to_staff:
            sent = await context.bot.send_message(
                chat_id=msg.chat_id, text=body, reply_to_message_id=msg.message_id,
            )
            gm_create_clarification(
                chat_id=msg.chat_id,
                chat_title=msg.chat.title,
                topic="cash_lost",
                question_msg_id=sent.message_id,
                target_msg_id=msg.message_id,
                question_text=body,
                sender_name=(msg.from_user.full_name if msg.from_user else None),
                context_ref=str(full.get("report_id")),
            )
            logger.info("Cash-lost ask posted for report %s ($%.2f short)",
                        full.get("report_id"), lost_amt)
        else:
            await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body)
    except Exception as e:
        logger.error("_maybe_ask_lost failed: %s", e)


def _humanize_gap(delta: timedelta) -> str:
    """Short human duration, e.g. '40 min', '12h 5m', '2d 3h'."""
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        return "%d min" % max(mins, 0)
    hours = mins // 60
    if hours < 24:
        return "%dh %dm" % (hours, mins % 60)
    days = hours // 24
    return "%dd %dh" % (days, hours % 24)


def _repeat_within(last_iso: str, now: datetime, window_hours: int) -> bool:
    """True if `last_iso` is a valid timestamp within `window_hours` before `now`."""
    if not last_iso:
        return False
    try:
        last = datetime.fromisoformat(last_iso)
    except (ValueError, TypeError):
        return False
    return timedelta(0) <= (now - last) <= timedelta(hours=window_hours)


def _repeat_alert_text(policy: dict, chat_title: str, concern_type: str,
                       sender: str, trigger: str, gap: str) -> str:
    """Owner heads-up when the same policy is triggered again inside the repeat window."""
    return (
        "⚠️ Repeat issue — correction not landing\n"
        "Group: %s\n"
        "Type: %s\n"
        "Policy: %s\n"
        "%s triggered the same policy again, %s after the last time.\n"
        "Latest message: %s\n"
        "(GM has replied in-group as usual.)"
    ) % (chat_title or "?", concern_type, (policy.get("group_name") or "?"),
         sender or "Someone", gap, (trigger or "")[:200])


def _policy_reply_plan(reply_text: str, to_staff: bool, *,
                       sender: str, chat_title: str, trigger: str) -> dict:
    """Decide where a composed policy reply goes and the exact text to send.
    to_staff True  -> {'destination': 'group', 'text': reply_text} (posted in the group)
    to_staff False -> {'destination': 'owner', 'text': <preview>} (private to owner only)."""
    if to_staff:
        return {"destination": "group", "text": reply_text}
    preview = (
        "📋 Policy reply (preview — NOT sent to staff)\n"
        "Group: %s\n"
        "%s posted: %s\n\n"
        "GM would reply:\n%s"
    ) % (chat_title or "?", sender or "Someone", (trigger or "")[:200], reply_text)
    return {"destination": "owner", "text": preview}


async def _maybe_policy_reply(context, msg, concern_type: str, sender: str, trigger: str) -> None:
    """Voice an approved correction policy live when a matching concern appears.
    Owner-gated: previews privately to the owner until gm_state 'policy_replies_to_staff'
    is 'true', then posts in-group as a reply to the triggering message."""
    policy = gm_get_approved_policy_for_type(concern_type)
    if not policy:
        return
    reply_text = await gm_compose_reply(
        solution_intent=policy.get("solution_text", ""),
        trigger_text=trigger,
        sender_name=sender,
        chat_title=msg.chat.title or "",
    )
    if not reply_text:
        return
    to_staff = gm_get_state("policy_replies_to_staff") == "true"
    plan = _policy_reply_plan(reply_text, to_staff, sender=sender,
                              chat_title=msg.chat.title or "", trigger=trigger)
    try:
        if plan["destination"] == "group":
            await context.bot.send_message(
                chat_id=msg.chat_id, text=plan["text"], reply_to_message_id=msg.message_id,
            )
            logger.info("Policy reply posted in %s (policy #%s, %s)",
                        msg.chat_id, policy.get("id"), concern_type)
            # Repeat detection: same policy/group within the window -> ping owner too.
            rk = "policy_last_reply:%s:%s" % (msg.chat_id, concern_type)
            now = datetime.now(timezone.utc)
            last = gm_get_state(rk)
            if _repeat_within(last, now, config.GM_POLICY_REPEAT_HOURS):
                gap = _humanize_gap(now - datetime.fromisoformat(last))
                alert = _repeat_alert_text(policy, msg.chat.title or "", concern_type,
                                           sender, trigger, gap)
                try:
                    await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=alert)
                    await context.bot.forward_message(
                        chat_id=config.OWNER_TELEGRAM_ID,
                        from_chat_id=msg.chat_id, message_id=msg.message_id,
                    )
                except Exception as e:
                    logger.error("repeat-violation owner alert failed: %s", e)
                logger.info("Repeat policy violation (%s in %s, %s ago) — owner alerted",
                            concern_type, msg.chat_id, gap)
            gm_set_state(rk, now.isoformat())
        else:
            await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=plan["text"])
            logger.info("Policy reply previewed to owner (policy #%s, %s)",
                        policy.get("id"), concern_type)
    except Exception as e:
        logger.error("_maybe_policy_reply failed: %s", e)


# ─── Staff tagging (GLOBAL — use for EVERY GM tag of a staff member) ───────────

def _staff_mention(name: str, uid: int | None = None) -> str:
    """Build a pinging HTML mention for a staff member referenced by free-text name.
    Shows the call-name next to the account tag (mentions.format_mention rules).
    Resolves the uid from ops_messages when not supplied. Use this everywhere the GM
    tags a person so the convention is consistent. Send the message with HTML parse mode."""
    display = name
    resolved_uid = uid
    if resolved_uid is None:
        resolved_uid = gm_get_staff_uid(name)
    if resolved_uid is None:
        disp = config.display_for_call_name(name)
        if disp:
            display = disp
            resolved_uid = gm_get_staff_uid(disp)
    return mentions.format_mention(resolved_uid, display, config.call_name_for(display))


# ─── Lateness / pay-back ladder ───────────────────────────────────────────────

async def _handle_lateness(context, msg, text: str, sender: str) -> None:
    """Supervisors/Management: detect a lateness report and open the pay-back ladder,
    or resolve an open case when a reply supplies the pay-back day. Staged AI:
    free pre-gate -> Haiku detect/extract -> deterministic ladder."""
    chat_id = msg.chat_id

    # 1) Is this a reply that resolves an open case? (reply to the senior's report
    #    or to the GM's question)
    replied = msg.reply_to_message
    if replied:
        for case in gm_get_open_lateness_in_chat(chat_id):
            if replied.message_id in (case.get("case_msg_id"), case.get("last_question_msg_id")):
                pb = await extract_payback_day(text)
                if pb.get("has_payback_day"):
                    gm_resolve_lateness(case["id"], pb.get("payback_day"))
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id, text="Noted, thank you. ✓",
                            reply_to_message_id=msg.message_id,
                        )
                    except Exception:
                        pass
                    logger.info("Lateness case %s resolved: payback=%s",
                                case["id"], pb.get("payback_day"))
                return  # handled as a reply; don't treat as a new report

    # 2) Free pre-gate: only spend a Haiku call on plausibly-attendance messages.
    from gm_bot.analyzer import ATTENDANCE_KW
    t = text.lower()
    if len(text.strip()) < 6 or not any(kw in t for kw in ATTENDANCE_KW):
        return

    # 3) Haiku: is this a lateness report? who, and is a pay-back day already given?
    result = await detect_lateness_report(text)
    if result.get("_error") or not result.get("is_lateness_report"):
        return
    if result.get("confidence", 0.0) < 0.55:
        return
    late_person = (result.get("late_person") or "").strip() or None
    if not late_person:
        return

    reporter_uid = msg.from_user.id if msg.from_user else None
    late_uid = gm_get_staff_uid(late_person) or (
        gm_get_staff_uid(config.display_for_call_name(late_person) or "") or None)

    # 4) If the senior already gave the pay-back day, just record it — no follow-up.
    if result.get("payback_day"):
        case_id = gm_create_lateness_case(
            chat_id, msg.chat.title, msg.message_id, sender, reporter_uid,
            late_person, late_uid, None)
        if case_id:
            gm_resolve_lateness(case_id, result["payback_day"])
            logger.info("Lateness logged with payback day up-front: %s -> %s",
                        late_person, result["payback_day"])
        return

    # 5) No pay-back day -> ask the reporting senior, opening the ladder.
    case_id = gm_create_lateness_case(
        chat_id, msg.chat.title, msg.message_id, sender, reporter_uid,
        late_person, late_uid, None)
    if not case_id:
        return  # already tracked
    reporter_mention = _staff_mention(sender, uid=reporter_uid)
    late_mention = _staff_mention(late_person, uid=late_uid)
    body = lateness.ask_senior_text(reporter_mention, late_mention)
    try:
        sent = await context.bot.send_message(
            chat_id=chat_id, text=body, reply_to_message_id=msg.message_id,
            parse_mode=ParseMode.HTML,
        )
        # Store the question msg id so a reply to it resolves the case.
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE gm_lateness_cases SET last_question_msg_id = %s WHERE id = %s",
                    (sent.message_id, case_id))
        logger.info("Lateness case %s opened, senior asked re %s", case_id, late_person)
    except Exception as e:
        logger.error("lateness ask-senior failed: %s", e)


async def _lateness_ladder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Every couple of minutes: 30 min -> ask the group; 24 h -> tell the owner."""
    now = datetime.now(timezone.utc)
    for case in gm_get_open_lateness_cases():
        action = lateness.decide_lateness_action(
            case["status"], case.get("asked_senior_at"),
            case.get("asked_group_at"), now,
        )
        try:
            if action == "ask_group":
                late_mention = _staff_mention(case.get("late_person") or "",
                                              uid=case.get("late_uid"))
                body = lateness.ask_group_text(late_mention)
                sent = await context.bot.send_message(
                    chat_id=case["chat_id"], text=body,
                    reply_to_message_id=case.get("case_msg_id"),
                    parse_mode=ParseMode.HTML,
                )
                gm_mark_lateness_group_asked(case["id"], sent.message_id)
                logger.info("Lateness case %s: asked the group", case["id"])
            elif action == "escalate":
                body = lateness.escalation_text(
                    case.get("chat_title") or str(case["chat_id"]),
                    case.get("late_person") or "?", case.get("reporter_name"), None)
                await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body)
                if case.get("case_msg_id"):
                    try:
                        await context.bot.forward_message(
                            chat_id=config.OWNER_TELEGRAM_ID,
                            from_chat_id=case["chat_id"], message_id=case["case_msg_id"],
                        )
                    except Exception:
                        pass
                gm_escalate_lateness(case["id"])
                logger.info("Lateness case %s escalated to owner", case["id"])
        except Exception as e:
            logger.error("lateness ladder action %s failed for case %s: %s",
                         action, case["id"], e)


async def _weekly_attendance_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Once a week (Monday, Phnom Penh): Opus digests the week's lateness + attendance
    notes and DMs the owner. Skips quietly when there's nothing to report."""
    now_pp = datetime.now(finance.PP_TZ)
    if now_pp.weekday() != 0:  # 0 = Monday
        return
    try:
        cases = gm_get_lateness_cases_since(7)
        concerns = gm_get_concerns_since("staffing", 7)
        if not cases and not concerns:
            logger.info("Weekly attendance digest: no data, skipping")
            return
        digest = await generate_attendance_digest(cases, concerns)
        if digest:
            header = "🗓️ Weekly attendance digest (%s)\n\n" % now_pp.strftime("%d %b %Y")
            await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=header + digest)
            logger.info("Weekly attendance digest sent (%d cases, %d concerns)",
                        len(cases), len(concerns))
    except Exception as e:
        logger.error("weekly attendance digest failed: %s", e)


def _resolve_clarification_response(chat_id: int, msg, text: str) -> dict | None:
    """Record a staff response to a GM clarification. Direct reply = answer (or 'checking');
    a loose 'we're checking' message while any clarification is open backs the ladder off.
    Returns {'clar', 'answer'} when a real answer was recorded (so the caller can AI-judge it)."""
    now = datetime.now(timezone.utc)
    if msg.reply_to_message:
        clar = gm_find_clarification_by_question_msg(chat_id, msg.reply_to_message.message_id)
        if clar and clar["status"] in ("open", "checking"):
            if clarify.is_checking_phrase(text):
                gm_set_clarification_checking(clar["id"], now + clarify.NUDGE_INTERVAL_CHECKING)
                return None
            gm_answer_clarification(clar["id"], text.strip())
            logger.info("Clarification %s answered by %s", clar["id"], clar.get("sender_name"))
            return {"clar": clar, "answer": text.strip()}
    # Not a direct reply — but "give us time / checking" while clarifications are open -> back off
    if clarify.is_checking_phrase(text):
        for clar in gm_get_active_clarifications_for_chat(chat_id):
            if clar["status"] == "open":
                gm_set_clarification_checking(clar["id"], now + clarify.NUDGE_INTERVAL_CHECKING)
    return None


async def _judge_clarification(context, clar: dict, answer: str) -> None:
    """Sonnet checks whether the staff reply actually resolves the clarification.
    If it doesn't add up, escalate to the owner with the answer + the reason."""
    verdict = await judge_clarification_answer(
        clar.get("question_text") or "", answer, clar["topic"],
    )
    if verdict.get("resolved", True):
        return
    body = clarify.escalation_text(
        clar["topic"], clar.get("chat_title") or str(clar["chat_id"]),
        clar.get("sender_name"), clar.get("question_text") or "", answer,
    )
    reason = verdict.get("reason", "")
    if reason:
        body += f"\nWhy flagged: {reason}"
    try:
        await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body)
        if clar.get("target_msg_id"):
            try:
                await context.bot.forward_message(
                    chat_id=config.OWNER_TELEGRAM_ID,
                    from_chat_id=clar["chat_id"], message_id=clar["target_msg_id"],
                )
            except Exception:
                pass
        gm_escalate_clarification(clar["id"])
        logger.info("Clarification %s judged not-resolved -> escalated", clar["id"])
    except Exception as e:
        logger.error("_judge_clarification escalate failed: %s", e)


async def _clarification_ladder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Every couple of minutes: nudge open clarifications on schedule, escalate at 2h."""
    now = datetime.now(timezone.utc)
    for clar in gm_get_active_clarifications():
        action, new_next = clarify.decide_ladder_action(
            clar["status"], clar["created_at"], now, clar.get("next_action_at"),
        )
        try:
            if action == "nudge":
                reply_to = clar.get("question_msg_id") or clar.get("target_msg_id")
                nudge = clarify.nudge_text(clar["topic"], clar.get("nudge_count", 0))
                try:
                    await context.bot.send_message(
                        chat_id=clar["chat_id"], text=nudge, reply_to_message_id=reply_to,
                    )
                except Exception:
                    await context.bot.send_message(chat_id=clar["chat_id"], text=nudge)
                gm_record_clarification_nudge(clar["id"], new_next)
                logger.info("Clarification %s nudged (count %s)", clar["id"], clar.get("nudge_count", 0) + 1)
            elif action == "escalate":
                body = clarify.escalation_text(
                    clar["topic"], clar.get("chat_title") or str(clar["chat_id"]),
                    clar.get("sender_name"), clar.get("question_text") or "",
                    clar.get("answer_text"),
                )
                await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body)
                if clar.get("target_msg_id"):
                    try:
                        await context.bot.forward_message(
                            chat_id=config.OWNER_TELEGRAM_ID,
                            from_chat_id=clar["chat_id"], message_id=clar["target_msg_id"],
                        )
                    except Exception:
                        pass
                gm_escalate_clarification(clar["id"])
                logger.info("Clarification %s escalated to owner", clar["id"])
        except Exception as e:
            logger.error("ladder action %s failed for clar %s: %s", action, clar["id"], e)


async def _check_report_receipt(msg, context) -> None:
    """Download a TWB REPORT photo, assess clarity, reply in-group if unclear."""
    try:
        photo_file = await msg.photo[-1].get_file()
        photo_bytes = bytes(await photo_file.download_as_bytearray())
        examples = receipt_get_answered_examples(msg.chat_id)
        result = await assess_receipt_photo(photo_bytes, past_examples=examples)

        if not result["is_receipt"]:
            return
        if result["is_clear"]:
            # A clear receipt arrived — resolves any pending "send again / clarify" in this chat.
            gm_resolve_open_clarifications(msg.chat_id, "receipt_clarity", "(clear receipt received)")
            return

        sender = msg.from_user.full_name if msg.from_user else "Staff"
        partial = result.get("readable_partial", "")

        if result.get("is_handwritten") and partial:
            question = f"Can you tell me what this says? I can see \"{partial}\" but hard to read."
            sent = await context.bot.send_message(
                chat_id=msg.chat_id,
                text=question,
                reply_to_message_id=msg.message_id,
            )
            receipt_save_clarification(msg.chat_id, msg.message_id, sent.message_id, question, sender)
            logger.info("Asked handwritten clarification for msg %s", msg.message_id)
        else:
            issues = result["issues"]
            if issues:
                issue_text = " and ".join(i.lower().rstrip(".") for i in issues[:2])
                reply = f"Please send this photo again — {issue_text}."
            else:
                reply = "Please send this photo again — not clear enough to record."
            sent = await context.bot.send_message(
                chat_id=msg.chat_id,
                text=reply,
                reply_to_message_id=msg.message_id,
            )
            question = reply
            logger.info("Unclear receipt reply sent for msg %s: %s", msg.message_id, issues)

        # Fold the receipt clarification into the ladder (nudge / escalate / record reason).
        gm_create_clarification(
            chat_id=msg.chat_id,
            chat_title=msg.chat.title,
            topic="receipt_clarity",
            question_msg_id=sent.message_id,
            target_msg_id=msg.message_id,
            question_text=question,
            sender_name=sender,
            context_ref=None,
        )
    except Exception as exc:
        logger.error("_check_report_receipt failed: %s", exc)


async def _report_clarification_reply(msg, context) -> None:
    """Handle staff reply to a GM clarification question — save the answer."""
    replied_to = msg.reply_to_message
    if not replied_to:
        return
    clarification = receipt_get_pending(msg.chat_id, replied_to.message_id)
    if not clarification:
        return
    answer = msg.text or msg.caption or ""
    if not answer.strip():
        return
    receipt_save_answer(clarification["id"], answer.strip())
    await context.bot.send_message(
        chat_id=msg.chat_id,
        text="Got it, thanks! ✓",
        reply_to_message_id=msg.message_id,
    )
    logger.info("Receipt clarification saved for photo_msg %s: %s", clarification["photo_msg_id"], answer[:60])


_PHOTO_WINDOW = 600  # seconds — how long to look back/forward for related photos
_msg_buffer: dict = defaultdict(lambda: deque(maxlen=30))   # (chat_id, uid) → recent messages
_concern_tracker: dict = defaultdict(list)                  # (chat_id, uid) → [(concern_id, ts)]


def _sender_key(msg):
    uid = msg.from_user.id if msg.from_user else 0
    return (msg.chat_id, uid)


def _prune_concerns(key: tuple) -> None:
    cutoff = time.time() - _PHOTO_WINDOW
    _concern_tracker[key] = [(cid, ts) for cid, ts in _concern_tracker[key] if ts > cutoff]


async def _live_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or update.channel_post
    if not msg:
        return

    now = time.time()
    key = _sender_key(msg)
    sender = msg.from_user.full_name if msg.from_user else (msg.chat.title or "Unknown")
    chat_id = msg.chat_id
    msg_id = msg.message_id
    has_media = bool(msg.photo or msg.document or msg.video)
    text = msg.text or msg.caption or ""

    # Always buffer this message for later correlation
    _msg_buffer[key].append((now, msg))

    # Persist to ops_messages so all groups accumulate history automatically
    try:
        media_type = ("photo" if msg.photo else
                      "video" if msg.video else
                      "document" if msg.document else None)
        sent_at = msg.date.isoformat() if msg.date else None
        sender_id = msg.from_user.id if msg.from_user else None
        chat_title = msg.chat.title or None
        save_ops_message(chat_id, msg_id, chat_title, sender_id, sender,
                         text or None, media_type, sent_at)
    except Exception as _e:
        logger.debug("ops_messages log failed: %s", _e)

    logger.debug("Group msg: chat_id=%s title=%r sender=%s", chat_id, msg.chat.title, sender)

    # Did staff respond to a GM clarification question? (any group) — records their reason,
    # then Sonnet checks whether the answer actually adds up.
    if text.strip():
        try:
            resolved = _resolve_clarification_response(chat_id, msg, text)
            if resolved:
                await _judge_clarification(context, resolved["clar"], resolved["answer"])
        except Exception as e:
            logger.error("clarification resolve failed: %s", e)

    # Supervisors / Management: lateness reports + pay-back follow-up ladder.
    if text.strip() and chat_id in (config.SUPERVISORS_CHAT_ID, config.MANAGEMENT_CHAT_ID):
        try:
            await _handle_lateness(context, msg, text, sender)
        except Exception as e:
            logger.error("lateness handling failed: %s", e)

    # TWB REPORT group: receipt photos, clarification replies, daily-report parsing
    if chat_id == config.DAILY_REPORT_CHAT_ID:
        if msg.reply_to_message and text.strip():
            await _report_clarification_reply(msg, context)
            return
        if msg.photo:
            await _check_report_receipt(msg, context)
            return
        # Text: if it's a daily books report, parse + store, correct math, flag big losses
        if text.strip():
            try:
                full = await _store_daily_report_if_any(msg, text)
                if full is not None:
                    await _maybe_correct_report(context, msg, full)
                    await _maybe_ask_lost(context, msg, full)
            except Exception as e:
                logger.error("daily report parse failed: %s", e)
        # Everything in REPORT is already in ops_messages — ingest only, no misrouted alerts.
        return

    # Photo with no triggering text — check if a recent concern needs it
    if has_media and not text.strip():
        _prune_concerns(key)
        if _concern_tracker[key]:
            try:
                await context.bot.send_message(
                    chat_id=config.OWNER_TELEGRAM_ID,
                    text="📎 Photo from %s — possibly related to concern above" % sender,
                )
                await context.bot.forward_message(
                    chat_id=config.OWNER_TELEGRAM_ID,
                    from_chat_id=chat_id,
                    message_id=msg_id,
                )
            except Exception as e:
                logger.error("Failed to forward related photo: %s", e)
        return

    if not text.strip():
        return

    concerns = await analyze_live_message(chat_id, msg_id, sender, text)
    for c in concerns:
        new_id = gm_save_concern(
            source_chat_id=chat_id,
            source_msg_key=c["source_msg_key"],
            concern_type=c["concern_type"],
            severity=c["severity"],
            sender_name=c.get("sender_name"),
            description=c["description"],
        )
        if new_id:
            try:
                # Collect file_ids from buffer (this message + nearby same-sender photos)
                cutoff = now - _PHOTO_WINDOW
                file_ids = []
                for ts, bm in list(_msg_buffer[key]):
                    if ts < cutoff:
                        continue
                    if bm.photo:
                        file_ids.append(bm.photo[-1].file_id)
                    elif bm.video:
                        file_ids.append(bm.video.file_id)
                # Deduplicate preserving order
                seen_fids = set()
                unique_fids = []
                for fid in file_ids:
                    if fid not in seen_fids:
                        seen_fids.add(fid); unique_fids.append(fid)

                tg_msg_id = await _send_concern_with_photos(
                    context.bot, {**c, "id": new_id}, unique_fids
                )
                gm_mark_sent(new_id, tg_msg_id)
                _concern_tracker[key].append((new_id, now))
                logger.info("Live concern sent: %s from %s in %s", c["concern_type"], sender, chat_id)
            except Exception as e:
                logger.error("Failed to send live concern: %s", e)

            # Voice a matching approved policy live (owner-gated; preview until enabled).
            await _maybe_policy_reply(context, msg, c["concern_type"], sender, text)


# ─── Application builder ──────────────────────────────────────────────────────

def build_app() -> Application:
    if not config.GM_BOT_TOKEN:
        raise ValueError("GM_BOT_TOKEN not set in config/secrets")

    app = Application.builder().token(config.GM_BOT_TOKEN).build()

    # ConversationHandler wraps the teach + proposal-refine flows
    teach_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern=r"^gm:"),
            CallbackQueryHandler(gmprop_callback, pattern=r"^gmprop:"),
        ],
        states={
            TEACH_WAITING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, teach_receive),
                CommandHandler("cancel", teach_cancel),
                MessageHandler(filters.COMMAND, _conv_interrupt),
            ],
            REFINE_WAITING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, refine_receive),
                CommandHandler("cancel", refine_cancel),
                MessageHandler(filters.COMMAND, _conv_interrupt),
            ],
            CONFLICT_WAITING: [
                CallbackQueryHandler(conflict_callback, pattern=r"^gmprop:conflict:"),
                CommandHandler("cancel", refine_cancel),
                MessageHandler(filters.COMMAND, _conv_interrupt),
            ],
            CONFLICT_EXPLAIN_WAITING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, conflict_explain_receive),
                CommandHandler("cancel", refine_cancel),
                MessageHandler(filters.COMMAND, _conv_interrupt),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", teach_cancel),
            MessageHandler(filters.COMMAND, _conv_interrupt),
        ],
        per_message=False,
        per_chat=True,
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("check",     cmd_check))
    app.add_handler(CommandHandler("review",    cmd_review))
    app.add_handler(CommandHandler("proposals", cmd_proposals))
    app.add_handler(CommandHandler("approved",  cmd_approved))
    app.add_handler(CommandHandler("points",    cmd_points))
    app.add_handler(CommandHandler("pending",   cmd_pending))
    app.add_handler(CommandHandler("staff",     cmd_staff))
    app.add_handler(CommandHandler("rules",     cmd_rules))
    app.add_handler(CallbackQueryHandler(staff_button_callback, pattern=r"^ss:"))
    app.add_handler(teach_conv)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, _live_group_handler))

    # Schedule analysis: every day at 08:00 Phnom Penh time (01:00 UTC)
    app.job_queue.run_daily(
        _daily_analysis_job,
        time=__import__("datetime").time(hour=1, minute=0),
        name="gm_daily_analysis",
    )
    # Also run every 4 hours to catch things during the day
    app.job_queue.run_repeating(
        _daily_analysis_job,
        interval=4 * 3600,
        first=60,
        name="gm_periodic_analysis",
    )
    # Auto-skip proposals that the owner hasn't acted on in 24 hours
    app.job_queue.run_repeating(
        _auto_skip_proposals_job,
        interval=3600,
        first=300,
        name="gm_auto_skip_proposals",
    )
    # Clarification escalation ladder: nudge / escalate on schedule
    app.job_queue.run_repeating(
        _clarification_ladder_job,
        interval=120,
        first=90,
        name="gm_clarification_ladder",
    )
    # Lateness / pay-back ladder: 30 min -> ask group, 24 h -> owner
    app.job_queue.run_repeating(
        _lateness_ladder_job,
        interval=120,
        first=100,
        name="gm_lateness_ladder",
    )
    # Weekly attendance/AL digest (Opus): runs daily at 08:00 PP (01:00 UTC),
    # the job itself only fires on Mondays.
    app.job_queue.run_daily(
        _weekly_attendance_digest_job,
        time=__import__("datetime").time(hour=1, minute=30),
        name="gm_weekly_attendance_digest",
    )

    return app
