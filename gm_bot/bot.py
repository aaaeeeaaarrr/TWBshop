"""
GM Manager TWB bot — private digest to owner.
Sends operational concerns with [✓ All good] [🚨 Real issue] [📚 Teach bot] buttons.
Does NOT post to any staff group. Owner-only, private chat.
"""
import asyncio
import logging
import random
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
    gm_get_unsent_concerns, gm_mark_sent, gm_review_concern, gm_save_concern,
    gm_get_concern_by_msg_id, gm_save_rule, init_gm_db,
    gm_get_related_photos, gm_get_unsent_by_sender, gm_get_pending_by_sender,
    gm_get_unreviewed_by_sender, gm_get_unreviewed_by_sender_name,
    gm_save_proposal, gm_get_proposal, gm_get_draft_proposals,
    gm_approve_proposal, gm_reject_proposal, gm_update_proposal_solution,
    gm_set_proposal_msg_id, gm_get_points_summary, _db,
    gm_get_approved_policy_for_type,
    gm_skip_proposal, gm_get_stale_draft_proposals, gm_purge_lower_ranked_drafts,
    gm_append_refinement_note, save_ops_message, al_apply_due_deductions,
    att_get_session, att_check_in, att_record_ping,
    late_declare, payback_open_debt, payback_add_debt, payback_credit, payback_book, payback_all_open,
    al_create_request, al_get_request, al_add_approval, al_get_approvals, al_set_status,
    al_approve_and_deduct, al_reject,
    al_pending_requests, al_deduct, points_record, points_seed_catalogue,
    al_leave_days_set, staff_absent_dates, payback_bookings_due_reminder, payback_mark_reminded,
    dayoff_set_override, dayoff_override_for, swap_create, swap_get, swap_set_partner,
    swap_add_senior_vote, swap_set_status, swap_approve_claim,
    ot_bank_balance, ot_bank_add, ot_buyback_book,
    sick_create, sick_get, sick_set, sick_provisional_open, sick_family_days_used,
    special_leave_create, special_leave_set_days, special_leave_get,
    no_show_record, no_show_reverse, lateness_dates,
    set_att_test, att_test_on, attendance_testreset, attendance_test_counts, attendance_testseed,
    init_receipt_clarifications_db, receipt_save_clarification,
    receipt_get_pending, receipt_save_answer, receipt_get_answered_examples,
    init_gm_finance_db, save_daily_report, get_daily_reports_for_day, gm_get_state, gm_set_state,
    save_report_doc, get_report_docs,
    init_gm_clarifications_db, gm_create_clarification, gm_get_active_clarifications,
    gm_get_active_clarifications_for_chat, gm_find_clarification_by_question_msg,
    gm_record_clarification_nudge, gm_set_clarification_checking,
    gm_add_clarification_nudge_msg, gm_get_vendor_rules, gm_set_vendor_rule,
    gm_answer_clarification, gm_escalate_clarification, gm_resolve_open_clarifications,
    init_gm_lateness_db, gm_create_lateness_case, gm_get_open_lateness_cases,
    gm_get_open_lateness_in_chat, gm_mark_lateness_group_asked, gm_resolve_lateness,
    gm_escalate_lateness, gm_get_staff_uid,
    gm_add_finance_alias, gm_get_finance_aliases,
    gm_get_lateness_cases_since, gm_get_concerns_since,
    init_gm_leave_db, gm_create_leave_event, gm_link_leave_clarification,
    gm_get_sales_history,
    stock_get_items, stock_apply_sheet_reading, stock_days_since_last_count,
    staff_all, staff_get_by_uid, staff_find_by_name, staff_mark_ex,
)
from shared.ai_client import (
    generate_proposals, refine_proposal_with_ai, refine_proposal_resolve_conflict,
    GM_PROPOSALS_MODEL, assess_receipt_photo, judge_clarification_answer,
    gm_compose_reply, detect_lateness_report, extract_payback_day,
    extract_daily_report_ai, generate_attendance_digest, narrate_attendance_week,
    categorize_reasons, detect_leave_request,
    classify_stock_photo, read_stock_sheet, read_medical_paper, generate_callout,
)
from gm_bot.analyzer import run_analysis, analyze_live_message
from gm_bot import finance, clarify, lateness, mentions, reconcile, sales, stock
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
        # staff roll-call: pressing Start binds + greets them (silence for strangers).
        # When attendance is LIVE, an active TWB staffer instead opens their own attendance menu.
        if update.effective_chat and update.effective_chat.type == "private":
            uid = update.effective_user.id
            rec = staff_get_by_uid(uid) if _attendance_live() else None
            if rec and rec.get("status") == "active" and rec.get("org") == "TWB":
                from gm_bot import attendance_ui
                if len(rec.get("telegram_ids", [])) > 1:
                    from shared.database import staff_bind_uid
                    staff_bind_uid(rec["id"], uid)
                await attendance_ui.open_live_menu(update, context, rec)
                return
            from gm_bot import rollcall
            await rollcall.handle_staff_private(update, context)
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
        # Multiple senders matched — list them. (NO local import here: a function-local import
        # makes the name function-local EVERYWHERE, so the earlier no-args branch crashed with
        # UnboundLocalError — the module-level import already provides it. Prod bug, Jun 10.)
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


async def _send_reconciliation(context, business_day: str) -> None:
    """Level-1 reconciliation (session 28, owner-preview): photos vs typed report.
    Sent privately to the OWNER on every final report — he learns the baseline first."""
    try:
        rows = get_daily_reports_for_day(business_day)
        mid = next((r for r in reversed(rows) if r.get("report_kind") == "mid"), None)
        final = next((r for r in reversed(rows) if r.get("report_kind") == "final"), None)
        docs = get_report_docs(business_day)
        checks = reconcile.checks_for_day(mid, final, docs)
        if not checks:
            return
        await context.bot.send_message(
            chat_id=config.OWNER_TELEGRAM_ID,
            text=reconcile.format_summary(str(business_day), checks),
        )
    except Exception as e:
        logger.error("reconciliation failed for %s: %s", business_day, e)


async def _capture_voice_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """A staffer on a reason-wait who sends voice / photo / sticker INSTEAD of typing. Owner decision
    (Jun 13, menu-patterns Law 6 — F1): the old code said "Got it 👍 thank you", forwarded the media,
    and NEVER submitted — the request silently vanished. Now we REFUSE the non-text input and KEEP the
    prompt armed, so their next typed line still submits. Returns True only when an armed reason pend
    existed (so the photo router doesn't then treat it as a sick-paper). Test-mode aware so it's
    walkable: owner test pend lives in user_data; a live staffer's in flow_state."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return False
    armed = False
    if _att_test_mode() and context.user_data.get("att_test_pending"):
        armed = True
    elif _attendance_live():
        from shared.database import flow_load_or_expired
        active, expired = flow_load_or_expired(user.id)
        if active and str(active.get("step", "")).endswith("reason"):
            armed = True
        elif expired and expired.get("flow") == "att_pending":
            # A6: the media arrived AFTER the prompt expired — don't let it (and the F3 honesty) vanish.
            ep = expired.get("data") or {}
            await _expiry_nudge(context, msg.chat_id, ep.get("_summary") or "",
                                old_chat=ep.get("_prompt_chat"), old_msg=ep.get("_prompt_msg"))
            return True
    if not armed:
        return False
    await msg.reply_text(
        "🎤 I can't read a voice note / photo here — please type your reason in one line.\n"
        "🎤 ខ្ញុំមិនអាចអានសារសំឡេង/រូបភាពនៅទីនេះបានទេ — សូមវាយមូលហេតុជាអក្សរ ១បន្ទាត់។")
    return True


async def _private_photo_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Private photo: sick-PAPERS first, then the voice/photo-on-a-reason-prompt refusal (owner,
    Jun 13). A photo is almost always a DOCUMENT, not a 'reason' — and paper-capture is DB-keyed (the
    open sick case), so it works regardless of menu state, even after a menu is reopened. Only if it's
    NOT papers-for-an-open-case do we fall through to refuse it as a non-text reason."""
    try:
        if await _handle_sick_paper(update, context):
            return
        await _capture_voice_reason(update, context)
    except Exception as e:
        logger.error("private photo handling failed: %s", e)


async def _private_voice_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Private voice/sticker: reason capture (gated)."""
    try:
        await _capture_voice_reason(update, context)
    except Exception as e:
        logger.error("voice reason handling failed: %s", e)


async def _expiry_nudge(context: ContextTypes.DEFAULT_TYPE, chat_id: int, detail: str = "",
                        old_chat=None, old_msg=None) -> None:
    """Law 6/8 (F2/F3): an armed state expired or a dead tap landed → PUSH a FRESH message headed
    'NOT CONFIRMED — TRY AGAIN' (caps EN + bold KH) carrying what expired, and remove the stale card
    (delete ≤48h, else strip its buttons). A new message push-notifies; a silent in-place edit would
    be missed (owner, Jun 13). Best-effort throughout."""
    if old_chat and old_msg:
        try:
            await context.bot.delete_message(old_chat, old_msg)
        except Exception:
            try:
                await context.bot.edit_message_reply_markup(chat_id=old_chat, message_id=old_msg,
                                                            reply_markup=None)
            except Exception:
                pass
    body = "❗ NOT CONFIRMED — TRY AGAIN\n❗ <b>មិនទាន់បានបញ្ជាក់ — សូមធ្វើម្ដងទៀត</b>"
    detail = (detail or "").strip()
    if detail:
        body += "\n\n" + detail
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📋 Open menu · បើក menu", callback_data="att:menu")]])
    try:
        await context.bot.send_message(chat_id, body, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:    # parse_mode can choke if the quoted detail has stray markup — retry plain
            await context.bot.send_message(chat_id, body.replace("<b>", "").replace("</b>", ""),
                                           reply_markup=kb)
        except Exception:
            pass


async def _private_location_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Staff check-in (gated/live) takes precedence; otherwise the owner-only test handler."""
    try:
        if await _handle_staff_location(update, context):
            return
    except Exception as e:
        logger.error("staff location handling failed: %s", e)
    from gm_bot import attendance_ui
    await attendance_ui.handle_location_test(update, context)


def _attendance_live() -> bool:
    """MASTER SWITCH (owner gate): until set 'true', the check-in engine touches NO staff —
    no scheduled prompts, no location processing. Flip via gm_set_state('attendance_live','true')
    only after role-play sign-off + staff briefed. Default OFF."""
    return gm_get_state("attendance_live") == "true"


def _att_test_mode() -> bool:
    """TEST MODE: owner role-plays the whole system alone. Every message routes to the owner;
    every write is is_test-tagged; real balances untouched. Never messages a real staffer."""
    return gm_get_state("attendance_test_mode") == "true"


def _att_active() -> bool:
    """A flow runs if it's live OR in test mode (test never reaches real staff)."""
    return _attendance_live() or _att_test_mode()


def _now_pp() -> datetime:
    """Current time in Phnom-Penh tz — EXCEPT in test mode, where an owner-set frozen 'pretend now'
    (`att_test_now`, ISO) overrides it. This is the one knob that lets time-conditioned behaviour
    (payback ladder days, the OT-shield/PB deadlines, AL accrual, sick night-nudges, no-show sweep)
    be rehearsed in /test without waiting real days. NEVER overrides in live mode — real staff always
    run on the wall clock. Set via /testclock; clear with /testclock off."""
    real = datetime.now(finance.PP_TZ)
    if _att_test_mode():
        iso = gm_get_state("att_test_now")
        if iso:
            try:
                dt = datetime.fromisoformat(iso)
                return dt if dt.tzinfo else dt.replace(tzinfo=finance.PP_TZ)
            except Exception:
                pass
    return real


def _today_pp():
    """Today's date in PP tz, honouring the test clock (see _now_pp)."""
    return _now_pp().date()


def _record_dead_tap(data: str) -> None:
    """Count unhandled/expired button taps (gm_state, per day, time-stamped samples) — the daily
    auto-audit reads these, so a dead button can never stay invisible again (the payback-picker
    lesson, Jun 11: a silent return writes nothing → no net could see it)."""
    try:
        import json as _json
        key = "dead_taps:%s" % _today_pp().isoformat()
        cur = gm_get_state(key)
        rec = _json.loads(cur) if cur else {"n": 0, "samples": []}
        rec["n"] += 1
        sample = "%s %s" % (_now_pp().strftime("%H:%M"), data or "?")
        if not any(s.split(" ", 1)[-1] == (data or "?") for s in rec["samples"]):
            rec["samples"] = (rec["samples"] + [sample])[-5:]
        gm_set_state(key, _json.dumps(rec))
    except Exception as e:
        logger.error("dead-tap record failed: %s", e)


_DEAD_TAP_LAST_DM = 0.0


async def _dead_tap_alarm(context, data: str, uid: int | None) -> None:
    """INSTANT owner DM on a dead tap (owner, Jun 11) — time + who + which button, so the source
    is suspectable immediately. Throttled to one per 30 min (a confused staffer may tap 5×);
    every tap is still recorded for the daily audit either way."""
    global _DEAD_TAP_LAST_DM
    import time as _time
    now_t = _time.time()
    if now_t - _DEAD_TAP_LAST_DM < 1800:
        return
    _DEAD_TAP_LAST_DM = now_t
    who = "?"
    if uid:
        s = staff_get_by_uid(uid)
        who = ((s.get("call_name") or s["canonical_name"]) if s
               else ("owner" if uid == config.OWNER_TELEGRAM_ID else str(uid)))
    try:
        await context.bot.send_message(config.OWNER_TELEGRAM_ID,
            "🔘 Dead button at %s — %s tapped '%.40s' and nothing could handle it.\n"
            "(recorded for the daily audit; more in the next 30 min are logged only)"
            % (_now_pp().strftime("%H:%M"), who, data or "?"))
    except Exception:
        pass


async def _expired_toast(query, context=None, uid: int | None = None) -> None:
    """In-handler bail (stale card, missing record, unresolved tapper): a non-destructive popup —
    the message stays intact for whoever it's still valid for — recorded + instant owner alarm."""
    data = getattr(query, "data", "") or "?"
    _record_dead_tap(data)
    if context is not None:
        await _dead_tap_alarm(context, data, uid)
    try:
        await query.answer("⏳ Expired — try again · ផុតកំណត់ — សាកម្តងទៀត", show_alert=True)
    except Exception:
        pass


async def _expired_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CATCH-ALL (registered LAST): a tapped button NO handler recognises = an orphaned/legacy
    message → collapse it into an honest expired note WITH a recovery button (the menu is the
    root of every flow), record the tap, and alarm the owner instantly."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    _record_dead_tap(query.data or "?")
    await _dead_tap_alarm(context, query.data or "?",
                          update.effective_user.id if update.effective_user else None)
    try:
        await query.edit_message_text(
            "⏳ Expired message — please start again.\n"
            "⏳ សារនេះផុតកំណត់ហើយ — សូមចាប់ផ្តើមម្តងទៀត។",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                "📋 Open menu · បើក menu", callback_data="att:menu")]]))
    except Exception:
        pass


def _msg_time_pp(update, fallback: datetime) -> datetime:
    """The Telegram-stamped time of this update, in PP tz. Queued updates (bot down/restarting,
    long-poll backlog) must be judged by when the STAFFER acted, not when we got to process them —
    Telegram queues up to 24h and every update carries its original date (edits carry edit_date).
    In test mode the test clock (the fallback) wins, so /testclock rehearsals keep working."""
    if _att_test_mode():
        return fallback
    m = update.edited_message or update.message
    dt = getattr(m, "edit_date", None) or getattr(m, "date", None)
    if not dt:
        return fallback
    try:
        return dt.astimezone(finance.PP_TZ)
    except Exception:
        return fallback


_TEST_FORCE_RUN = False   # True only while /testrun fires a job body on demand (test mode)


def _job_gate(live_only: bool = False) -> bool:
    """Whether a scheduled job's body should execute. Normally live-only or live+test per the job.
    During an explicit /testrun in test mode it forces ON, so the owner can watch a time-driven job
    fire on demand against the test clock (writes are is_test, messages route to the owner)."""
    if _TEST_FORCE_RUN and _att_test_mode():
        return True
    return _attendance_live() if live_only else _att_active()


async def _att_send(context, to_uid, role: str, to_name: str, text: str,
                    kb=None, group: bool = False, parse_mode: str | None = None):
    """THE single outbound chokepoint for attendance messages (rule: test == prod, route only).
    - test mode: deliver to the OWNER, labeled [→ role: name], buttons kept functional so the
      owner taps as that role.
    - live: deliver to the real recipient (to_uid, or the Supervisors group when group=True)."""
    from gm_bot.attendance import strip_khmer
    if _att_test_mode():
        # everything routes to the OWNER in test → English-only by default. /testkhmer on keeps the
        # full bilingual body so the owner can proof-read the real Khmer staff will see.
        prefix = "🧪 [→ %s%s]\n" % (role, (": " + to_name) if to_name else "")
        full = prefix + text
        body = full if gm_get_state("att_test_khmer") == "true" else strip_khmer(full)
        try:
            return await context.bot.send_message(config.OWNER_TELEGRAM_ID, body,
                                                  reply_markup=kb, parse_mode=parse_mode)
        except Exception as e:
            logger.error("att_send(test) failed: %s", e)
            return None
    target = config.SUPERVISORS_CHAT_ID if group else to_uid
    if not target:
        return None
    # the owner reads English only; staff/groups get the full bilingual text
    body = strip_khmer(text) if target == config.OWNER_TELEGRAM_ID else text
    try:
        return await context.bot.send_message(target, body, reply_markup=kb, parse_mode=parse_mode)
    except Exception as e:
        logger.error("att_send to %s failed: %s", target, e)
        return None


async def _checkin_scheduler_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Per-minute: fire due check-in events (T−10/T0/T+5/check-out/leave-early) to staff.
    GATED: returns immediately unless attendance_live. Suppresses prompts for staff already
    checked in (T0/T+5) / checked out. State + sessions in DB so restarts are safe."""
    if not _job_gate(live_only=True):
        return
    from gm_bot import attendance_ui as ui, checkin as ci
    now_pp = _now_pp()
    now_min = now_pp.hour * 60 + now_pp.minute
    try:
        events = ui.compute_day_events(now_pp.date())   # schedule-driven, skips day-off/AL/Tyty/Delis
    except Exception as e:
        logger.error("checkin scheduler compute failed: %s", e)
        return
    # Redefined shifts (session 31): compute_day_events already fires this roster's prompts at the
    # REDEFINED [start,end] for any approved shift_change — incl. an extended/OT end — so the old
    # ot_now_end_times "extend the shift" pass is gone; the redefined checkout rides the event stream.
    # Every event carries its SHIFT-START date (sd): an overnight checkout fires today but its
    # session + redefine live under YESTERDAY — lookups and the checkout arm must use sd, not today.
    from shared.database import flow_save
    for minute, name, label, text, sd in events:
        if not ci.is_due(minute, now_min):
            continue
        staff = next((s for s in staff_all("active")
                      if (s.get("call_name") or s["canonical_name"]) == name), None)
        if not staff or not (staff.get("telegram_ids") or []):
            continue
        uid = staff["telegram_ids"][0]
        sess = att_get_session(staff["id"], sd)
        checked_in = bool(sess and sess.get("checked_in_at"))
        checked_out = bool(sess and sess.get("checked_out_at"))
        # suppression: once checked in, drop T0/T+5 prompts; once checked out, drop the close prompts
        if checked_in and (label.startswith("T0") or label.startswith("T+")):
            continue
        if checked_out and (label.startswith("check-out") or label.startswith("leave-early")):
            continue
        # AUTO-CHECKOUT (spec §3.7): at shift end, if their live share is still running IN-ZONE we
        # know they were here to the last minute — close silently + settle OT, no request, no
        # leave-early chase (the now-set checked_out_at suppresses those on the next ticks).
        if label.startswith("check-out") and checked_in and not checked_out:
            from shared.database import att_last_ping, att_check_out
            if ci.can_auto_checkout(att_last_ping(staff["id"]), now_pp):
                att_check_out(staff["id"], sd, now_pp.isoformat())
                banked, new_bal = _settle_redefined_shift(staff, sd, now_pp)
                await _att_send(context, uid, "Staff", name, ui._CO_DONE)
                if banked > 0:
                    await _offer_buyback(context, staff, new_bal, uid, banked)
                continue
        await _att_send(context, uid, "Staff", name, text)
        # arm check-out capture: next in-zone share while this is set = checked out (60-min window).
        # sd (not today) → the checkout write + the OT settle bind to the shift's real session.
        if label.startswith("check-out"):
            flow_save(uid, "checkout", "await", {"shift_date": sd}, ttl_min=60)


def _sc_taken_dates(staff_id: int) -> set[str]:
    """Upcoming dates already holding an approved redefine — never offer a payback slot there."""
    try:
        from shared.database import shift_change_upcoming_dates
        return shift_change_upcoming_dates(staff_id, _today_pp().isoformat())
    except Exception:
        return set()


def _pb_remaining(staff: dict, balance: int) -> int:
    """The bookable remainder of an open debt (payback.unbooked) — the balance minus extension
    already covered by approved upcoming redefines. Computed FRESH at every surface (picker,
    offer, the book tap itself) so a stale button can never over-book (owner find, Jun 11:
    book-and-book-again was minting OT from the surplus)."""
    from gm_bot import payback as pb
    from shared.database import ot_pending_extension_min
    try:
        pend = ot_pending_extension_min(staff["id"], _today_pp().isoformat())
    except Exception:
        pend = 0
    return pb.unbooked(balance, pend)


_PB_FULLY_BOOKED = ("Your pay-back time is already fully booked ✓ Just work the booked times.\n"
                    "ម៉ោងសងវិញរបស់ប្អូនបានកក់រួចទាំងអស់ហើយ ✓ សូមមកធ្វើតាមម៉ោងដែលបានកក់។")


# The stored `who` is an English key (child/spouse/parent/family); dropped raw into a Khmer
# sentence it reads half-English ("សង្ឃឹមថា child របស់ប្អូន…"). Map to a BARE Khmer noun —
# no possessive, because the templates already supply របស់ប្អូន / របស់អ្នក.
_WHO_KH_BARE = {"child": "កូន", "spouse": "ប្តី/ប្រពន្ធ", "parent": "ឪពុក/ម្តាយ",
                "family member": "សមាជិកគ្រួសារ", "family": "សមាជិកគ្រួសារ"}


def _who_kh(who: str) -> str:
    return _WHO_KH_BARE.get((who or "").strip().lower(), who or "")


def _payback_slot_keyboard(staff: dict, balance: int):
    """Build payback slot buttons sized to `balance` = the REMAINING-to-book minutes (callers
    clamp via _pb_remaining): before/after each of the next working days + day-off option +
    partial buttons. Working-day slots cap so the day's TOTAL work time never exceeds 15h
    (owner rule, Jun 11); dates already carrying an approved redefine are skipped (a second
    redefine would supersede the first). callback att:pb:book:{date}:{start}:{end}:{mins}."""
    from gm_bot import payback as pb
    from gm_bot.attendance import to_min
    ws, we = to_min(staff.get("work_start")), to_min(staff.get("work_end"))
    if ws is None or we is None or balance <= 0:
        return None
    from gm_bot import coverage as cov
    from gm_bot.attendance import to_min
    leave = al_leave_days_set(staff["id"])
    leave_isos = set(leave)
    taken = _sc_taken_dates(staff["id"])
    days = [d for d in pb.working_days_ahead(staff.get("day_off"), leave_isos,
                                             _today_pp(), 7, 3) if d.isoformat() not in taken]
    roster = [s for s in staff_all("active") if s.get("org") == "TWB"]
    expertise = staff.get("expertise") or []
    normal_len = ((we - ws) % 1440) or 1440
    slot_size = min(balance, pb.day_ext_cap(normal_len))   # 15h-total-day cap (owner rule)
    # build (score, button) then sort neediest-first (the shop's most-needed times rise to the top)
    scored = []
    for d in (days if slot_size > 0 else []):
        wd = d.strftime("%a")
        for label, s_min, e_min in pb.slot_windows(ws, we, slot_size):
            score = cov.slot_score(expertise, s_min, e_min, wd, roster, set(), to_min)
            txt = "%s %s %s-%s%s" % (("🌅" if label == "before" else "🌙"),
                                     d.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min),
                                     " ⚠" if score >= 2 else "")
            scored.append((score, [InlineKeyboardButton(
                txt, callback_data="att:pb:book:%s:%d:%d:%d" % (d.isoformat(), s_min, e_min, slot_size))]))
    scored.sort(key=lambda t: -t[0])
    rows = [btn for _score, btn in scored]
    # + ONE day-off option (owner spec, now wired): the neediest slot WITHIN their regular shift hours
    # on an upcoming day off (a night-shift person gets a night window, never a 5am call). Natural cap
    # = a shift-length (dayoff_windows sizes the window to min(balance, shift span)).
    do_scored = []
    for do in pb.dayoff_dates_ahead(staff.get("day_off"), leave_isos,
                                    _today_pp(), 14):
        if do.isoformat() in taken:
            continue
        for s_min, e_min in pb.dayoff_windows(ws, we, balance):
            sc = cov.slot_score(expertise, s_min, e_min, do.strftime("%a"), roster, set(), to_min)
            do_scored.append((sc, do, s_min, e_min))
    # owner spec (Jun 11): the TOP-3 neediest day-off windows, all within their own shift hours
    # ("we choose the best hours for us"); full-shift debt naturally yields the whole shift.
    do_scored.sort(key=lambda t: -t[0])
    for _sc, do, s_min, e_min in do_scored[:3]:
        mins = (e_min - s_min) % 1440 or balance
        txt = "🛌 %s %s-%s · day off" % (do.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min))
        rows.append([InlineKeyboardButton(
            txt, callback_data="att:pb:book:%s:%d:%d:%d" % (do.isoformat(), s_min, e_min, mins))])
    # partial options — 1h/2h/3h (owner)
    for part in (60, 120, 180):
        if part < balance:
            rows.append([InlineKeyboardButton("Pay %dh only · សងតែ %dh" % (part // 60, part // 60),
                                              callback_data="att:pb:part:%d" % part)])
    return InlineKeyboardMarkup(rows) if rows else None


def _fmt_min(m: int) -> str:
    m %= 1440
    h, mm = divmod(m, 60)
    sfx = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return ("%d:%02d%s" % (h12, mm, sfx)) if mm else ("%d%s" % (h12, sfx))


def _create_payback_redefine(staff: dict, slot_date: str, s_min: int, e_min: int) -> None:
    """A booked payback slot IS a shift redefine (owner unification): the existing engine then
    does everything — T−10 at the new start, lateness vs the new start, checkout settle credits
    the slot minutes against the debt (partial naturally = clamped worked time). Best-effort:
    a failure here never blocks the booking confirmation."""
    try:
        from datetime import date as _d
        from gm_bot import payback as pb
        from gm_bot.attendance import to_min
        from shared.database import shift_change_autoapprove
        ws, we = to_min(staff.get("work_start")), to_min(staff.get("work_end"))
        off = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5,
               "sun": 6}.get((staff.get("day_off") or "")[:3].lower())
        is_dayoff = off is not None and _d.fromisoformat(slot_date).weekday() == off
        win = pb.redefine_window(ws, we, is_dayoff, s_min, e_min)
        if win:
            shift_change_autoapprove(staff["id"], slot_date, win[0], win[1], win[2],
                                     "payback slot")
    except Exception as e:
        logger.error("payback redefine create failed: %s", e)


async def _offer_payback(context, staff: dict, balance: int, uid: int,
                         late_min: int | None = None) -> None:
    """Send the payback slot picker, sized to the REMAINING-to-book minutes (never the raw
    balance — already-booked extension covers part of the debt). On a FRESH late arrival
    (late_min given) the check-in verdict is COMBINED into this one message — so the reason
    ('X late, counts as pay-back') and the picker can't be read separately. Other contexts
    (re-offers/ladder) get the plain 'You owe X' header. Fully booked → no picker, just the
    honest 'already booked' line."""
    from gm_bot.attendance_ui import _hm
    remaining = _pb_remaining(staff, balance)
    kb = _payback_slot_keyboard(staff, remaining)
    if remaining <= 0 or kb is None:
        # everything is already covered by booked time — no picker, honest line instead
        head = ("Checked in ✓ — %s late (counts as pay-back).\n"
                "ចុះវត្តមានរួច ✓ — យឺត %s (រាប់ជាម៉ោងសងវិញ)។"
                % (_hm(late_min), _hm(late_min))) if late_min is not None else \
               ("You owe %s.\nប្អូននៅត្រូវសង %s។" % (_hm(balance), _hm(balance)))
        await _att_send(context, uid, "Staff", staff.get("call_name") or staff["canonical_name"],
                        head + "\n" + _PB_FULLY_BOOKED)
        return
    if late_min is not None:
        text = ("Checked in ✓ — %s late (counts as pay-back). Pick when to work it off — the "
                "times we need you most:\n"
                "ចុះវត្តមានរួច ✓ — យឺត %s (រាប់ជាម៉ោងសងវិញ)។ "
                "សូមជ្រើសពេលធ្វើសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖"
                % (_hm(late_min), _hm(late_min)))
    else:
        text = ("You owe %s. Pick when to work it off — these are the times we need you most:\n"
                "ប្អូននៅត្រូវសង %s។ សូមជ្រើសពេលធ្វើសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖"
                % (_hm(balance), _hm(balance)))
    if remaining < balance:
        text += ("\n(%s booked already · បានកក់រួច %s — %s left to book · នៅសល់ %s ត្រូវកក់)"
                 % (_hm(balance - remaining), _hm(balance - remaining),
                    _hm(remaining), _hm(remaining)))
    await _att_send(context, uid, "Staff", staff.get("call_name") or staff["canonical_name"],
                    text, kb=kb)


async def _handle_staff_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Real staff check-in via live location. GATED. Returns True if handled (so the test
    handler doesn't also fire). Records the ping (secret feed) always-on; on first in-zone
    fix during a scheduled shift → check-in + verdict."""
    if not _attendance_live():
        return False
    msg = update.message or update.edited_message
    user = update.effective_user
    if not msg or not msg.location or not user:
        return False
    staff = staff_get_by_uid(user.id)
    if not staff or staff.get("status") != "active" or staff.get("org") != "TWB":
        return False
    if update.edited_message:   # live-share lifecycle update (movement/stop) — record silently
        pass
    loc = msg.location
    from gm_bot import attendance as att, checkin as ci, attendance_ui as ui
    in_zone = att.in_work_zone(loc.latitude, loc.longitude)
    # Judge by the TELEGRAM-STAMPED time, not processing time: if the bot was down/restarting,
    # queued updates arrive late — a punctual staffer must never be marked late (and a stale ping
    # must never look fresh to auto-checkout) because of OUR downtime.
    now_pp = _msg_time_pp(update, _now_pp())
    # find today's (or last night's overnight) shift this check-in belongs to
    shift_date = now_pp.date().isoformat()
    ws = att.to_min(staff.get("work_start"))
    # the ONE resolver decides the shift start: a redefine moves it (lateness judged vs the REDEFINED
    # start); leave (AL/sick) yields no redefined start so the normal work_start stands.
    dec = ui.resolve_day(staff, shift_date)
    if dec["working"] and dec.get("start_min") is not None:
        ws = int(dec["start_min"]) % 1440
    if ws is None:
        return True
    # A STOPPED live-share (edited update, live_period gone) is NOT presence proof — record it
    # in-zone=False so the auto-checkout never trusts a share the staffer just turned off.
    is_stop = ci.is_share_stop(bool(update.edited_message), getattr(loc, "live_period", None))
    try:
        att_record_ping(staff["id"], loc.latitude, loc.longitude, in_zone and not is_stop,
                        now_pp.isoformat())
    except Exception:
        pass
    # check-OUT capture: if a check-out request armed this, an in-zone share closes the shift
    from shared.database import flow_load, flow_clear, att_check_out
    fs = flow_load(user.id)
    if fs and fs.get("flow") == "checkout" and in_zone and not update.edited_message:
        sd = fs["data"].get("shift_date", shift_date)
        att_check_out(staff["id"], sd, now_pp.isoformat())
        flow_clear(user.id)
        banked, new_bal = _settle_redefined_shift(staff, sd, now_pp)   # OT net of payback, if redefined
        await msg.reply_text(ui._CO_DONE)
        if banked > 0:                               # earned OT → offer to take it back as rest
            await _offer_buyback(context, staff, new_bal, user.id, banked)
        return True
    if not in_zone:
        if not update.edited_message:
            await msg.reply_text(ui._V_FAR)
        return True
    now_min = now_pp.hour * 60 + now_pp.minute
    state, mins = ci.verdict(now_min, ws, True)
    late = mins if state == "late" else 0
    early = mins if state == "early" else 0
    first = att_check_in(staff["id"], shift_date, now_pp.isoformat(), True, late, early)
    if first:
        # record raw points events (values derived later — owner-tuned; nothing connected yet)
        try:
            if state == "early":
                points_record(staff["id"], "early_arrival", 1, shift_date)
            elif state == "late":
                # the DECLARATION TIME splits the minutes (owner, Jun 11): already-late minutes
                # before declaring stay −2/min; minutes after the declaration are −1/min;
                # declared before shift start → all −1/min. Never declared → all −2/min.
                from shared.database import late_declared_at
                from gm_bot.points import split_late
                dec = late_declared_at(staff["id"], shift_date)
                off = None
                if dec is not None:
                    sd0 = datetime.fromisoformat(str(shift_date)).replace(
                        tzinfo=finance.PP_TZ) + timedelta(minutes=ws)
                    off = int((dec.astimezone(finance.PP_TZ) - sd0).total_seconds() // 60)
                un_min, inf_min = split_late(late, off)
                if un_min:
                    points_record(staff["id"], "late_uninformed", un_min, shift_date)
                if inf_min:
                    points_record(staff["id"], "late_informed", inf_min, shift_date)
        except Exception:
            pass
    if first and not update.edited_message:
        if state == "early":
            await msg.reply_text(ui._V_EARLY % (early, early))
        elif state == "late":
            # late arrival → ONE combined message: the verdict + the payback picker (so the reason
            # and the slot picker can't be read separately).
            try:
                payback_add_debt(staff["id"], late, "late arrival", shift_date)
                d = payback_open_debt(staff["id"])
                if d:
                    await _offer_payback(context, staff, d["balance"], user.id, late_min=late)
                else:
                    await msg.reply_text(ui._V_LATE % (late, late))
            except Exception as e:
                logger.error("payback debt create failed: %s", e)
                await msg.reply_text(ui._V_LATE % (late, late))
        else:
            await msg.reply_text(ui._V_ONTIME)
    return True


async def book_family_death(context, staff: dict, who: str, start_date: str) -> int:
    """Family death — NO approval, instant condolence + book + Supervisors notice + AL deduct
    (negative ok). Compassion tier (sibling/grandparent) = 1 day → owner can upgrade."""
    from gm_bot import special as sp
    from datetime import date as _date, timedelta as _td
    days = sp.death_default_days(who)
    leave_id = special_leave_create(staff["id"], "death", who, start_date, days)
    al_deduct(staff["id"], days)   # AL may go below zero for death
    name = staff.get("call_name") or staff["canonical_name"]
    d0 = _date.fromisoformat(start_date)
    dn = (d0 + _td(days=days - 1)).strftime("%a %d/%m")
    await _att_send(context, (staff.get("telegram_ids") or [None])[0], "Staff", name,
        "We're very sorry for your loss 🤍\n%d days of leave, %s → %s. No approval needed.\n"
        "យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍 សម្រាក %d ថ្ងៃ, %s → %s។ "
        "មិនចាំបាច់រង់ចាំការអនុម័តទេ។"
        % (days, d0.strftime("%a %d/%m"), dn, days, d0.strftime("%a %d/%m"), dn))
    await _att_send(context, None, "Supervisors group", "",
        "%s on leave %s → %s (death of %s).\n%s ឈប់សម្រាក %s → %s (មរណភាព %s)។"
        % (name, d0.strftime("%a %d/%m"), dn, who, name, d0.strftime("%a %d/%m"), dn, who), group=True)
    # compassion tier → let the owner upgrade to the full law-tier with one tap
    if sp.death_tier(who) == "compassion":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Upgrade to 3 days", callback_data="att:dth:%d:3" % leave_id)],
            [InlineKeyboardButton("Keep 1 day", callback_data="att:dth:%d:1" % leave_id)]])
        for oid in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
            if oid:
                try:
                    await context.bot.send_message(oid,
                        "%s reported a %s's death — gave 1 day (compassion). Upgrade?" % (name, who),
                        reply_markup=kb)
                except Exception:
                    pass
    return leave_id


async def _death_upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:dth:{leave}:{days} — owner upgrades a compassion-tier death leave."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    _, _, lid_s, days_s = query.data.split(":")
    leave = special_leave_get(int(lid_s))
    if not leave:
        return
    new_days = int(days_s)
    extra = new_days - (leave["days"] or 1)
    if extra > 0:
        special_leave_set_days(int(lid_s), new_days)
        al_deduct(leave["staff_id"], extra)
        staff = next((s for s in staff_all("active") if s["id"] == leave["staff_id"]), None)
        if staff:
            await _att_send(context, (staff.get("telegram_ids") or [None])[0], "Staff",
                staff.get("call_name") or staff["canonical_name"],
                "Your leave is extended to %d days 🤍\nច្បាប់សម្រាករបស់អ្នកត្រូវបានបន្ថែមដល់ %d ថ្ងៃហើយ 🤍"
                % (new_days, new_days))
    await query.edit_message_text(query.message.text + "\n\n✓ %d day(s)." % new_days)


async def book_wife_birth(context, staff: dict, start_date: str) -> int:
    """Wife giving birth — 2 days, notify only, AL deduct (negative ok)."""
    from gm_bot import special as sp
    from datetime import date as _date, timedelta as _td
    leave_id = special_leave_create(staff["id"], "birth", "wife", start_date, sp.BIRTH_DAYS)
    al_deduct(staff["id"], sp.BIRTH_DAYS)
    name = staff.get("call_name") or staff["canonical_name"]
    d0 = _date.fromisoformat(start_date)
    dn = (d0 + _td(days=sp.BIRTH_DAYS - 1)).strftime("%a %d/%m")
    await _att_send(context, (staff.get("telegram_ids") or [None])[0], "Staff", name,
        "Congratulations! 👶 2 days of leave, %s → %s.\nអបអរសាទរ! 👶 សម្រាក 2 ថ្ងៃ, %s → %s។"
        % (d0.strftime("%a %d/%m"), dn, d0.strftime("%a %d/%m"), dn))
    await _att_send(context, None, "Supervisors group", "",
        "%s on leave %s → %s (wife giving birth).\n%s ឈប់សម្រាក %s → %s (ប្រពន្ធសម្រាលកូន)។"
        % (name, d0.strftime("%a %d/%m"), dn, name, d0.strftime("%a %d/%m"), dn), group=True)
    return leave_id


def _sc_coverage_lines(staff: dict, when_date: str, start_min: int, end_min: int) -> str:
    """Who's working the REDEFINED window on that date (plain text). An overnight tail past
    midnight shows the when_date portion only — good enough to decide coverage."""
    s = start_min % 1440
    e = 1440 if end_min > 1440 else end_min
    hs = "%02d:%02d" % (s // 60, s % 60)
    he = "23:59" if e >= 1440 else "%02d:%02d" % (e // 60, e % 60)
    try:
        return _al_availability_lines(staff, [str(when_date)], hs, he) or ""
    except Exception:
        return ""


def _sc_card(g: dict, staff: dict, show_cov: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """The staff's shift-redefine card — Approve/Can't while proposed, the decision line after,
    and a PERSISTENT 👁 who's-working toggle at every stage (owner, Jun 11: both parties must
    see who covers the new times — it helps them decide)."""
    from shared.database import payback_open_debt
    from gm_bot import ot as ot_mod
    start_min, end_min = int(g["start_min"]), int(g["end_min"])
    normal_len = int(g.get("normal_len") or 0)
    extra = max(0, end_min - (start_min + normal_len))
    pb = 0
    if extra:
        d = payback_open_debt(staff["id"])
        pb = max(0, (d["minutes_owed"] - d["minutes_paid"])) if d else 0
    pb_cleared, ot_min = ot_mod.split_ot_pb(extra, pb)
    tag = ot_mod._ext_tag(pb_cleared, ot_min)
    win = "%s-%s" % (_fmt_min(start_min), _fmt_min(end_min))
    tagtxt = (" (%s)" % tag) if tag else ""
    body = ("🕒 Shift change — %s: %s%s\n"
            "🕒 ប្តូរវេន — %s៖ %s%s\n"
            "Why · មូលហេតុ៖ %s\n\n"
            "You're paid for the time you work; come early → +10 points ⭐; normal late/no-show rules apply.\n"
            "ប្អូនទទួលប្រាក់តាមម៉ោងដែលប្អូនធ្វើការ; មកដល់មុនម៉ោង → +10 points ⭐; ច្បាប់មកយឺត/No-show ធម្មតានៅតែអនុវត្ត។"
            % (g["when_date"], win, tagtxt, g["when_date"], win, tagtxt, g.get("reason") or "—"))
    st = g.get("status")
    if st == "approved":
        body += "\n\n✅ Approved · បានយល់ព្រម"
    elif st == "declined":
        body += "\n\n❌ Declined · មិនបានយល់ព្រម"
    elif st == "done":
        body += "\n\n✅ Done · រួចរាល់"
    if show_cov:
        cov = _sc_coverage_lines(staff, g["when_date"], start_min, end_min)
        if cov:
            body += "\n\n👥 Working those hours · អ្នកធ្វើការពេលនោះ:\n" + cov
    rows = []
    if st == "proposed":
        rows = [[InlineKeyboardButton("✅ Approve · យល់ព្រម", callback_data="att:sc:yes:%d" % g["id"])],
                [InlineKeyboardButton("❌ Can't — explain · មិនអាច — ពន្យល់",
                                      callback_data="att:sc:no:%d" % g["id"])]]
    cov_btn = (("🙈 Hide who's working · លាក់អ្នកធ្វើការ", 0) if show_cov
               else ("👁 Show who's working · បង្ហាញអ្នកធ្វើការ", 1))
    rows.append([InlineKeyboardButton(cov_btn[0],
                 callback_data="att:sccov:%d:%d" % (g["id"], cov_btn[1]))])
    return body, InlineKeyboardMarkup(rows)


async def _sc_cov_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:sccov:{cid}:{flag} — the shift-change card's who's-working toggle, any stage."""
    from shared.database import shift_change_get
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    g = shift_change_get(int(parts[2]))
    staff = next((s for s in staff_all("active") if s["id"] == (g or {}).get("staff_id")), None)
    if not g or not staff:
        return await _expired_toast(query, context,
                                    update.effective_user.id if update.effective_user else None)
    body, kb = _sc_card(g, staff, show_cov=bool(int(parts[3])))
    try:
        await query.edit_message_text(body, reply_markup=kb)
    except Exception:
        pass


async def submit_shift_change(context, senior: dict, staff: dict, when_date: str,
                              start_min: int, end_min: int, normal_len: int, reason: str) -> int:
    """A senior REDEFINES staff's shift for when_date (retime / move / extend — see docs/OT_DESIGN.md).
    Creates a PROPOSED row and sends the staff an approval card. OT is emergent = worked beyond
    normal_len; normal attendance rules apply to [start,end]. Any extension first clears outstanding
    payback (shown as +PB then +OT). Banking happens at checkout (Phase: completion wiring)."""
    from shared.database import shift_change_create, shift_change_get
    cid = shift_change_create(senior["id"], staff["id"], when_date, start_min, end_min, normal_len, reason)
    sn = staff.get("call_name") or staff["canonical_name"]
    g = shift_change_get(cid) or {"id": cid, "when_date": when_date, "start_min": start_min,
                                  "end_min": end_min, "normal_len": normal_len, "reason": reason,
                                  "status": "proposed", "staff_id": staff["id"]}
    body, kb = _sc_card(g, staff, show_cov=False)
    suid = (staff.get("telegram_ids") or [None])[0]
    msg = await _att_send(context, suid, "Staff", sn, body, kb=kb)
    if msg is not None:
        context.bot_data.setdefault("sc_staff_card", {})[cid] = (msg.chat_id, msg.message_id)
    return cid


async def _shift_change_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:sc:yes|no:{id} — staff approves/declines a senior's shift redefine. Approve → the shift is
    active for that day (attendance uses it); decline → nothing changes."""
    from shared.database import shift_change_get, shift_change_set_status, shift_change_approve_claim
    query = update.callback_query
    await query.answer()
    cid = int(query.data.split(":")[3])
    g = shift_change_get(cid)
    if not g or g["status"] != "proposed":
        return await _expired_toast(query, context, update.effective_user.id if update.effective_user else None)
    if not _att_test_mode():
        staff = staff_get_by_uid(update.effective_user.id)
        if not staff or staff["id"] != g["staff_id"]:
            return
    stf0 = next((s for s in staff_all("active") if s["id"] == g["staff_id"]), None)
    if query.data.split(":")[2] == "no":
        shift_change_set_status(cid, "declined")
        if stf0:   # rebuild the card → decision line shown, the 👁 toggle SURVIVES (owner)
            body0, kb0 = _sc_card(dict(g, status="declined"), stf0, show_cov=False)
            try:
                await query.edit_message_text(body0, reply_markup=kb0)
            except Exception:
                pass
        # tell the PROPOSING senior (owner, Jun 11: they were left waiting forever otherwise)
        sen = next((s for s in staff_all("active") if s["id"] == g.get("senior_id")), None)
        stf = stf0
        if sen:
            await _att_send(context, (sen.get("telegram_ids") or [None])[0], "Senior",
                sen.get("call_name") or sen["canonical_name"],
                "❌ %s declined the shift change for %s (%s-%s)."
                % ((stf or {}).get("call_name") or (stf or {}).get("canonical_name", "Staff"),
                   g["when_date"], _fmt_min(g["start_min"]), _fmt_min(g["end_min"])))
            # act-first, reason-after: the staffer's reason follows to the proposing senior
            _win = "%s %s-%s" % (g["when_date"], _fmt_min(g["start_min"]), _fmt_min(g["end_min"]))
            _arm_reason(context, update, {"flow": "rej_exp", "to_sid": sen["id"],
                                          "frm": (stf or {}).get("call_name")
                                                 or (stf or {}).get("canonical_name", "Staff"),
                                          "what": "shift change (%s)" % _win,
                                          "what_kh": "ការប្តូរវេន (%s)" % _win,
                                          "persona_id": g["staff_id"]})
            await _ask_reason(query, sen.get("call_name") or sen["canonical_name"])
        return
    _scres = shift_change_approve_claim(cid)
    if _scres == "conflict":
        # F14: they have approved AL that day — can't also be scheduled to work it
        if stf0:
            await _att_send(context, (stf0.get("telegram_ids") or [None])[0], "Staff",
                stf0.get("call_name") or stf0["canonical_name"],
                "Couldn't approve — you have approved leave that day.\n"
                "មិនអាចអនុម័តបានទេ — ប្អូនមានច្បាប់ឈប់សម្រាកនៅថ្ងៃនោះ។")
        return
    if not _scres:
        return await _expired_toast(query, context, update.effective_user.id if update.effective_user else None)
    if stf0:   # rebuild → ✅ line + the 👁 toggle stays usable after the decision (owner)
        body0, kb0 = _sc_card(dict(g, status="approved"), stf0, show_cov=False)
        try:
            await query.edit_message_text(body0, reply_markup=kb0)
        except Exception:
            pass
    staff = stf0
    if staff:
        nm = staff.get("call_name") or staff["canonical_name"]
        win = "%s-%s" % (_fmt_min(g["start_min"]), _fmt_min(g["end_min"]))
        await _att_send(context, None, "Supervisors group", "",
            "FYI: %s's shift on %s is now %s.\nFYI: វេនរបស់ %s នៅ %s ឥឡូវ %s។"
            % (nm, g["when_date"], win, nm, g["when_date"], win), group=True)


def _settle_redefined_shift(staff: dict, shift_date: str, now_pp) -> tuple[int, int]:
    """At checkout for a day that had an APPROVED shift-redefine: OT = worked beyond the normal shift
    length; it clears outstanding payback FIRST, the rest banks (capped at the 14h bank). Marks the
    change done. NO-OP for a normal (un-redefined) day, or one already settled. Best-effort — never
    blocks the checkout. Points are NOT touched here (reputation stays on its own track).
    Returns (banked_min, new_bank_balance) so the caller can offer buyback; (0, …) when nothing banked."""
    try:
        from shared.database import (shift_change_active, att_get_session, payback_open_debt,
                                     payback_credit, ot_bank_add, ot_bank_balance,
                                     shift_change_set_banked, shift_change_claim_settle,
                                     payback_booking_mark_done)
        from gm_bot import ot as ot_mod
        from gm_bot import attendance_ui as ui
        # leave-guard via the ONE resolver: if the day actually resolves to leave (AL/sick/special wins
        # over a redefine), NEVER bank OT here — only a day that resolves to a redefine settles.
        if ui.resolve_day(staff, shift_date)["reason"] != "redefine":
            return 0, 0
        sc = shift_change_active(staff["id"], shift_date)
        # normal_len=0 is VALID: a day-off payback window — every worked minute is extension,
        # so the engine credits the whole window against the debt. Only None means un-settleable.
        if not sc or sc.get("status") != "approved" or sc.get("normal_len") is None:
            return 0, 0                  # not redefined, or already done
        sess = att_get_session(staff["id"], shift_date) or {}
        ci_dt = sess.get("checked_in_at")
        if not ci_dt:
            return 0, 0
        # Worked = presence INSIDE the approved [start,end] only. Early arrival earns points, never
        # OT; lingering past the approved end banks nothing; late arrival still reduces (by design).
        from datetime import date as _date, timedelta as _td
        base = datetime.combine(_date.fromisoformat(str(shift_date)), datetime.min.time(),
                                tzinfo=finance.PP_TZ)
        appr_start = base + _td(minutes=int(sc["start_min"]))
        appr_end = base + _td(minutes=int(sc["end_min"]))
        worked = round((min(now_pp, appr_end) - max(ci_dt, appr_start)).total_seconds() / 60)
        if worked <= 0:
            return 0, 0
        # Atomic claim BEFORE any balance moves: exactly one checkout path banks this shift. A loser
        # (concurrent auto+manual checkout, or a crash-redelivered duplicate) gets the live balance and
        # banks nothing. Failure mode is now underpay-but-visible, never a silent double-bank.
        if not shift_change_claim_settle(sc["id"]):
            return 0, ot_bank_balance(staff["id"])
        debt = payback_open_debt(staff["id"])
        pb = max(0, debt["minutes_owed"] - debt["minutes_paid"]) if debt else 0
        ot_banked, pb_cleared, _new = ot_mod.settle_shift(worked, sc["normal_len"], pb)
        if (sc.get("reason") or "") == "payback slot":
            ot_banked = 0   # a payback slot repays debt ONLY — it can never mint OT (owner, Jun 11)
        if pb_cleared and debt:
            payback_credit(debt["id"], pb_cleared)   # OT clears the debt first (uncapped)
        new_bal = ot_bank_balance(staff["id"])
        banked = 0
        if ot_banked:
            banked = min(ot_banked, ot_mod.cap_room(new_bal))   # respect 14h bank
            if banked > 0:
                new_bal = ot_bank_add(staff["id"], banked)      # post-add balance (test: computed)
        shift_change_set_banked(sc["id"], banked)
        try:
            payback_booking_mark_done(staff["id"], shift_date)   # slot booking → done (bookkeeping)
            from shared.database import ot_buyback_mark_taken
            ot_buyback_mark_taken(staff["id"], shift_date)       # rest booking → taken (bookkeeping)
        except Exception:
            pass
        return banked, new_bal
    except Exception as e:
        logger.error("OT settle at checkout failed: %s", e)
        return 0, 0


async def _offer_buyback(context, staff: dict, bank_min: int, uid: int, just_added: int) -> None:
    """Offer buyback rest at the SAFEST (most-surplus) times — reward tone."""
    from gm_bot import coverage as cov, payback as pb
    from gm_bot.attendance import to_min
    ws, we = to_min(staff.get("work_start")), to_min(staff.get("work_end"))
    label = ("%dmin" % just_added) if just_added < 60 else ("%gh" % (just_added / 60))
    rows = []
    if ws is not None and we is not None:
        days = pb.working_days_ahead(staff.get("day_off"), set(),
                                     _today_pp(), 7, 3)
        roster = [s for s in staff_all("active") if s.get("org") == "TWB"]
        scored = []
        for d in days:
            wd = d.strftime("%a")
            for lbl, s_min, e_min in pb.takeback_windows(ws, we, bank_min):
                surp = cov.slot_surplus(staff.get("expertise") or [], s_min, e_min, wd,
                                        roster, set(), to_min)
                tag = "🌅 in late" if lbl == "start late" else "🌙 leave early"
                txt = "%s %s-%s · %s" % (d.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min), tag)
                scored.append((surp, [InlineKeyboardButton(
                    txt, callback_data="att:otb:%d:%s:%d:%d:%d"
                    % (staff["id"], d.isoformat(), s_min, e_min, bank_min))]))
        scored.sort(key=lambda t: -t[0])   # safest (most surplus) first
        rows = [b for _s, b in scored]
    await _att_send(context, uid, "Staff", staff.get("call_name") or staff["canonical_name"],
        "+%s OT approved — your bank: %gh. Choose when to take it back:\n"
        "+%s OT ត្រូវបានអនុម័ត — OT bank៖ %gh។ សូមជ្រើសម៉ោងសម្រាកសងវិញ៖"
        % (label, bank_min / 60, label, bank_min / 60),
        kb=InlineKeyboardMarkup(rows) if rows else None)


async def _ot_buyback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:otb:{date}:{start}:{end}:{bankmin} — staff books buyback rest."""
    query = update.callback_query
    await query.answer()
    # att:otb:{sid}:{date}:{start}:{end}:{bank}
    _, _, sid_s, slot_date, s_min, e_min, _bank = query.data.split(":")
    if _att_test_mode():
        staff = next((s for s in staff_all("active") if s["id"] == int(sid_s)), None)
    else:
        staff = staff_get_by_uid(update.effective_user.id)
        if not staff or staff["id"] != int(sid_s):
            return await _expired_toast(query, context, update.effective_user.id if update.effective_user else None)
    if not staff:
        return await _expired_toast(query, context, update.effective_user.id if update.effective_user else None)
    rest_min = (int(e_min) - int(s_min)) % 1440 or 1440
    ot_buyback_book(staff["id"], slot_date, int(s_min), int(e_min), rest_min)
    # Jun 11 (the buyback twin of the mini-shift bug): booking now DEBITS the bank immediately
    # (was: nothing debited → the same hours bookable forever) and creates the shift REDEFINE so
    # attendance is fair on the rest day (no false 'late' for using earned rest).
    from shared.database import ot_bank_spend, shift_change_autoapprove
    from gm_bot.attendance import to_min as _tm0
    from gm_bot import ot as _ot
    ot_bank_spend(staff["id"], rest_min)
    _w0, _w1 = _tm0(staff.get("work_start")), _tm0(staff.get("work_end"))
    if _w0 is not None and _w1 is not None:
        win = _ot.rest_redefine(_w0, _w1, int(s_min), int(e_min))
        if win:
            shift_change_autoapprove(staff["id"], slot_date, win[0], win[1], win[2], "OT rest")
    from datetime import date as _date
    d = _date.fromisoformat(slot_date)
    await query.edit_message_text(
        "Booked your rest ✓ — %s %s-%s 🌴\nបានកក់ម៉ោងសម្រាករបស់អ្នករួច ✓ — %s %s-%s 🌴"
        % (d.strftime("%a %d/%m"), _fmt_min(int(s_min)), _fmt_min(int(e_min)),
           d.strftime("%a %d/%m"), _fmt_min(int(s_min)), _fmt_min(int(e_min))))
    # Supervisors must know the day's coverage changed (owner, Jun 11: every confirmed outcome
    # lands in the group) — English-only, like the payback-booked sibling.
    from gm_bot.attendance import to_min as _tm
    nm = staff.get("call_name") or staff["canonical_name"]
    ws0, we0 = _tm(staff.get("work_start")), _tm(staff.get("work_end"))
    if ws0 is not None and int(s_min) % 1440 == ws0 % 1440:
        detail = "starts at %s (OT rest first)" % _fmt_min(int(e_min))
    elif we0 is not None and int(e_min) % 1440 == we0 % 1440:
        detail = "leaves at %s (OT rest last)" % _fmt_min(int(s_min))
    else:
        detail = "rests %s-%s (earned OT)" % (_fmt_min(int(s_min)), _fmt_min(int(e_min)))
    await _att_send(context, None, "Supervisors group", "",
                    "🌴 OT rest: %s on %s — %s." % (nm, d.strftime("%a %d/%m"), detail), group=True)


def _swap_coverage_html(req: dict, partner: dict, sw: dict) -> str:
    """The '👥 Working those days' block for a swap — BOTH affected days: who's working on the
    requester's off date (requester away) AND on the partner's off date (partner away)."""
    import html
    parts = []
    for who_off, iso in ((req, str(sw["req_off_date"])), (partner, str(sw["partner_off_date"]))):
        ln = _al_availability_lines(who_off, [iso])     # excludes who_off, uses their shift hours
        if ln:
            parts.append(ln)
    if not parts:
        return ""
    avail = "\n".join(
        ("<b>%s</b>:%s" % (html.escape(l.split(":", 1)[0]), html.escape(l.split(":", 1)[1]))
         if ":" in l else html.escape(l))
        for l in "\n".join(parts).split("\n"))
    return "\n\n👥 Working those days · អ្នកធ្វើការពេលនោះ:\n%s" % avail


def _swap_card(sw: dict, req: dict, partner: dict, *, audience: str,
               show_cov: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """The ONE day-off-swap card for partner / senior / requester, in every state
    (pending / partner_ok / approved / rejected), each carrying a persistent 👁/🙈 Show-who's-working
    toggle (BOTH affected days) that survives the decision."""
    import html
    from datetime import date as _date
    rn = req.get("call_name") or req["canonical_name"]
    pn = partner.get("call_name") or partner["canonical_name"]
    d1 = _date.fromisoformat(str(sw["req_off_date"])).strftime("%a %d/%m")
    d2 = _date.fromisoformat(str(sw["partner_off_date"])).strftime("%a %d/%m")
    reason = html.escape(sw.get("reason") or "—")
    st = sw.get("status")
    partner_ok = sw.get("partner_ok")
    # reason appears ONCE after the EN+KH lines (owner, Jun 11 — never duplicate typed text)
    if audience == "partner":
        body = ("%s wants to swap day off: %s takes %s off, you take %s — same week.\n"
                "%s ស្នើសុំប្តូរថ្ងៃឈប់ជាមួយប្អូន៖ %s ឈប់ %s, ប្អូនឈប់ %s — ក្នុងសប្តាហ៍ដដែល។\n"
                "Reason · មូលហេតុ៖ %s"
                % (html.escape(rn), html.escape(rn), d1, d2,
                   html.escape(rn), html.escape(rn), d1, d2, reason))
    elif audience == "requester":
        body = ("Day-off swap — your off %s ↔ %s off %s.\n"
                "ប្តូរថ្ងៃឈប់ — ប្អូនឈប់ %s ↔ %s ឈប់ %s។\n"
                "Reason · មូលហេតុ៖ %s"
                % (d1, html.escape(pn), d2,
                   d1, html.escape(pn), d2, reason))
    else:  # senior
        body = ("Day-off swap: %s ↔ %s\n%s off %s, %s off %s.\n"
                "ប្តូរថ្ងៃឈប់៖ %s ↔ %s\n%s ឈប់ %s, %s ឈប់ %s។\n"
                "Reason · មូលហេតុ៖ %s"
                % (html.escape(rn), html.escape(pn), html.escape(rn), d1, html.escape(pn), d2,
                   html.escape(rn), html.escape(pn), html.escape(rn), d1, html.escape(pn), d2,
                   reason))
    status_line = None
    if st == "approved":
        status_line = "✅ Approved · បានអនុម័ត"
    elif st == "rejected":
        status_line = ("✋ Declined by partner · ដៃគូមិនបានយល់ព្រម" if partner_ok is False
                       else "❌ Not approved · មិនបានអនុម័ត")
    elif st == "partner_ok":
        status_line = ("✅ You agreed — sent to seniors · ប្អូនបានយល់ព្រមហើយ — បានផ្ញើទៅបងៗ"
                       if audience == "partner"
                       else "⏳ Awaiting senior approval · កំពុងរង់ចាំបងៗអនុម័ត")
    elif st == "pending" and audience == "requester":
        status_line = "⏳ Awaiting partner · កំពុងរង់ចាំដៃគូយល់ព្រម"
    if status_line:
        body += "\n\n" + status_line
    if show_cov:
        body += _swap_coverage_html(req, partner, sw)
    cov = (("🙈 Hide who's working · លាក់អ្នកធ្វើការ", 0) if show_cov
           else ("👁 Show who's working · បង្ហាញអ្នកធ្វើការ", 1))
    rows = []
    if audience == "partner" and st == "pending":
        rows.append([InlineKeyboardButton("✅ I agree · ខ្ញុំយល់ព្រម",
                     callback_data="att:swp:%d:agree" % sw["id"])])
        rows.append([InlineKeyboardButton("✋ No — explain · ទេ — ពន្យល់", callback_data="att:swp:%d:no" % sw["id"])])
    elif audience == "senior" and st == "partner_ok":
        rows.append([InlineKeyboardButton("✅ Approve · អនុម័ត",
                     callback_data="att:swps:%d:approve" % sw["id"])])
        rows.append([InlineKeyboardButton("❌ Not approve — explain · មិនអនុម័ត — ពន្យល់",
                     callback_data="att:swps:%d:not_approve" % sw["id"])])
    rows.append([InlineKeyboardButton(cov[0],
                 callback_data="att:swcov:%d:%s:%d" % (sw["id"], audience, cov[1]))])
    return body, InlineKeyboardMarkup(rows)


async def _swap_coverage_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:swcov:{id}:{audience}:{flag} — show/hide both-days coverage on any swap card, any state."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    sw = swap_get(int(parts[2]))
    if not sw:
        return
    req = next((s for s in staff_all("active") if s["id"] == sw["requester_id"]), None)
    partner = next((s for s in staff_all("active") if s["id"] == sw["partner_id"]), None)
    if not req or not partner:
        return
    body, kb = _swap_card(sw, req, partner, audience=parts[3], show_cov=bool(int(parts[4])))
    try:
        await query.edit_message_text(body, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


async def submit_swap(context, requester: dict, partner: dict, req_off_date: str,
                      partner_off_date: str, reason: str) -> int:
    """Create a day-off swap and ask the PARTNER first (their veto is cheapest)."""
    swap_id = swap_create(requester["id"], partner["id"], req_off_date, partner_off_date, reason)
    sw = swap_get(swap_id)
    body, kb = _swap_card(sw, requester, partner, audience="partner", show_cov=False)
    msg = await _att_send(context, (partner.get("telegram_ids") or [None])[0], "Partner",
                          partner.get("call_name") or partner["canonical_name"], body, kb=kb,
                          parse_mode="HTML")
    if msg is not None:   # register so _swap_apply can flip the partner card to the verdict
        context.bot_data.setdefault("swap_partner_cards", {})[swap_id] = (msg.chat_id, msg.message_id)
    return swap_id


async def _swap_partner_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:swp:{id}:{agree|no} — partner decides FIRST."""
    query = update.callback_query
    await query.answer()
    sw = swap_get(int(query.data.split(":")[2]))
    if not sw or sw["status"] != "pending":
        await query.edit_message_text(query.message.text + "\n\n(already decided)")
        return
    if not _att_test_mode():
        tapper = staff_get_by_uid(update.effective_user.id)
        if not tapper or tapper["id"] != sw["partner_id"]:
            return
    partner = next((s for s in staff_all("active") if s["id"] == sw["partner_id"]), None)
    req = next((s for s in staff_all("active") if s["id"] == sw["requester_id"]), None)
    decision = query.data.split(":")[3]
    if decision == "no":
        swap_set_partner(int(sw["id"]), False)
        sw = swap_get(int(sw["id"]))   # re-read: status now 'rejected', partner_ok False
        body, kb = _swap_card(sw, req, partner, audience="partner", show_cov=False)
        try:
            await query.edit_message_text(body, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
        await _swap_flip_requester_card(context, sw, req, partner)   # requester card → declined
        if req:
            from datetime import date as _dp
            d1p = _dp.fromisoformat(str(sw["req_off_date"])).strftime("%a %d/%m")
            d2p = _dp.fromisoformat(str(sw["partner_off_date"])).strftime("%a %d/%m")
            await _att_send(context, (req.get("telegram_ids") or [None])[0], "Requester",
                req.get("call_name") or req["canonical_name"],
                "Your day-off swap (%s ↔ %s) wasn't accepted by your partner.\n"
                "អ្នកដែលត្រូវប្តូរជាមួយ មិនបានយល់ព្រមលើការប្តូរថ្ងៃឈប់ (%s ↔ %s) របស់ប្អូនទេ។"
                % (d1p, d2p, d1p, d2p))
            # act-first, reason-after: the partner's reason is relayed to the requester
            _arm_reason(context, update, {"flow": "rej_exp", "to_sid": req["id"],
                                          "frm": (partner or {}).get("call_name")
                                                 or (partner or {}).get("canonical_name", "partner"),
                                          "what": "day-off swap (%s ↔ %s)" % (d1p, d2p),
                                          "what_kh": "ការប្តូរថ្ងៃឈប់ (%s ↔ %s)" % (d1p, d2p),
                                          "persona_id": (partner or {}).get("id")})
            await _ask_reason(query, req.get("call_name") or req["canonical_name"])
        return
    swap_set_partner(int(sw["id"]), True)
    sw = swap_get(int(sw["id"]))       # re-read: status now 'partner_ok' (drives both cards)
    body, kb = _swap_card(sw, req, partner, audience="partner", show_cov=False)
    try:
        await query.edit_message_text(body, reply_markup=kb, parse_mode="HTML")  # partner card keeps toggle
    except Exception:
        pass
    await _swap_flip_requester_card(context, sw, req, partner)   # requester card → awaiting senior
    # now seniors — the card carries a persistent 👁 Show-who's-working toggle (both affected days)
    cards = context.bot_data.setdefault("swap_cards", {}).setdefault(sw["id"], [])
    for sen in _seniors(exclude_staff_id=sw["requester_id"]):
        body, kb = _swap_card(sw, req, partner, audience="senior", show_cov=False)
        msg = await _att_send(context, (sen.get("telegram_ids") or [None])[0], "Senior",
                              sen.get("call_name") or sen["canonical_name"], body, kb=kb,
                              parse_mode="HTML")
        if msg is not None:
            cards.append((msg.chat_id, msg.message_id))


async def _swap_flip_requester_card(context, sw: dict, req: dict, partner: dict) -> None:
    """Re-render the requester's OWN swap card (if registered) to the current state, keeping its toggle."""
    sc = context.bot_data.get("swap_req_cards", {}).get(sw["id"])
    if not sc or not req or not partner:
        return
    body, kb = _swap_card(sw, req, partner, audience="requester", show_cov=False)
    try:
        await context.bot.edit_message_text(body, chat_id=sc[0], message_id=sc[1],
                                            reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


async def _swap_senior_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:swps:{id}:{approve|not_approve} — seniors decide AFTER the partner agreed.
    Test: owner taps as a senior (votes aren't deduped per-senior, so two taps reach quorum)."""
    query = update.callback_query
    await query.answer()
    if not _att_test_mode():
        sen = staff_get_by_uid(update.effective_user.id)
        if not sen or not sen.get("is_senior"):
            return
    sw = swap_get(int(query.data.split(":")[2]))
    if not sw or sw["status"] != "partner_ok":
        await query.edit_message_text(query.message.text + "\n\n(already decided)")
        return
    from gm_bot import al as alm
    requester = next((s for s in staff_all("active") if s["id"] == sw["requester_id"]), None)
    needed = alm.approvals_needed(bool(requester and requester.get("is_senior")))
    votes = swap_add_senior_vote(int(sw["id"]), query.data.split(":")[3])
    await query.edit_message_text(query.message.text + "\n\n✓ voted: %s" % query.data.split(":")[3])
    if query.data.split(":")[3] == "not_approve":
        # owner (Jun 11): ONE ❌ decides; approvals still need the quorum
        await _swap_apply(context, sw, approved=False)
        if requester:
            from datetime import date as _date
            d1 = _date.fromisoformat(str(sw["req_off_date"])).strftime("%a %d/%m")
            d2 = _date.fromisoformat(str(sw["partner_off_date"])).strftime("%a %d/%m")
            sen2 = sen if not _att_test_mode() else None
            frm = ((sen2 or {}).get("call_name") or (sen2 or {}).get("canonical_name", "a senior"))
            _arm_reason(context, update, {"flow": "rej_exp", "to_sid": requester["id"],
                                          "frm": frm,
                                          "what": "day-off swap (%s ↔ %s)" % (d1, d2),
                                          "what_kh": "ការប្តូរថ្ងៃឈប់ (%s ↔ %s)" % (d1, d2),
                                          "persona_id": (sen2 or {}).get("id") or requester["id"]})
            await _ask_reason(query, requester.get("call_name") or requester["canonical_name"])
    elif alm.quorum_reached(votes, needed):
        await _swap_apply(context, sw, approved=True)


async def _swap_apply(context, sw: dict, approved: bool) -> None:
    if swap_get(sw["id"])["status"] != "partner_ok":
        return
    req = next((s for s in staff_all("active") if s["id"] == sw["requester_id"]), None)
    partner = next((s for s in staff_all("active") if s["id"] == sw["partner_id"]), None)
    if not req or not partner:
        return
    if approved:
        # F14 (swap side): atomically check NEITHER party has approved AL on the day the swap would put
        # them to WORK, then flip + write the 4 overrides in ONE txn (shared advisory lock w/ AL/shift).
        res = swap_approve_claim(sw["id"])
        if res == "conflict":
            for s, role in ((req, "Requester"), (partner, "Partner")):
                await _att_send(context, (s.get("telegram_ids") or [None])[0], role,
                    s.get("call_name") or s["canonical_name"],
                    "Couldn't approve the swap — one of you has approved leave on a day it needs worked.\n"
                    "មិនអាចអនុម័តការប្តូរបានទេ — ម្នាក់ក្នុងចំណោមអ្នកមានច្បាប់ឈប់សម្រាកនៅថ្ងៃដែលត្រូវធ្វើការ។")
            return
        if not res:
            return   # lost the claim / not in a claimable state
    else:
        swap_set_status(sw["id"], "rejected")
    # edit the senior cards in place (request stays intact + the verdict) — and KEEP the
    # 👁 Show-who's-working toggle so coverage stays checkable after the decision (like AL).
    sw2 = swap_get(sw["id"])   # status now approved/rejected
    _fbody, _fkb = _swap_card(sw2, req, partner, audience="senior", show_cov=False)
    for _cid, _mid in context.bot_data.get("swap_cards", {}).pop(sw["id"], []):
        try:
            await context.bot.edit_message_text(_fbody, chat_id=_cid, message_id=_mid,
                                                reply_markup=_fkb, parse_mode="HTML")
        except Exception:
            pass
    # flip the partner's card + the requester's own card to the verdict too (toggle stays on both)
    _pc = context.bot_data.get("swap_partner_cards", {}).pop(sw["id"], None)
    if _pc:
        pbody, pkb = _swap_card(sw2, req, partner, audience="partner", show_cov=False)
        try:
            await context.bot.edit_message_text(pbody, chat_id=_pc[0], message_id=_pc[1],
                                                reply_markup=pkb, parse_mode="HTML")
        except Exception:
            pass
    await _swap_flip_requester_card(context, sw2, req, partner)
    context.bot_data.get("swap_req_cards", {}).pop(sw["id"], None)
    if approved:
        # the 4 dated overrides were written atomically inside swap_approve_claim (with the F14 check)
        for s, role in ((req, "Requester"), (partner, "Partner")):
            await _att_send(context, (s.get("telegram_ids") or [None])[0], role,
                s.get("call_name") or s["canonical_name"],
                "Your day-off swap is approved ✓\nការប្តូរថ្ងៃឈប់របស់អ្នកបានអនុម័តហើយ ✓")
        from datetime import date as _date
        rn2 = req.get("call_name") or req["canonical_name"]
        pn2 = partner.get("call_name") or partner["canonical_name"]
        rd2 = _date.fromisoformat(str(sw["req_off_date"])).strftime("%a %d/%m")
        pd2 = _date.fromisoformat(str(sw["partner_off_date"])).strftime("%a %d/%m")
        await _att_send(context, None, "Supervisors group", "",
            "Day-off swap: %s off %s, %s off %s.\nប្តូរថ្ងៃឈប់៖ %s ឈប់ %s, %s ឈប់ %s។"
            % (rn2, rd2, pn2, pd2, rn2, rd2, pn2, pd2), group=True)
    else:
        from datetime import date as _dr
        rd3 = _dr.fromisoformat(str(sw["req_off_date"])).strftime("%a %d/%m")
        pd3 = _dr.fromisoformat(str(sw["partner_off_date"])).strftime("%a %d/%m")
        for s, role in ((req, "Requester"), (partner, "Partner")):
            await _att_send(context, (s.get("telegram_ids") or [None])[0], role,
                s.get("call_name") or s["canonical_name"],
                "The day-off swap (%s ↔ %s) wasn't approved.\n"
                "ការប្តូរថ្ងៃឈប់ (%s ↔ %s) មិនបានអនុម័តទេ។" % (rd3, pd3, rd3, pd3))


def _seniors(exclude_staff_id: int | None = None) -> list[dict]:
    return [s for s in staff_all("active")
            if s.get("is_senior") and s.get("org") == "TWB" and s["id"] != exclude_staff_id
            and (s.get("telegram_ids") or [])]   # TWB seniors only — attendance never mixes locations


def _al_availability_lines(requester: dict, days: list[str],
                           hours_start: str | None = None, hours_end: str | None = None) -> str:
    """Per AL day: who works the AL HOURS that day — the requester's full shift, or for an hours-AL
    the chosen hours (so the senior sees exactly who covers the few hours she's off). Excl day-off."""
    from gm_bot.attendance import available_staff, to_min
    from datetime import date as _date
    ws, we = to_min(requester.get("work_start")), to_min(requester.get("work_end"))
    if hours_start and hours_end:
        hs, he = to_min(hours_start), to_min(hours_end)
        if hs is not None and he is not None:
            ws, we = hs, he
    if ws is None or we is None:
        return ""
    scheds = [{"name": s.get("call_name") or s["canonical_name"],
               "work_start": to_min(s.get("work_start")), "work_end": to_min(s.get("work_end")),
               "day_off": s.get("day_off")} for s in staff_all("active")
              if s["id"] != requester["id"] and s.get("org") == "TWB"
              and s.get("canonical_name") != "Tyty"]   # TWB only — never mix in Delis/Tyty
    # who's on AL each day (from approved requests)
    on_al_by_day = {}
    for r in al_pending_requests():  # pending don't count; use approved below
        pass
    lines = []
    for iso in days:
        wd = _date.fromisoformat(iso).strftime("%a")
        names = available_staff(ws, we, wd, scheds, set())
        lines.append("%s: %s" % (_date.fromisoformat(iso).strftime("%a %d/%m"),
                                 ", ".join(names) or "—"))
    return "\n".join(lines)


def _al_coverage_html(requester: dict, days: list[str],
                      hours_start: str | None, hours_end: str | None) -> str:
    """The '👥 Working those hours' block (HTML) for the senior card's expanded view."""
    import html
    avail = _al_availability_lines(requester, days, hours_start, hours_end)
    if not avail:
        return ""
    avail_html = "\n".join(
        ("<b>%s</b>:%s" % (html.escape(ln.split(":", 1)[0]), html.escape(ln.split(":", 1)[1]))
         if ":" in ln else html.escape(ln))
        for ln in avail.split("\n"))
    label = ("Working those hours · អ្នកធ្វើការពេលនោះ" if hours_start
             else "Working those days · អ្នកធ្វើការពេលនោះ")
    return "\n\n👥 %s:\n%s" % (label, avail_html)


def _al_card(req: dict, requester: dict, *, audience: str, sen_id: int = 0,
             show_cov: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """The ONE AL card — used for the senior's approval card AND the requester's own card, in EVERY
    state (pending / approved / rejected). Carries a persistent 👁/🙈 Show-who's-working toggle that
    survives all transitions. `audience`: 'senior' (gets Approve/Not-approve while pending) or 'staff'
    (the requester's own card — toggle only, shows '⏳ Awaiting approval' while pending)."""
    import html
    name = requester.get("call_name") or requester["canonical_name"]
    body = _al_summary(name, req["days"], req.get("reason"), requester.get("day_off"),
                       staff_absent_dates(req["staff_id"]), req.get("hours_start"), req.get("hours_end"))
    st = req.get("status")
    if st in ("approved", "rejected"):
        voters = [a for a in al_get_approvals(req["id"])
                  if a["decision"] == ("approve" if st == "approved" else "not_approve")]
        vnames = " and ".join(v.get("call_name") or v["canonical_name"] for v in voters[:2]) or "—"
        body += "\n\n" + (("✅ Approved by %s." if st == "approved"
                           else "❌ Not approved by %s.") % html.escape(vnames))
    elif audience == "staff":
        body += "\n\n⏳ Awaiting approval · កំពុងរង់ចាំការអនុម័ត"
    if show_cov:
        body += _al_coverage_html(requester, req["days"], req.get("hours_start"), req.get("hours_end"))
    cov = (("🙈 Hide who's working · លាក់អ្នកធ្វើការ", 0) if show_cov
           else ("👁 Show who's working · បង្ហាញអ្នកធ្វើការ", 1))
    rows = []
    if audience == "senior" and st == "pending":
        rows.append([InlineKeyboardButton("✅ Approve",
                     callback_data="att:alapp:%d:approve:%d" % (req["id"], sen_id))])
        rows.append([InlineKeyboardButton("❌ Not approve — explain · មិនអនុម័ត — ពន្យល់",
                     callback_data="att:alapp:%d:not_approve:%d" % (req["id"], sen_id))])
    rows.append([InlineKeyboardButton(cov[0],
                 callback_data="att:alcov:%d:%s:%d:%d" % (req["id"], audience, sen_id, cov[1]))])
    return body, InlineKeyboardMarkup(rows)


async def _al_coverage_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:alcov:{req}:{audience}:{sid}:{flag} — show/hide who's-working on a card. Works for the
    senior card AND the requester's own card, in ANY state (pending/approved/rejected) — the toggle
    persists across every transition. Rebuilds the whole card from the request so other buttons stay."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    req_id, audience, sid, flag = int(parts[2]), parts[3], int(parts[4]), int(parts[5])
    req = al_get_request(req_id)
    if not req:
        return
    requester = next((s for s in staff_all("active") if s["id"] == req["staff_id"]), None)
    if not requester:
        return
    body, kb = _al_card(req, requester, audience=audience, sen_id=sid, show_cov=bool(flag))
    try:
        await query.edit_message_text(body, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


async def submit_al_request(context, requester: dict, kind: str, days: list[str],
                            hours_start: str | None, hours_end: str | None, reason: str,
                            requested_by_uid: int) -> int:
    """Create the AL request and DM every senior an approval card (gated by caller).
    Returns the new request id, or None if blocked (a day is already approved leave / a scheduled
    shift change — F14 request-side: don't waste a senior's decision on a day that can only conflict)."""
    import html
    from shared.database import al_date_conflict
    conflicts = al_date_conflict(requester["id"], days)
    if conflicts:
        runc = requester.get("telegram_ids") or []
        await _att_send(context, runc[0] if runc else None, "Requester",
            requester.get("call_name") or requester["canonical_name"],
            "⚠ You already have approved leave or a scheduled shift change on: %s.\n"
            "Pick other day(s).\n"
            "⚠ ប្អូនមានច្បាប់ឈប់សម្រាក ឬការប្តូរវេនដែលអនុម័តរួចនៅ៖ %s។ សូមជ្រើសថ្ងៃផ្សេង។"
            % (", ".join(conflicts), ", ".join(conflicts)))
        return None
    req_id = al_create_request(requester["id"], kind, days, hours_start, hours_end,
                               reason, requested_by_uid)
    # AL cards are English-only (owner request); COMPACT by default — request + BOLD from→to dates +
    # the hours window for an hours-AL. Coverage ("Working those hours") opens via the Show toggle.
    req = al_get_request(req_id)
    cards = context.bot_data.setdefault("al_cards", {}).setdefault(req_id, [])
    for sen in _seniors(exclude_staff_id=requester["id"]):
        # senior id encoded so a test-mode tap (by the owner) is attributed to THIS senior
        uid = (sen.get("telegram_ids") or [None])[0]
        body, kb = _al_card(req, requester, audience="senior", sen_id=sen["id"], show_cov=False)
        msg = await _att_send(context, uid, "Senior", sen.get("call_name") or sen["canonical_name"],
                              body, kb=kb, parse_mode="HTML")
        if msg is not None:
            cards.append((msg.chat_id, msg.message_id))
    return req_id


def _al_summary(name: str, days: list[str], reason: str, day_off: str | None = None,
                non_working: set | None = None, hours_start: str | None = None,
                hours_end: str | None = None) -> str:
    """The AL request one-liner, English, with BOLD from→to dates (HTML) that BRIDGE any absence
    (day-off, other approved AL, swap day-off …). For an HOURS-AL also shows the BOLD time window.
    Reused for the senior card and the final edited-in-place result so the request text stays intact."""
    import html
    from gm_bot import al as alm
    from gm_bot.attendance import to_min
    span = alm.al_span_label(days, day_off, non_working)
    span_html = "   ".join("<b>%s</b>" % html.escape(seg.strip()) for seg in span.split(",") if seg.strip())
    htxt = ""
    if hours_start and hours_end:
        htxt = "  <b>%s–%s</b>" % (html.escape(_fmt_min(to_min(hours_start))),
                                   html.escape(_fmt_min(to_min(hours_end))))
    return "%s requests AL: %s%s\nReason: %s" % (html.escape(name), span_html, htxt, html.escape(reason or "—"))


async def _al_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:alapp:{req}:{approve|not_approve}:{senior_id} — a senior decides.
    TEST mode: the owner taps; the encoded senior_id is the actor (so two distinct senior
    cards = quorum). LIVE: the tapper must be that senior."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    req_s, decision = parts[2], parts[3]
    enc_sid = int(parts[4]) if len(parts) > 4 else None
    if _att_test_mode() and enc_sid is not None:
        sen = next((s for s in staff_all("active") if s["id"] == enc_sid), None)
        actor_uid = (sen.get("telegram_ids") or [enc_sid])[0] if sen else enc_sid
    else:
        sen = staff_get_by_uid(update.effective_user.id)
        actor_uid = update.effective_user.id
    if not sen or not sen.get("is_senior"):
        return
    req = al_get_request(int(req_s))
    if not req or req["status"] != "pending":
        await query.edit_message_text(query.message.text + "\n\n(already decided)")
        return
    if sen["id"] == req["staff_id"]:
        await query.answer("Can't approve your own AL · មិនអាចអនុម័ត AL របស់ខ្លួនឯងបានទេ", show_alert=True)
        return
    from gm_bot import al as alm
    requester = next((s for s in staff_all("active") if s["id"] == req["staff_id"]), None)
    needed = alm.approvals_needed(bool(requester and requester.get("is_senior")))
    decisions = al_add_approval(int(req_s), sen["id"], actor_uid, decision)
    await query.edit_message_text(query.message.text + "\n\n✓ You voted: %s" % decision)
    if decision == "not_approve":
        # owner (Jun 11): ONE ❌ decides — a senior who refuses has a reason; approvals still
        # need the quorum. Bonus: at most one reason relay ever (no doubled notes).
        await _al_finalize(context, req, approved=False)
        nw0 = staff_absent_dates(req["staff_id"])
        span = alm.al_span_label(req["days"], (requester or {}).get("day_off"), nw0)
        rq_name = (requester or {}).get("call_name") or (requester or {}).get("canonical_name", "the requester")
        _arm_reason(context, update, {"flow": "rej_exp", "to_sid": req["staff_id"],
                                      "frm": sen.get("call_name") or sen["canonical_name"],
                                      "what": "AL request (%s)" % span,
                                      "what_kh": "សំណើ AL (%s)" % span,
                                      "persona_id": sen["id"]})
        await _ask_reason(query, rq_name)
    elif alm.quorum_reached(decisions, needed):
        await _al_finalize(context, req, approved=True)


async def _announce_supersessions(context, victim_name: str, superseded: list) -> None:
    """Schedule-model notify-all (docs/SCHEDULE_RESOLUTION_MODEL.md, Phase 4 seed): when a newer
    decision stood older ones down, tell the senior who owned each + the Supervisors group, so a human
    re-covers (the machine owns balances+truth+telling; humans own coverage). Best-effort + bilingual;
    never blocks the state change that already committed. Today it handles a stood-down SENIOR redefine
    (the AL-supersedes-redefine path); other kinds are added as their creation paths get wired."""
    if not superseded:
        return
    from datetime import date as _date
    allstaff = staff_all("active")
    for d in superseded:
        if d.get("kind") != "redefine":
            continue
        iso = d.get("date") or ""
        try:
            dlabel = _date.fromisoformat(iso).strftime("%a %d/%m")
        except Exception:
            dlabel = iso
        times = ""
        if d.get("start_min") is not None and d.get("end_min") is not None:
            times = " (%s–%s)" % (_fmt_min(d["start_min"]), _fmt_min(d["end_min"]))
        line = ("🔁 %s took approved AL on %s — the shift change set for them%s no longer applies. "
                "Please re-arrange cover if needed.\n"
                "🔁 %s បានយក AL ដែលអនុម័តនៅ %s — ការប្តូរវេនដែលបានកំណត់ឱ្យ%s លែងប្រើទៀតហើយ។ "
                "សូមរៀបចំអ្នកជំនួសបើចាំបាច់។"
                % (victim_name, dlabel, times, victim_name, dlabel, times))
        sen = next((s for s in allstaff if s["id"] == d.get("senior_id")), None)
        if sen:
            await _att_send(context, (sen.get("telegram_ids") or [None])[0], "Senior",
                            sen.get("call_name") or sen["canonical_name"], line)
        await _att_send(context, None, "Supervisors group", "", line, group=True)


async def _al_finalize(context, req: dict, approved: bool) -> None:
    """On 2 ✅ or 2 ❌: recap to seniors, notify requester, (if approved) Supervisors notice + deduct."""
    if al_get_request(req["id"])["status"] != "pending":
        return  # cheap early-out; the real claim is the atomic CAS below
    requester = next((s for s in staff_all("active") if s["id"] == req["staff_id"]), None)
    if not requester:
        return
    import html
    from gm_bot import al as alm
    from gm_bot.attendance import to_min
    name = requester.get("call_name") or requester["canonical_name"]
    days = req["days"]
    # absent set EXCLUDING this request's own days — explicit so a reorder can never re-introduce the
    # self-exclusion deduct-nothing bug; is_test-scoped so a test approval never bleeds into real math.
    nw = staff_absent_dates(req["staff_id"], exclude_req_id=req["id"])
    days_txt = alm.al_span_label(days, requester.get("day_off"), nw)   # from→to, bridging any absence
    runc = requester.get("telegram_ids") or []
    sl = (to_min(requester.get("work_end")) - to_min(requester.get("work_start"))) % 1440 or 1440

    # ── settle the decision ATOMICALLY before touching any card (S1/S2/S3) ─────
    new_bal = None
    if approved:
        no_deduct = bool(req.get("no_deduct"))            # structural PH-comp flag → costs no AL
        frac = alm.fractional_al(to_min(req["hours_start"]), to_min(req["hours_end"]), sl) \
            if req["kind"] == "hours" and req.get("hours_start") else 1.0
        # frozen per-day charge (keys == days, 0 for day-off/absent/PH-comp) — refund + audit read it
        deducted_map, total = alm.al_deduction_map(days, req["kind"], frac, requester.get("day_off"),
                                                   nw, no_deduct)
        # short-notice penalty FROZEN per day (−0.1/min), judged vs the REQUEST date; none for PH-comp
        from datetime import date as _d
        created = req["created_at"].date() if req.get("created_at") else _today_pp()
        win = sl
        if req["kind"] == "hours" and req.get("hours_start"):
            win = (to_min(req["hours_end"]) - to_min(req["hours_start"])) % 1440 or sl
        points_map = {} if no_deduct else {
            d: win for d in days
            if (_d.fromisoformat(d) - created).days < alm.SHORT_NOTICE_DAYS}
        superseded: list = []
        new_bal = al_approve_and_deduct(req["id"], total, deducted_map, points_map,
                                        superseded_out=superseded)
        if new_bal == "conflict":
            # F14: another approved leave already owns one of these days — never double-book/deduct.
            # Leave the request pending (it's not a senior 'no'); just tell the requester why.
            await _att_send(context, runc[0] if runc else None, "Requester", name,
                "Couldn't approve — you already have approved leave on one of those days.\n"
                "មិនអាចអនុម័តបានទេ — ប្អូនមានច្បាប់ឈប់សម្រាកដែលអនុម័តរួចនៅថ្ងៃនោះ។")
            return
        if new_bal is None:
            return  # lost the claim — another finalize already decided this request
        # (short-notice points are written inside al_approve_and_deduct's transaction — atomic w/ deduct)
    else:
        if not al_reject(req["id"]):
            return  # lost the claim

    # EDIT the senior cards in place — request text stays intact, the decision is appended, and the
    # 👁 Show-who's-working toggle STAYS (seniors can still check coverage after the decision).
    req2 = al_get_request(req["id"])   # status now approved/rejected
    sbody, skb = _al_card(req2, requester, audience="senior", sen_id=0, show_cov=False)
    edited = 0
    for cid, mid in context.bot_data.get("al_cards", {}).pop(req["id"], []):
        try:
            await context.bot.edit_message_text(sbody, chat_id=cid, message_id=mid,
                                                reply_markup=skb, parse_mode="HTML")
            edited += 1
        except Exception:
            pass
    if not edited:   # card refs lost (e.g. a restart) → one recap so seniors still see the outcome
        for sen in _seniors(exclude_staff_id=req["staff_id"]):
            b, k = _al_card(req2, requester, audience="senior", sen_id=sen["id"], show_cov=False)
            await _att_send(context, (sen.get("telegram_ids") or [None])[0], "Senior",
                            sen.get("call_name") or sen["canonical_name"], b, kb=k, parse_mode="HTML")
    # flip the REQUESTER's own awaiting card → decided too (keeps its toggle).
    sc = context.bot_data.get("al_staff_cards", {}).pop(req["id"], None)
    if sc:
        rbody, rkb = _al_card(req2, requester, audience="staff", show_cov=False)
        try:
            await context.bot.edit_message_text(rbody, chat_id=sc[0], message_id=sc[1],
                                                reply_markup=rkb, parse_mode="HTML")
        except Exception:
            pass
    # the requester + Supervisors notices stay bilingual (the owner sees English via strip_khmer)
    if approved:
        await _att_send(context, runc[0] if runc else None, "Requester", name,
            "Your AL for %s is approved ✓. You have %g AL days left. 🤍\n"
            "AL របស់ប្អូនសម្រាប់ %s បានអនុម័តហើយ ✓។ ប្អូននៅសល់ AL %g ថ្ងៃទៀត 🤍"
            % (days_txt, new_bal, days_txt, new_bal))
        # Supervisors notice — ENGLISH-ONLY (owner, Jun 11: the bilingual twin doubled every
        # line; seniors read English). Locked format: leave + reason + day-off + BACK AT WORK
        # (the back-at-work line was promised by the locked format but missing live — added).
        day_off = requester.get("day_off") or "—"
        if req["kind"] == "hours" and req.get("hours_start"):
            span_note = "%s (%s–%s each day)" % (days_txt, _fmt_min(to_min(req["hours_start"])),
                                                 _fmt_min(to_min(req["hours_end"])))
            back = "%s each of those days (rest of shift as normal)" % _fmt_min(to_min(req["hours_end"]))
        else:
            span_note = days_txt
            bd = alm.back_at_work_date(days, requester.get("day_off"), nw)
            back = "%s, %s" % (bd.strftime("%a %d/%m"),
                               _fmt_min(to_min(requester.get("work_start")) or 0))
        # over-balance heads-up (Fable M1): two requests can each pass the submit-time gate against
        # the same balance, so an approval can still take them negative — make it VISIBLE to the
        # deciding seniors (non-blocking; the deduction stands and the number is honest, S4).
        warn = ("\n⚠ This puts %s at %g AL — over their balance." % (name, new_bal)) \
            if (new_bal is not None and new_bal < 0) else ""
        await _att_send(context, None, "Supervisors group", "",
            "%s on leave: %s.\nReason: %s\nNormal day off: %s\nBack at work: %s.%s"
            % (name, span_note, req.get("reason") or "—", day_off, back, warn), group=True)
        # schedule model: if this AL stood down a senior shift-redefine, tell that senior + supervisors
        # so coverage is re-arranged by a human (never a silent revoke). Best-effort, after the verdict.
        await _announce_supersessions(context, name, superseded)
    else:
        # owner (Jun 11): say WHICH request — they may have several pending
        await _att_send(context, runc[0] if runc else None, "Requester", name,
            "Your AL for %s wasn't approved.\nAL របស់ប្អូនសម្រាប់ %s មិនបានអនុម័តទេ។"
            % (days_txt, days_txt))


async def _payback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:pb:book:{date}:{start}:{end}:{mins} | att:pb:part:{mins} — staff books a payback slot."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if user and await _att_paused(query, user.id):   # A5: don't book during a maintenance pause
        return
    if _att_test_mode() and user.id == config.OWNER_TELEGRAM_ID:
        # test shell: the owner taps AS the persona (the callback data carries no staff id) —
        # without this branch every payback button was DEAD in /test (owner find, Jun 11)
        sid = context.user_data.get("att_persona")
        staff = next((s for s in staff_all("active") if s["id"] == sid), None) if sid else None
    else:
        staff = staff_get_by_uid(user.id)
    if not staff:
        # In test mode: att_persona lost on restart. Collapse the old message (buttons still showing
        # post-restart would keep looping the popup forever) and give the recovery tap.
        _record_dead_tap(query.data or "?")
        await _dead_tap_alarm(context, query.data or "?",
                              update.effective_user.id if update.effective_user else None)
        try:
            await query.edit_message_text(
                "⏳ Expired message — please start again.\n"
                "⏳ សារនេះផុតកំណត់ហើយ — សូមចាប់ផ្តើមម្តងទៀត។",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                    "📋 Open menu · បើក menu", callback_data="att:menu")]]))
        except Exception:
            await query.answer("⏳ Expired — try again · ផុតកំណត់ — សាកម្តងទៀត", show_alert=True)
        return
    data = query.data.split(":")
    sub = data[2] if len(data) > 2 else ""
    debt = payback_open_debt(staff["id"])
    if not debt:
        await query.edit_message_text("Your payback is already cleared ✓ / សងរួចរាល់ហើយ ✓")
        return
    remaining = _pb_remaining(staff, debt["balance"])
    if sub == "offer":
        from gm_bot.attendance_ui import _hm, day_label, fmt12
        from shared.database import payback_open_bookings
        from datetime import date as _date
        if remaining <= 0:
            await query.edit_message_text(_PB_FULLY_BOOKED)
            return
        kb = _payback_slot_keyboard(staff, remaining)
        # build the booked-slots list
        booked_slots = payback_open_bookings(staff["id"])
        booked_total = sum(b["minutes"] for b in booked_slots)
        header = ("Debt · ម៉ោងត្រូវសង: %s" % _hm(debt["balance"]))
        if booked_slots:
            slot_lines = "\n".join(
                "  %s: %s %s–%s" % (
                    _hm(b["minutes"]),
                    day_label(_date.fromisoformat(str(b["slot_date"]))),
                    fmt12(b["start_min"]),
                    fmt12(b["end_min"]),
                ) for b in booked_slots
            )
            header += ("\nBooked · បានកក់រួច: %s:\n%s" % (_hm(booked_total), slot_lines))
        text = (header + "\n\nChoose the times below to pay — these are the times we need you most:\n"
                "សូមជ្រើសម៉ោងខាងក្រោមដើម្បីសង — ពេលទាំងនេះហាងត្រូវការប្អូនបំផុត៖")
        await query.edit_message_text(text, reply_markup=kb)
        return
    if sub == "part":
        from gm_bot.attendance_ui import _hm
        if remaining <= 0:
            await query.edit_message_text(_PB_FULLY_BOOKED)
            return
        part = min(int(data[3]), remaining)
        kb = _payback_slot_keyboard({**staff}, part)
        await query.edit_message_text(
            "Pick a time for %s:\nសូមជ្រើសពេលសម្រាប់ %s៖" % (_hm(part), _hm(part)), reply_markup=kb)
        return
    if sub == "book":
        if len(data) < 7:
            # stale button from pre-guard code (< 7 parts) — show a fresh picker instead of crashing
            from gm_bot.attendance_ui import _hm
            kb = _payback_slot_keyboard(staff, remaining) if remaining > 0 else None
            if kb:
                await query.edit_message_text(
                    "You owe %s — pick when to work it off:\nប្អូននៅត្រូវសង %s — សូមជ្រើសពេលធ្វើសង៖"
                    % (_hm(debt["balance"]), _hm(debt["balance"])), reply_markup=kb)
            else:
                await query.edit_message_text(_PB_FULLY_BOOKED)
            return
        slot_date, s_min, e_min, mins = data[3], int(data[4]), int(data[5]), int(data[6])
        # HARD GATE, recomputed at tap time (buttons can be stale): never book past the
        # remaining debt, and never stack a second redefine onto a date that has one.
        from shared.database import shift_change_active
        try:
            clash = shift_change_active(staff["id"], slot_date)
        except Exception:
            clash = None
        if remaining <= 0:
            await query.edit_message_text(_PB_FULLY_BOOKED)
            return
        if mins > remaining or clash:
            from gm_bot.attendance_ui import _hm
            kb = _payback_slot_keyboard(staff, remaining)
            await query.edit_message_text(
                "That time isn't available any more — %s left to book. Pick again:\n"
                "ពេលនោះមិនអាចកក់បានទៀតទេ — នៅសល់ %s ត្រូវកក់។ សូមជ្រើសម្តងទៀត៖"
                % (_hm(remaining), _hm(remaining)), reply_markup=kb)
            return
        payback_book(debt["id"], staff["id"], slot_date, s_min, e_min, mins)
        _create_payback_redefine(staff, slot_date, s_min, e_min)   # the slot IS a redefine
        from datetime import date as _date
        d = _date.fromisoformat(slot_date)
        await query.edit_message_text(
            "Booked ✓ — %s %s-%s.\nបានកក់រួច ✓ — %s %s-%s។\n"
            "Come 5 minutes early and you earn +10 points ⭐\n"
            "មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐"
            % (d.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min),
               d.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min)))
        # plain Supervisors notice
        await _att_send(context, None, "Supervisors group", "",
            "%s pays back %s %s-%s." % (staff.get("call_name") or staff["canonical_name"],
                                       d.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min)),
            group=True)


async def _payback_ladder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily (gated): advance the ignore-ladder for unbooked debts — day-3 warn, day-4 auto-book.
    (The calm daily check-in line is delivered by the check-in flow; this job handles warn/autobook.)
    Runs in live OR test mode; payback_all_open() returns the matching dataset (real vs is_test),
    and _att_send routes to the owner in test."""
    if not _job_gate():
        return
    from gm_bot import payback as pb
    from shared.database import ot_shield_until
    today = _today_pp()
    for debt in payback_all_open():
        staff = next((s for s in staff_all("active") if s["id"] == debt["staff_id"]), None)
        if not staff or not (staff.get("telegram_ids") or []):
            continue
        # OT SHIELD (OT_DESIGN §4): an agreed upcoming OT landing before this debt's deadline will
        # clear it at checkout — pause warn/auto-book while it stands. Stateless: decline / re-edit
        # to no-OT / absence (date passes) simply stop matching and the ladder resumes next run.
        if debt.get("created_date"):
            from datetime import timedelta as _sd
            ddl = (debt["created_date"] + _sd(days=pb.PB_DEADLINE_DAYS)).isoformat()
            if ot_shield_until(debt["staff_id"], today.isoformat(), ddl):
                continue
        uid = staff["telegram_ids"][0]
        # ladder days = calendar days since created MINUS legitimate-leave days (freeze rule) and the
        # staff's day-off weekday (they can still tap, but we don't count it as a chance missed)
        from datetime import timedelta as _td
        leave = al_leave_days_set(debt["staff_id"])
        off = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5,
               "sun": 6}.get((staff.get("day_off") or "")[:3].lower())
        days = 0
        if debt.get("created_date"):
            d = debt["created_date"]
            while d < today:
                d += _td(days=1)
                if d.isoformat() not in leave and d.weekday() != off:
                    days += 1
        stage = pb.ignore_stage(days)
        nm = staff.get("call_name") or staff["canonical_name"]
        # fully-booked debts never warn/auto-book — the booked time already covers them
        # (the shield usually pauses these, but a booking landing past the deadline wouldn't)
        remaining = _pb_remaining(staff, debt["balance"])
        if remaining <= 0:
            continue
        try:
            if stage == "warn":
                await _att_send(context, uid, "Staff", nm,
                    "Pick before tomorrow, or I'll pick for you.\n"
                    "សូមជ្រើសមុនថ្ងៃស្អែក។ បើអ្នកមិនទាន់ជ្រើសទេ ខ្ញុំនឹងជ្រើសជូនអ្នក។",
                    kb=_payback_slot_keyboard(staff, remaining))
            elif stage == "autobook":
                from gm_bot import payback as _pb
                from gm_bot.attendance import to_min
                ws, we = to_min(staff.get("work_start")), to_min(staff.get("work_end"))
                taken = _sc_taken_dates(debt["staff_id"])
                days_ahead = [d for d in _pb.working_days_ahead(staff.get("day_off"), set(),
                                                                today, 7, 3)
                              if d.isoformat() not in taken][:1]
                if ws is not None and we is not None and days_ahead:
                    d0 = days_ahead[0]
                    normal_len = ((we - ws) % 1440) or 1440
                    amt = min(remaining, _pb.day_ext_cap(normal_len))   # 15h-total-day cap
                    _lbl, s_min, e_min = _pb.slot_windows(ws, we, amt)[0]
                    payback_book(debt["id"], staff["id"], d0.isoformat(), s_min, e_min,
                                 amt, auto_booked=True)
                    _create_payback_redefine(staff, d0.isoformat(), s_min, e_min)
                    await _att_send(context, uid, "Staff", nm,
                        "I booked you %s %s-%s (you didn't choose).\n"
                        "ខ្ញុំបានកក់ពេលឱ្យអ្នក %s %s-%s (ព្រោះអ្នកមិនបានជ្រើស)។"
                        % (d0.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min),
                           d0.strftime("%a %d/%m"), _fmt_min(s_min), _fmt_min(e_min)))
        except Exception as e:
            logger.error("payback ladder for %s failed: %s", debt["staff_id"], e)


def _open_sick_case(staff_id: int) -> dict | None:
    """Most recent open/provisional own-sick case for a staff (papers attach to it)."""
    for c in sick_provisional_open():
        if c["staff_id"] == staff_id:
            return c
    return None


async def _handle_sick_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Gated: a staff with an open own-sick case sends a photo → Opus reads it → owner card.
    Returns True if handled. Papers go ONLY to owner+Tyty; never analysed in a death context."""
    if not _att_active():
        return False
    msg = update.message
    if not msg or not msg.photo or not update.effective_user:
        return False
    if _att_test_mode() and update.effective_user.id == config.OWNER_TELEGRAM_ID:
        # test: the owner-as-persona sends the papers photo
        sid = context.user_data.get("att_persona")
        staff = next((s for s in staff_all("active") if s["id"] == sid), None) if sid else None
    else:
        staff = staff_get_by_uid(update.effective_user.id)
    if not staff or staff.get("status") != "active":
        return False
    # DEATH CONTEXT (owner — was preview-only until Jun 11): a photo within a week of a death
    # leave gets condolence ONLY — no AI ever reads it; forwarded to owner+Tyty alone.
    from shared.database import death_leave_recent
    if death_leave_recent(staff["id"], (_today_pp() - timedelta(days=7)).isoformat()):
        # owner: condolence ONLY — never "no need to send"; photos SHOULD keep coming to us
        await msg.reply_text(
            "We're so sorry for your loss 🤍\n"
            "យើងសូមចូលរួមរំលែកទុក្ខចំពោះការបាត់បង់នេះ 🤍")
        for oid in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
            if not oid:
                continue
            try:
                await context.bot.forward_message(oid, msg.chat_id, msg.message_id)
            except Exception:
                pass
        return True
    case = _open_sick_case(staff["id"])
    if not case:
        return False
    sick_set(case["id"], papers_seen=True)
    await msg.reply_text("Got your papers ✓ sending to the owner.\n"
                         "បានទទួលឯកសាររបស់អ្នក ✓ កំពុងផ្ញើទៅម្ចាស់ហាង។")
    try:
        photo = await msg.photo[-1].get_file()
        data = bytes(await photo.download_as_bytearray())
        info = await read_medical_paper(data)
    except Exception as e:
        logger.error("sick paper read failed: %s", e)
        info = {"is_medical": False, "_error": True, "rest_days": None,
                "contagious": False, "part_duty_possible": False}
    name = staff.get("call_name") or staff["canonical_name"]
    adv = ("🩺 %s — sick papers\n" % name)
    if info.get("_error"):
        adv += "(couldn't read — see the photo)\n"
    else:
        adv += ("Opus: %s · %s · likely %s · %s\n"
                % (info.get("hospital") or "?", info.get("reasoning") or "—",
                   ("%sd" % info["rest_days"]) if info.get("rest_days") else "no period stated",
                   "CONTAGIOUS — no come-in" if info.get("contagious") else "not contagious"))
    rows = [[InlineKeyboardButton("✓ Accept (cover %s)" % (("%sd" % info["rest_days"])
                                                           if info.get("rest_days") else "1d"),
                                  callback_data="att:sp:cov:%d:%d" % (case["id"], info.get("rest_days") or 1))],
            [InlineKeyboardButton("1d", callback_data="att:sp:cov:%d:1" % case["id"]),
             InlineKeyboardButton("2d", callback_data="att:sp:cov:%d:2" % case["id"]),
             InlineKeyboardButton("3d", callback_data="att:sp:cov:%d:3" % case["id"])]]
    if info.get("part_duty_possible") and not info.get("contagious"):
        rows.append([InlineKeyboardButton("💺 Offer part-duty (%s)" % (info.get("suggested_jobs") or "light"),
                                          callback_data="att:sp:duty:%d" % case["id"])])
    rows.append([InlineKeyboardButton("Skip → nightly nudges", callback_data="att:sp:cov:%d:0" % case["id"])])
    # papers go to owner + Tyty only
    for oid in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        if not oid:
            continue
        try:
            await context.bot.send_message(oid, adv, reply_markup=InlineKeyboardMarkup(rows))
            await context.bot.forward_message(oid, msg.chat_id, msg.message_id)
        except Exception:
            pass
    return True


def _tyty_uid() -> int | None:
    t = next((s for s in staff_all() if s["canonical_name"] == "Tyty"), None)
    ids = (t or {}).get("telegram_ids") or []
    return ids[0] if ids else None


# The nightly nudge is a RETURN CHECK only — never mentions papers or pay-back (they already know
# paperless sick is paid back; papers are mentioned once at declaration).
_SICK_RETURN_CHECK = ("I hope you're feeling better now 🤍 Are you coming in tomorrow?\n"
                      "សង្ឃឹមថាប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?")


def _wipe_sick_payback(staff_id: int, the_date_iso: str) -> bool:
    """Cancel the paperless-sick pay-back debt for this sick date (accepted papers within window)."""
    for d in payback_all_open():
        if (d["staff_id"] == staff_id and "sick" in (d.get("reason") or "").lower()
                and str(d.get("created_date")) == the_date_iso and d["balance"] > 0):
            payback_credit(d["id"], d["balance"])
            return True
    return False


def _sick_return_kb(case_id: int) -> InlineKeyboardMarkup:
    """Return-check buttons on the nightly nudge. Owner (Jun 11): no one-tap opt-out — staying
    out requires a typed reason that the Supervisors read (warm but accountable)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Coming in tomorrow · ស្អែកមកធ្វើការ", callback_data="att:sret:yes:%d" % case_id)],
        [InlineKeyboardButton("📝 Still resting — explain · សម្រាកបន្ត — ពន្យល់",
                              callback_data="att:sret:no:%d" % case_id)],
        [InlineKeyboardButton("⏰ Coming in today at… · ថ្ងៃនេះមកម៉ោង…", callback_data="att:sret:today:%d" % case_id)],
    ])


NUDGE_FLOWS = {"sfam_exp", "sret_exp", "sick_me", "rej_exp"}   # the bounded 10/20/30 ladder


def _arm_reason(context, update, pend: dict) -> None:
    """Arm the next typed message as a REQUIRED reason, with the 10/20/30 nudge-ladder metadata
    (owner, Jun 11: 'they might think it's all known now that they tapped'). Test: owner shell;
    live: the tapper's next text — 35-min window so the ladder can finish before expiry."""
    from gm_bot.attendance_ui import _supersede_prev_pend
    _supersede_prev_pend(context, update)   # honesty: relabel any prompt this one overwrites
    pend = dict(pend)
    pend["armed_at"] = _now_pp().isoformat()
    pend["nudges"] = 0
    if _att_test_mode():
        context.user_data["att_test_pending"] = pend
    else:
        from shared.database import flow_save
        flow_save(update.effective_user.id, "att_pending", "reason", pend, ttl_min=35)


def _arm_sick_explain(context, update, flow: str, case_id: int, staff_id: int) -> None:
    """Arm the explain-reason for a sick nudge (rides the generic _arm_reason ladder)."""
    _arm_reason(context, update, {"flow": flow, "case_id": case_id, "persona_id": staff_id})


async def _ask_reason(query, to_name: str) -> None:
    """The type-it-here prompt right after a decline tap — says WHERE the reason goes."""
    try:
        await query.message.reply_text(
            "📝 One line why — it goes to %s.\n📝 មូលហេតុ 1 ឃ្លា — នឹងផ្ញើទៅ %s។"
            % (to_name, to_name))
    except Exception:
        pass


def _sret_time_kb(case_id: int) -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(_fmt_min(h * 60), callback_data="att:sret:t:%d:%d" % (case_id, h * 60))
            for h in range(7, 21)]
    return InlineKeyboardMarkup([btns[i:i + 4] for i in range(0, len(btns), 4)])


async def _sick_return_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:sret:{yes|no|today|t}:{case}[:{min}] — the sick staff's return answer → Supervisors FYI."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action, case_id = parts[2], int(parts[3])
    case = sick_get(case_id)
    if not case:
        return
    staff = next((s for s in staff_all("active") if s["id"] == case["staff_id"]), None)
    nm = (staff.get("call_name") or staff["canonical_name"]) if staff else "Staff"
    if action == "yes":
        await query.edit_message_text("Great — see you tomorrow 🤍\nឃើញគ្នាស្អែក 🤍")
        await _att_send(context, None, "Supervisors group", "",
            "FYI: %s is well enough to return TOMORROW.\nFYI: %s នឹងវិលត្រឡប់មកធ្វើការវិញនៅថ្ងៃស្អែក។"
            % (nm, nm), group=True)
    elif action == "no":
        # owner (Jun 11): no one-tap stay-out — the reason is typed and the Supervisors read it
        _arm_sick_explain(context, update, "sret_exp", case_id, case["staff_id"])
        await query.edit_message_text(
            "Please type the reason — it goes to the Supervisors. 🤍\n"
            "សូមវាយមូលហេតុ — វានឹងផ្ញើទៅបងៗ។ 🤍")
    elif action == "today":
        await query.edit_message_text("What time today?\nម៉ោងប៉ុន្មានថ្ងៃនេះ?", reply_markup=_sret_time_kb(case_id))
    elif action == "t":
        m = int(parts[4])
        await query.edit_message_text("See you at %s today 🤍\nឃើញគ្នាម៉ោង %s ថ្ងៃនេះ 🤍"
                                      % (_fmt_min(m), _fmt_min(m)))
        await _att_send(context, None, "Supervisors group", "",
            "FYI: %s is coming in TODAY at %s.\nFYI: %s នឹងមកធ្វើការថ្ងៃនេះ ម៉ោង %s។"
            % (nm, _fmt_min(m), nm, _fmt_min(m)), group=True)


async def _sick_paper_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:sp:cov:{case}:{days} | att:sp:duty:{case} — owner decides on sick papers."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    sub, case_id = parts[2], int(parts[3])
    # cov/duty are the OWNER's decision; come/rest are the STAFF's (owner stands in during test).
    if sub in ("cov", "duty") and update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    case = sick_get(case_id)
    if not case:
        return
    staff = next((s for s in staff_all("active") if s["id"] == case["staff_id"]), None)
    uid = (staff.get("telegram_ids") or [None])[0] if staff else None
    nm0 = (staff.get("call_name") or staff["canonical_name"]) if staff else ""
    if sub == "cov":
        days = int(parts[4])
        if days:
            # papers accepted → CANCEL the paperless-sick pay-back, but only within the 2-day window
            from gm_bot import sick as sk
            within = not sk.papers_deadline_passed(case["the_date"], _today_pp())
            wiped = _wipe_sick_payback(case["staff_id"], case["the_date"].isoformat()) if within else False
            sick_set(case_id, status="papered", covered_days=days)
            await query.edit_message_text(query.message.text + ("\n\n✓ Covered %dd%s." % (
                days, " — pay-back cancelled" if wiped else " (after 2-day window — pay-back stands)"
                if not within else "")))
            await _att_send(context, uid, "Staff", nm0,
                "Saved ✓ — your sick day is confirmed. Get well 🤍\n"
                "រក្សាទុករួច ✓ — ថ្ងៃឈឺរបស់អ្នកបានបញ្ជាក់ហើយ។ សូមឱ្យឆាប់ជាសះស្បើយ 🤍")
            await _att_send(context, None, "Supervisors group", "",
                "FYI: %s is on covered sick leave for %d day(s).\nFYI: %s សុំច្បាប់ឈឺមានឯកសារ %d ថ្ងៃ។"
                % (nm0, days, nm0, days), group=True)
        else:
            # no cover — the pay-back created at declaration just stands (don't spell it out to them)
            sick_set(case_id, status="provisional")
            await query.edit_message_text(query.message.text + "\n\n✓ Noted.")
            if _att_test_mode():   # show the next step (the nightly return-check) so the test continues
                await _att_send(context, uid, "Staff", nm0, _SICK_RETURN_CHECK,
                                kb=_sick_return_kb(case_id))
    elif sub == "duty":
        await query.edit_message_text(query.message.text + "\n\n💺 Part-duty offered.")
        if uid or _att_test_mode():
            await _att_send(context, uid, "Staff",
                staff.get("call_name") or staff["canonical_name"] if staff else "",
                "Feeling a little better? If you're up to it, there's light work today (+15 points ⭐) — "
                "only if you truly feel able 🤍\n"
                "ធូរស្បើយបន្តិចហើយឬនៅ? បើអ្នកមានកម្លាំង អាចមកធ្វើការងារស្រាលៗថ្ងៃនេះបាន (+15 points ⭐) — "
                "តែបើអ្នកពិតជាអាចធ្វើបានប៉ុណ្ណោះ 🤍",
                kb=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💪 I can come · ខ្ញុំអាចមក", callback_data="att:sp:come:%d" % case_id)],
                    [InlineKeyboardButton("🛌 Rest today · សម្រាកថ្ងៃនេះ", callback_data="att:sp:rest:%d" % case_id)]]))
    elif sub == "come":
        # staff opted into part-duty (whole day stays papered; +15 gift; relaxed check-out)
        try:
            points_record(case["staff_id"], "return_after_doctor", 1, "part_duty")
        except Exception:
            pass
        await query.edit_message_text(
            "Thank you for coming in 🤍 light duty only — a senior will point you to seated/easy work.\n"
            "អរគុណដែលមកជួយ 🤍 ធ្វើតែការងារស្រាលៗប៉ុណ្ណោះ — បងៗនឹងណែនាំការងារអង្គុយ ឬការងារងាយៗឱ្យអ្នក។")
        # tell the Supervisors group (the seniors are already in there — no need to DM each)
        _ldn = (staff.get("call_name") or staff["canonical_name"]) if staff else "Staff"
        await _att_send(context, None, "Supervisors group", "",
            "%s is coming on LIGHT DUTY today — please give easy/seated work only.\n"
            "%s នឹងមកធ្វើ LIGHT DUTY ថ្ងៃនេះ — សូមឱ្យធ្វើតែការងារងាយៗ/អង្គុយប៉ុណ្ណោះ។"
            % (_ldn, _ldn), group=True)
    elif sub == "rest":
        await query.edit_message_text("Get well 🤍 rest today.\nសូមឱ្យឆាប់ជាសះស្បើយ 🤍 សម្រាកថ្ងៃនេះ។")


async def _callout_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Weekly (gated): detect lateness patterns → autonomous call-out (Sonnet private + Opus group),
    CC owner + Tyty. Throttled once per staff per ISO-week so it never nags."""
    if not _attendance_live():
        return
    from gm_bot import frequency as fq
    now = datetime.now(finance.PP_TZ)
    if now.weekday() != 0:   # Mondays only
        return
    today = now.date()
    wkstamp = today.strftime("%G-W%V")
    for s in staff_all("active"):
        if s.get("org") != "TWB" or s["canonical_name"] == "Tyty":
            continue
        pat = fq.detect(lateness_dates(s["id"]), today)
        if not pat:
            continue
        stamp = "callout_done:%d:%s" % (s["id"], wkstamp)
        if gm_get_state(stamp) == "true":
            continue
        gm_set_state(stamp, "true")
        call = s.get("call_name") or s["canonical_name"]
        dossier = "%s (%s)" % (pat["flag"], pat["detail"])
        uids = s.get("telegram_ids") or []
        try:
            priv = await generate_callout(dossier, call, "private")
            if priv and uids:
                await context.bot.send_message(uids[0], priv)
            # the anonymous GROUP line fires at most ONCE per week, no matter how many staff
            # pattern-matched that Monday ("says it once and goes quiet" — owner, Jun 11)
            grp = None
            gstamp = "callout_group_done:%s" % wkstamp
            if gm_get_state(gstamp) != "true":
                grp = await generate_callout(dossier, call, "group")
                if grp:
                    gm_set_state(gstamp, "true")
                    await context.bot.send_message(config.SUPERVISORS_CHAT_ID, grp)
            # CC both owners
            for oid in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
                if oid:
                    await context.bot.send_message(oid,
                        "📣 Call-out sent — %s (%s).\nPrivate: %s\nGroup: %s"
                        % (call, pat["detail"], priv[:120],
                           grp[:120] if grp else "(already said this week)"))
        except Exception as e:
            logger.error("callout for %s failed: %s", call, e)


async def _no_show_sweep_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily 08:00 PP (gated): yesterday's scheduled staff who never checked in AND had no
    approved leave/sick = no-show → record + points event + owner note (1 day's pay, owner-gated)."""
    if not _job_gate(live_only=True):
        return
    from gm_bot import attendance_ui as ui
    from gm_bot.attendance import to_min
    yday = (_today_pp() - timedelta(days=1))
    for p in staff_all("active"):
        if p.get("org") != "TWB" or p["canonical_name"] == "Tyty":
            continue
        # did they work yesterday's shift? (schedule, honoring overrides + leave)
        try:
            ev = ui.compute_day_events(yday)
        except Exception:
            ev = []
        names = {n for _m, n, _l, _t, _sd in ev}
        nm = p.get("call_name") or p["canonical_name"]
        if nm not in names:
            continue   # not scheduled (day-off/AL/PH) — not a no-show
        sess = att_get_session(p["id"], yday.isoformat())
        if sess and sess.get("checked_in_at"):
            continue   # they checked in
        if no_show_record(p["id"], yday.isoformat()):
            ws, we = to_min(p.get("work_start")), to_min(p.get("work_end"))
            shift_min = ((we - ws) % 1440 or 1440) if ws is not None and we is not None else 540
            try:
                points_record(p["id"], "no_show", shift_min, yday.isoformat())
            except Exception:
                pass
            try:
                await context.bot.send_message(config.OWNER_TELEGRAM_ID,
                    "🚫 NO-SHOW: %s, %s. Suggested: cut 1 day's pay + bonus not earned (your call)."
                    % (nm, yday.strftime("%a %d/%m")))
            except Exception:
                pass
            await _att_send(context, None, "Supervisors group", "",   # informational (decided next morning)
                "🚫 No-show: %s did not come for %s's shift.\n🚫 អវត្តមាន៖ %s មិនបានមកធ្វើការវេន %s។"
                % (nm, yday.strftime("%a %d/%m"), nm, yday.strftime("%a %d/%m")), group=True)


async def _sick_papers_deadline_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily (gated): while an own-sick case is open, send a nightly RETURN CHECK ('coming in
    tomorrow?') — never about papers or pay-back. The pay-back was created at declaration; after the
    2-day papers window with no accepted papers the case is finalized and nudges stop. No debt is
    created here (paperless sick is already pay-back from the start)."""
    if not _job_gate():
        return
    from gm_bot import sick as sk
    today = _today_pp()
    for c in sick_provisional_open():
        staff = next((s for s in staff_all("active") if s["id"] == c["staff_id"]), None)
        if not staff:
            continue
        uid = (staff.get("telegram_ids") or [None])[0]
        nm = staff.get("call_name") or staff["canonical_name"]
        if sk.papers_deadline_passed(c["the_date"], today):
            sick_set(c["id"], status="no_papers")   # window closed; the pay-back made at declaration stands
            continue
        await _att_send(context, uid, "Staff", nm, _SICK_RETURN_CHECK, kb=_sick_return_kb(c["id"]))
    # FAMILY-sick night nudge (owner — was preview-only until Jun 11): the family day was today;
    # one tap books tomorrow too (burns another of the 7 yearly family days) or closes the case.
    from shared.database import sick_family_open_today
    for c in sick_family_open_today(today.isoformat()):
        staff = next((s for s in staff_all("active") if s["id"] == c["staff_id"]), None)
        if not staff:
            continue
        uid = (staff.get("telegram_ids") or [None])[0]
        nm = staff.get("call_name") or staff["canonical_name"]
        # owner (Jun 11): expectation-first wording — coming is the default, staying out costs a
        # typed reason the Supervisors read (the old "tell me if you need tomorrow off" made the
        # easy no too easy).
        who = c.get("who") or "family member"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Coming tomorrow · ស្អែកមកធ្វើការ",
                                  callback_data="att:sfam:ok:%d" % c["id"])],
            [InlineKeyboardButton("📝 Can't come — explain · មកមិនបាន — ពន្យល់",
                                  callback_data="att:sfam:exp:%d" % c["id"])]])
        await _att_send(context, uid, "Staff", nm,
            "I hope your %s is better now 🤍 Are you coming tomorrow?\n"
            "សង្ឃឹមថា %s របស់ប្អូនធូរស្បើយហើយ 🤍 ស្អែកប្អូនមកធ្វើការមែនទេ?"
            % (who, _who_kh(who)), kb=kb)


async def _sfam_book(context, case: dict, reason: str) -> None:
    """Book TOMORROW as a continued family-sick day (status-first) + the Supervisors read the
    reason. Shared by the typed-reason dispatch and the 30-min auto-resolve."""
    sick_set(case["id"], status="extended")
    tmr = (_today_pp() + timedelta(days=1)).isoformat()
    sick_create(case["staff_id"], case.get("who") or "family", tmr, "open")
    stf = next((s for s in staff_all("active") if s["id"] == case["staff_id"]), None)
    nm = (stf or {}).get("call_name") or (stf or {}).get("canonical_name", "Staff")
    await _att_send(context, None, "Supervisors group", "",
        "FYI: %s's family-sick continues tomorrow (%s).\n"
        "FYI: %s បន្តសុំច្បាប់ឈឺសម្រាប់%sដល់ថ្ងៃស្អែក។\n"
        "Reason · មូលហេតុ៖ %s"
        % (nm, case.get("who") or "family", nm, _who_kh(case.get("who") or "family"), reason),
        group=True)


async def _sickme_book(context, persona: dict, date_iso: str, reason: str) -> None:
    """Day-1 own-sick booking (provisional case + paperless payback + rest-well + the FYI with
    the reason). Shared by the typed-reason dispatch and the 30-min auto-resolve."""
    sick_create(persona["id"], "me", date_iso, "provisional")
    from gm_bot.attendance import to_min
    ws, we = to_min(persona.get("work_start")), to_min(persona.get("work_end"))
    shift_min = ((we - ws) % 1440 or 1440) if ws is not None and we is not None else 540
    payback_add_debt(persona["id"], shift_min, "paperless sick", date_iso)
    await _att_send(context, (persona.get("telegram_ids") or [None])[0], "Staff",
        persona.get("call_name") or persona["canonical_name"],
        "OK — rest well 🤍 If you see a doctor, send me a photo of the papers.\n"
        "បានហើយ — សម្រាកឱ្យបានល្អ 🤍 បើអ្នកបានទៅជួបពេទ្យ សូមផ្ញើរូបថតឯកសារពេទ្យមកខ្ញុំ។")
    _snm = persona.get("call_name") or persona["canonical_name"]
    await _att_send(context, None, "Supervisors group", "",
        "FYI: %s is out sick today.\nFYI: %s សុំច្បាប់ឈឺថ្ងៃនេះ។\nReason · មូលហេតុ៖ %s"
        % (_snm, _snm, reason), group=True)


async def _sick_family_nudge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:sfam:ok|exp:{case_id} — the family-sick night nudge (owner Jun 11: coming is the
    DEFAULT; staying out requires a typed reason the Supervisors read — no one-tap easy no).
    'ok' = coming tomorrow → case cleared; 'exp' (and the legacy 'again') arms the next typed
    message as the reason — the booking happens in the dispatch branch, status-first."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    act, cid = parts[2], int(parts[3])
    case = sick_get(cid)
    if not case or case.get("status") != "open":
        return await _expired_toast(query, context, update.effective_user.id if update.effective_user else None)      # already answered (or stale) — never act twice
    if act == "ok":
        sick_set(cid, status="cleared")
        await query.edit_message_text("Great — see you tomorrow 🤍\nឃើញគ្នាស្អែក 🤍")
        return
    _arm_sick_explain(context, update, "sfam_exp", cid, case["staff_id"])
    await query.edit_message_text(
        "Please type the reason — it goes to the Supervisors. 🤍\n"
        "សូមវាយមូលហេតុ — វានឹងផ្ញើទៅបងៗ។ 🤍")


async def _reason_nudge_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Every 5 min (gated): the BOUNDED 10/20/30 ladder for armed reason-prompts (owner, Jun 11:
    'they might think tapping was enough'). +10 and +20 min → a gentle nudge; +30 min of silence
    → auto-resolve so nothing dangles: sick flows BOOK with '(no reason given — asked 3×)' (the
    shop covers reality, the non-compliance is visible to the seniors); a rejection's reason is
    simply dropped (the decision already stood). LIVE pends only — the owner's test shell keeps
    its pends in user_data and needs no nudging."""
    if not _job_gate():
        return
    from shared.database import flow_pending_reasons, flow_save, flow_clear
    now = _now_pp()
    marker = "(no reason given — asked 3×)"
    for row in flow_pending_reasons():
        pend = row["data"]
        if pend.get("flow") not in NUDGE_FLOWS or not pend.get("armed_at"):
            continue
        try:
            armed = datetime.fromisoformat(pend["armed_at"])
        except Exception:
            continue
        age = (now - armed).total_seconds()
        uid = row["uid"]
        if age >= 1800:
            fl = pend["flow"]
            try:
                if fl == "sfam_exp":
                    case = sick_get(pend.get("case_id"))
                    if case and case.get("status") == "open":
                        await _sfam_book(context, case, marker)
                elif fl == "sret_exp":
                    case = sick_get(pend.get("case_id"))
                    stf = next((s for s in staff_all("active")
                                if s["id"] == (case or {}).get("staff_id")), None)
                    if stf:
                        nm = stf.get("call_name") or stf["canonical_name"]
                        await _att_send(context, None, "Supervisors group", "",
                            "FYI: %s is still resting — NOT back tomorrow.\n"
                            "FYI: %s នៅតែសម្រាក — ស្អែកមិនទាន់មកធ្វើការទេ។\n"
                            "Reason · មូលហេតុ៖ %s"
                            % (nm, nm, marker), group=True)
                elif fl == "sick_me":
                    persona = next((s for s in staff_all("active")
                                    if s["id"] == pend.get("persona_id")), None)
                    if persona and pend.get("date"):
                        await _sickme_book(context, persona, pend["date"], marker)
                # rej_exp: the decision already stood — silence just drops the explanation
            except Exception as e:
                logger.error("reason auto-resolve failed (%s): %s", fl, e)
            flow_clear(uid)
            continue
        n = int(pend.get("nudges", 0))
        if n < 2 and age >= 600 * (n + 1):
            try:
                await context.bot.send_message(uid,
                    "Still need one line from you 🤍 just type why.\n"
                    "នៅខ្វះមូលហេតុ 1 ឃ្លាពីប្អូន 🤍 សូមវាយប្រាប់មូលហេតុ។")
            except Exception:
                pass
            pend["nudges"] = n + 1
            flow_save(uid, "att_pending", "reason", pend, ttl_min=35)


async def _booking_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gated, hourly: 12h-before reminder for booked payback slots (reward-neutral, encouraging)."""
    if not _job_gate():
        return
    from datetime import datetime as _dt
    now = _now_pp()
    for b in payback_bookings_due_reminder():
        ids = b.get("telegram_ids")
        try:
            import json as _json
            ids = _json.loads(ids) if isinstance(ids, str) else (ids or [])
        except Exception:
            ids = []
        if not ids:
            continue
        slot_dt = _dt.combine(b["slot_date"], _dt.min.time()).replace(tzinfo=finance.PP_TZ) \
            + __import__("datetime").timedelta(minutes=b["start_min"])
        hrs = (slot_dt - now).total_seconds() / 3600
        if not (0 < hrs <= 12):
            continue
        await _att_send(context, ids[0], "Staff", b.get("call_name") or b.get("canonical_name") or "",
            "Reminder — your payback time is %s %s.\n"
            "រំលឹក — ម៉ោងសងវិញរបស់អ្នកគឺ %s %s។\n"
            "Come 5 minutes early and you earn +10 points ⭐\n"
            "មកដល់មុន 5 នាទី ប្អូននឹងទទួលបាន +10 points ⭐"
            % (b["slot_date"].strftime("%a %d/%m"), _fmt_min(b["start_min"]),
               b["slot_date"].strftime("%a %d/%m"), _fmt_min(b["start_min"])))
        payback_mark_reminded(b["id"])


async def _al_accrual_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monthly +1.5 AL on the 1st (Phnom Penh) for active TWB staff (arrears: a new hire's
    first 1.5 lands the month after their first FULL calendar month). Idempotent via gm_state
    stamp so a restart on the 1st can't double-credit. Gated off the live switch is NOT needed —
    accrual is bookkeeping, safe to run regardless, but we still skip if attendance not set up."""
    now_pp = datetime.now(finance.PP_TZ)
    if now_pp.day != 1:
        return
    stamp = "al_accrual_done:%s" % now_pp.strftime("%Y-%m")
    if gm_get_state(stamp) == "true":
        return
    credited = []
    for s in staff_all("active"):
        if s.get("org") != "TWB" or s["canonical_name"] == "Tyty":
            continue
        # arrears: skip if their first full month hasn't elapsed (no created/start date tracked yet →
        # credit everyone seeded; new hires handled when join-date field exists). Conservative: credit.
        try:
            al_deduct(s["id"], -1.5)   # negative deduct = credit
            credited.append(s.get("call_name") or s["canonical_name"])
        except Exception as e:
            logger.error("accrual for %s failed: %s", s["canonical_name"], e)
    gm_set_state(stamp, "true")
    try:
        await context.bot.send_message(config.OWNER_TELEGRAM_ID,
            "🏖 Monthly AL accrual +1.5 applied to %d staff (%s)." % (len(credited), now_pp.strftime("%b %Y")))
    except Exception:
        pass


async def _al_deduction_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """07:05 PP daily: deduct planned-AL days that have passed (owner, session 28).
    PH-compensation leaves are never deducted. Owner gets a one-line note per deduction."""
    today = datetime.now(finance.PP_TZ).date().isoformat()
    try:
        applied = al_apply_due_deductions(today)
        for a in applied:
            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="🏖 AL deducted: %s −%d (%s) → %.1f left"
                     % (a["name"], len(a["days"]), ", ".join(a["days"]), a["new_balance"]))
    except Exception as e:
        logger.error("AL deduction job failed: %s", e)


async def _missing_mid_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """17:30 PP: today's midday report should be in by now (session 28 existence watchdog)."""
    day = datetime.now(finance.PP_TZ).date().isoformat()
    try:
        rows = get_daily_reports_for_day(day)
        if not any(r.get("report_kind") == "mid" for r in rows):
            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="⏰ No midday report in TWB REPORT for %s yet (17:30)." % day)
    except Exception as e:
        logger.error("missing-mid check failed: %s", e)


async def _missing_final_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """06:30 PP: the business day that just closed must have its final report."""
    day = (datetime.now(finance.PP_TZ).date() - timedelta(days=1)).isoformat()
    try:
        rows = get_daily_reports_for_day(day)
        if not any(r.get("report_kind") == "final" for r in rows):
            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="🚨 No FINAL report stored for business day %s (checked 06:30). "
                     "The day's books are missing — staff didn't post, or collection is down." % day)
    except Exception as e:
        logger.error("missing-final check failed: %s", e)


async def _resolve_report_math_if_fixed(context, chat_id: int, full: dict, fixed_msg, via: str) -> None:
    """A now-correct report (edited in place, or re-posted) closes its open report_math
    clarification and gets ACKNOWLEDGED in-group (session 28 — staff must see the fix landed)."""
    if not full or not full["computed"].get("math_ok", False):
        return
    opens = [c for c in gm_get_active_clarifications_for_chat(chat_id)
             if c["topic"] == "report_math"]
    if not opens:
        return
    targets = [c for c in opens if c.get("target_msg_id") == fixed_msg.message_id]
    if not targets and len(opens) == 1:
        targets = opens  # one open case + one correct report = obviously the fix
    if not targets:
        return
    for c in targets:
        gm_answer_clarification(c["id"], "(report corrected via %s — math checks out)" % via)
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✓ Corrected — it checks out now, thank you!\n"
                 "✓ កែរួចហើយ — ឥឡូវនេះត្រឹមត្រូវហើយ អរគុណ!",
            reply_to_message_id=fixed_msg.message_id,
        )
    except Exception:
        pass
    logger.info("report_math clarification auto-resolved via %s", via)


async def _edited_group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Edits used to be invisible (session 28). Two real cases:
    1. staff fix a REPORT by editing it -> re-parse; correct math closes the case + thanks them;
    2. staff complete an ANSWER by editing it ("...but we can not find it") -> the edited text
       runs through clarification resolution + the judge, any group."""
    msg = update.edited_message
    if not msg:
        return
    text = msg.text or msg.caption or ""
    if not text.strip():
        return
    if msg.chat_id == config.DAILY_REPORT_CHAT_ID:
        try:
            full = await _store_daily_report_if_any(msg, text)  # idempotent update, same message_id
            if full is not None:
                await _resolve_report_math_if_fixed(context, msg.chat_id, full, msg, "edit")
                return  # it was a report — done
        except Exception as e:
            logger.error("edited report handling failed: %s", e)
    # edited answer to an open clarification (any group)
    try:
        resolved = _resolve_clarification_response(msg.chat_id, msg, text)
        if resolved:
            await _judge_clarification(context, resolved["clar"], resolved["answer"], answer_msg=msg)
    except Exception as e:
        logger.error("edited answer handling failed: %s", e)


async def _maybe_correct_report(context, msg, full: dict) -> None:
    """On a math error, send the worked-out correction. Owner-gated: goes to the owner
    privately until gm_state 'report_corrections_to_staff' is 'true', then in-group tagged."""
    computed = full["computed"]
    if computed.get("math_ok", True):
        return
    correction = finance.format_correction(full["raw"], computed)
    if not correction:
        return
    body = (f"📊 Report math check · ពិនិត្យគណនារបាយការណ៍ — "
            f"{full['business_day']} ({full['report_kind']})\n\n{correction}")
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
                            chat_id=chat_id, text="Noted, thank you. ✓\nកត់ចំណាំហើយ អរគុណ។ ✓",
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
    if not config.GM_ATTENDANCE_GROUP_ACTIVE:
        return
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


def _leave_questions(said_al: bool, leave_type: str, dates) -> list[str]:
    """Pure: which clarifying questions a leave announcement needs. Empty list = complete.
    Asks AL-or-not when they said a plain 'off'/'unspecified' without the word AL, and
    asks for the day(s) when no date was given. Sick leave with a date needs nothing."""
    qs = []
    if not said_al and leave_type in ("off", "unspecified"):
        qs.append("is this annual leave (AL) or another kind of off")
    if not dates:
        qs.append("which day(s)")
    return qs


def _leave_clarify_msg(said_al: bool, leave_type: str, dates, name: str) -> str:
    """Full bilingual clarify question (one natural sentence per case — never glued
    fragments). Mirrors _leave_questions' two checks. KH approved batch-2 (ChatGPT)."""
    al_q = (not said_al) and leave_type in ("off", "unspecified")
    day_q = not dates
    if al_q and day_q:
        return ("Quick check on your time off, %s — is this annual leave (AL), or another "
                "kind of leave? And which day(s)? Thanks 🤍\n"
                "សុំឆែកបន្តិច %s — នេះជាច្បាប់ឈប់ប្រចាំឆ្នាំ (AL) ឬច្បាប់ប្រភេទផ្សេង? "
                "ហើយឈប់ថ្ងៃណាខ្លះ? អរគុណ 🤍" % (name, name))
    if al_q:
        return ("Quick check, %s — is this annual leave (AL), or another kind of leave? Thanks 🤍\n"
                "សុំឆែកបន្តិច %s — នេះជាច្បាប់ឈប់ប្រចាំឆ្នាំ (AL) ឬច្បាប់ប្រភេទផ្សេង? អរគុណ 🤍"
                % (name, name))
    return ("Quick check, %s — which day(s) is your time off? Thanks 🤍\n"
            "សុំឆែកបន្តិច %s — ប្អូនឈប់ថ្ងៃណាខ្លះ? អរគុណ 🤍" % (name, name))


async def _handle_leave(context, msg, text: str, sender: str) -> None:
    """Supervisors/Management: detect a time-off/leave announcement, record it (to
    accumulate for AL once balances are seeded), and OPEN A CLARIFICATION when info is
    missing — 'off' without the word AL, or no date. The clarification rides the existing
    ladder: GM asks -> nudges -> escalates to the owner. Staged: pre-gate -> Haiku -> logic."""
    chat_id = msg.chat_id
    res = await detect_leave_request(text)
    if res.get("_error") or not res.get("is_leave_request"):
        return
    if res.get("confidence", 0.0) < 0.55:
        return

    person = (res.get("person") or "").strip() or sender
    reporter_uid = msg.from_user.id if msg.from_user else None

    # What's missing? -> the questions the GM should ask.
    questions = _leave_questions(res.get("said_al", False),
                                 res.get("leave_type", "unspecified"), res.get("dates"))
    needs = bool(questions)

    event_id = gm_create_leave_event(
        chat_id, msg.chat.title, msg.message_id, sender, reporter_uid,
        person, res.get("leave_type", "unspecified"), res.get("said_al", False),
        res.get("dates"), res.get("reason"), needs)
    if not event_id:
        return  # already logged this message

    if not needs:
        logger.info("Leave logged (complete): %s, type=%s, dates=%s",
                    person, res.get("leave_type"), res.get("dates"))
        return

    # Ask in-group, tagging the person, and open a clarification so the ladder follows up.
    person_mention = _staff_mention(person)
    body = _leave_clarify_msg(res.get("said_al", False),
                              res.get("leave_type", "unspecified"), res.get("dates"), person_mention)
    try:
        sent = await context.bot.send_message(
            chat_id=chat_id, text=body, reply_to_message_id=msg.message_id,
            parse_mode=ParseMode.HTML,
        )
        clar_id = gm_create_clarification(
            chat_id=chat_id, chat_title=msg.chat.title, topic="leave_clarify",
            question_msg_id=sent.message_id, target_msg_id=msg.message_id,
            question_text=body, sender_name=sender, context_ref=str(event_id),
        )
        if clar_id:
            gm_link_leave_clarification(event_id, clar_id)
        logger.info("Leave clarification opened for %s (event %s)", person, event_id)
    except Exception as e:
        logger.error("leave clarification failed: %s", e)


async def _maybe_flag_sales_anomaly(context, full: dict) -> None:
    """On a FINAL daily report, compare sales to same-day-type history and DM the owner
    if it's below the normal band. Silent until a day-type has enough samples — so it
    activates only once the historical Messenger reports are imported."""
    if full.get("report_kind") != "final":
        return
    sales_val = (full.get("raw") or {}).get("total_sales")
    if sales_val is None:
        return
    try:
        history = gm_get_sales_history()
        result = sales.anomaly_check(full["business_day"], sales_val, history)
        if not result or not result.get("is_low"):
            return
        leave_n = len(gm_get_concerns_since("staffing", 1))  # rough same-day context
        reasons = sales.likely_reasons(full["business_day"], leave_count=0, lateness_count=leave_n)
        body = (
            "📉 Sales below normal — %s (%s)\n"
            "Sales $%.2f vs usual ~$%.2f for this day-type (%d samples); down %.1f%%."
        ) % (full["business_day"], result["day_type"], sales_val,
             result["median"], result["n"], result["drop_pct"])
        if reasons:
            body += "\nPossible context: " + "; ".join(reasons)
        await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body)
        logger.info("Sales anomaly flagged for %s (down %.1f%%)",
                    full["business_day"], result["drop_pct"])
    except Exception as e:
        logger.error("_maybe_flag_sales_anomaly failed: %s", e)


async def _handle_stock_photo(context, msg) -> None:
    """Stock Checks photo: cheap Haiku gate -> if it's a stock-count sheet, Sonnet reads
    the current counts and we store them (last_count + time-series). Event-driven so the
    7am job just reads stored data. ~1 cheap classify per photo; 1 Sonnet read per sheet."""
    try:
        photo_file = await msg.photo[-1].get_file()
        photo_bytes = bytes(await photo_file.download_as_bytearray())
    except Exception as e:
        logger.error("stock photo download failed: %s", e)
        return
    if not (await classify_stock_photo(photo_bytes)).get("is_stock_sheet"):
        return
    items = stock_get_items()
    res = await read_stock_sheet(photo_bytes, [it["item"] for it in items])
    if not res.get("is_stock_sheet") or not res.get("counts"):
        return
    count_date = (finance.business_day_for(msg.date) if msg.date
                  else datetime.now(timezone.utc).date()).isoformat()
    applied = stock_apply_sheet_reading(res["counts"], count_date, msg.message_id)
    logger.info("Stock sheet read: %d/%d counts applied (day %s)",
                applied, len(res["counts"]), count_date)


async def _stock_order_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """7am Phnom Penh: post 'Check if we need to order' for items below minimum.
    No sheet for 2+ days -> ask the group why. Owner-gated by gm_state
    'stock_order_to_staff' (preview to owner until 'true')."""
    days = stock_days_since_last_count()
    if days is None:
        logger.info("Stock order job: no stock counts yet")
        return
    if stock.no_sheet_decision(days) == "escalate":
        try:
            await context.bot.send_message(
                chat_id=config.STOCK_CHECKS_CHAT_ID,
                text=("No stock sheet has been posted for %d days. Please do the stock "
                      "check and send the sheet. Thank you.\n"
                      "មិនមាន stock sheet ត្រូវបានផ្ញើអស់ %d ថ្ងៃហើយ។ សូមធ្វើ stock check "
                      "ហើយផ្ញើ sheet។ អরគុណ។" % (days, days)))
            logger.info("Stock: escalated missing sheet (%d days)", days)
        except Exception as e:
            logger.error("stock no-sheet escalation failed: %s", e)

    items = stock_get_items()
    rows_input = [{
        "item": it["item"], "unit": it["unit"],
        "min_n": float(it["min_n"]) if it["min_n"] is not None else None,
        "current_n": float(it["last_count"]) if it["last_count"] is not None else None,
        "usage_per_day": float(it["usage_per_day"]) if it["usage_per_day"] is not None else None,
    } for it in items]
    # Guard: a 0/NULL minimum can never trigger a reorder — surface, never silently skip.
    no_min = [it["item"] for it in items if it["min_n"] is None or float(it["min_n"]) == 0]

    body = stock.format_order_message(stock.build_order_list(rows_input))
    if body is None and not no_min:
        logger.info("Stock order job: nothing below minimum")
        return

    to_staff = gm_get_state("stock_order_to_staff") == "true"
    try:
        if to_staff:
            if body:
                await context.bot.send_message(chat_id=config.STOCK_CHECKS_CHAT_ID, text=body)
        else:
            preview = "📋 Stock order (preview — NOT sent to staff)\n\n" + (body or "(nothing below minimum)")
            if no_min:
                preview += "\n\n⚠️ No minimum set (won't be checked): " + ", ".join(no_min)
            await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=preview)
        logger.info("Stock order job posted (to_staff=%s)", to_staff)
    except Exception as e:
        logger.error("stock order job send failed: %s", e)


# ─── Staff registry / ex-staff offboarding ────────────────────────────────────

def _internal_groups() -> list[tuple[str, int]]:
    """(label, chat_id) for the internal groups ex-staff must be removed from."""
    return [
        ("Stock Checks", config.STOCK_CHECKS_CHAT_ID),
        ("Supervisors",  config.SUPERVISORS_CHAT_ID),
        ("Management",   config.MANAGEMENT_CHAT_ID),
        ("COMMS",        config.COMMS_CHAT_ID),
        ("TWB REPORT",   config.DAILY_REPORT_CHAT_ID),
    ]

_DEPARTURE_PHRASES = [
    "no longer work", "left the company", "left us", "no longer with us", "quit",
    "resigned", "fired", "doesn't work here", "does not work here", "is gone",
    "not working here", "no longer here", "left our company", "has left",
]


async def _staff_current_groups(context, uids: list[int]) -> list[tuple[str, int]]:
    """Which internal groups any of these user_ids is currently a member of."""
    present = []
    for label, chat_id in _internal_groups():
        for uid in uids:
            try:
                m = await context.bot.get_chat_member(chat_id, uid)
                if m.status not in ("left", "kicked"):
                    present.append((label, chat_id)); break
            except Exception:
                continue
    return present


def _exstaff_kb(staff_id: int) -> InlineKeyboardMarkup:
    # one button per row — long labels get truncated side by side (owner, session 28)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Mark as left + remove", callback_data="exstaff:go:%d" % staff_id)],
        [InlineKeyboardButton("✋ No, keep", callback_data="exstaff:no:%d" % staff_id)],
    ])


async def _offer_exstaff(context, staff: dict, why: str = "") -> None:
    """DM the owner a confirm card for marking someone ex-staff."""
    groups = await _staff_current_groups(context, staff.get("telegram_ids", []))
    glist = ", ".join(label for label, _ in groups) or "no internal groups found"
    name = staff["canonical_name"] + (" (%s)" % staff["call_name"] if staff.get("call_name") else "")
    body = "%sMark %s as no longer working here?\nCurrently in: %s" % (
        (why + "\n") if why else "", name, glist)
    await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=body,
                                   reply_markup=_exstaff_kb(staff["id"]))


async def _do_exstaff(context, staff: dict) -> None:
    """Mark ex-staff + remove from internal groups (where the bot can) + report."""
    staff_mark_ex(staff["id"], "owner marked departed")
    removed, failed = [], []
    for label, chat_id in _internal_groups():
        gone = False
        for uid in staff.get("telegram_ids", []):
            try:
                m = await context.bot.get_chat_member(chat_id, uid)
                if m.status in ("left", "kicked"):
                    gone = True; continue
                await context.bot.ban_chat_member(chat_id, uid)
                removed.append(label); gone = True; break
            except Exception:
                failed.append(label); gone = True; break
        # if not seen in group at all, nothing to do
    name = staff["canonical_name"]
    lines = ["✓ Marked %s as ex-staff. Historical data kept; no bot will engage them." % name]
    if removed:
        lines.append("Removed from: " + ", ".join(sorted(set(removed))))
    leftover = [g for g in failed if g not in removed]
    if leftover:
        lines.append("⚠️ Could NOT remove (please remove manually): " + ", ".join(sorted(set(leftover))))
    await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text="\n".join(lines))
    logger.info("Ex-staff %s: removed=%s failed=%s", name, removed, leftover)


async def cmd_rollcall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/rollcall — owner: who has pressed Start with the GM (first contact is stamped
    even though the GM stays silent after the one greeting)."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    with __import__("shared.database", fromlist=["_db"])._db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT key, updated_at FROM gm_state
                           WHERE key LIKE 'rollcall_greeted:%' ORDER BY updated_at DESC""")
            rows = cur.fetchall()
    greeted = {}
    for r in rows:
        try:
            greeted[int(r["key"].split(":")[1])] = r["updated_at"]
        except (ValueError, IndexError):
            pass
    active = staff_all("active")
    started, missing = [], []
    for p in active:
        ts = next((greeted[u] for u in (p.get("telegram_ids") or []) if u in greeted), None)
        name = p.get("call_name") or p["canonical_name"]
        if ts is not None:
            started.append((ts, name))
        else:
            missing.append(name + (" (Delis)" if p.get("org") == "DELIS" else ""))
    started.sort(reverse=True)
    lines = ["📋 Roll-call: %d / %d started" % (len(started), len(active))]
    recent = started[:5]
    if recent:
        lines.append("Most recent: " + ", ".join(
            "%s (%s)" % (n, str(t)[5:16]) for t, n in recent))
    lines.append("Missing: " + (", ".join(sorted(missing)) or "— everyone in! ✅"))
    await update.message.reply_text("\n".join(lines))


async def cmd_payroll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/payroll [YYYY-MM] — owner: payslip preview for a WORK-month (defaults to last month).
    Read-only table (salary, pay1/pay2, bonus earned/not-earned, no-show cuts). Edit/send = later."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    from gm_bot import payroll as pr
    from shared.database import no_show_count_month
    args = (context.args or [])
    if args and "-" in args[0]:
        y, m = (int(x) for x in args[0].split("-")[:2])
    else:
        now = datetime.now(finance.PP_TZ)
        m = now.month - 1 or 12
        y = now.year if now.month > 1 else now.year - 1
    lines = ["📋 Payroll preview — work month %04d-%02d (paid the following month #1 + #2)" % (y, m)]
    for s in sorted(staff_all("active"), key=lambda r: r["canonical_name"]):
        if s.get("org") != "TWB" or s["canonical_name"] == "Tyty" or s.get("salary_usd") is None:
            continue
        ns = no_show_count_month(s["id"], y, m)
        slip = pr.compute_slip(float(s.get("salary_usd") or 0), float(s.get("bonus_usd") or 0),
                               float(s.get("first_pay_usd") or 0), float(s.get("second_pay_usd") or 0),
                               ns)
        lines.append(pr.slip_line(s.get("call_name") or s["canonical_name"], slip))
    lines.append("\n(preview — editing + send-to-staff slips is the next build)")
    # chunk to stay under Telegram's message limit
    text = "\n".join(lines)
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i + 3500])


def _parse_testclock(arg: str, base: datetime):
    """Parse a /testclock argument into an absolute 'pretend now' datetime (PP tz), or None to clear.
      off|clear|real          → None (use the wall clock)
      +3d / -2d / +90m / +5h  → base shifted by that delta
      tomorrow [HH:MM]        → next day (default 08:00) ; today [HH:MM]
      2026-06-15 [HH:MM]      → that date (default 08:00)
    Returns (dt_or_None, ok)."""
    import re as _re
    a = (arg or "").strip().lower()
    if a in ("off", "clear", "real", "none"):
        return None, True
    m = _re.fullmatch(r"([+-]\d+)\s*([dhm])", a)
    if m:
        n = int(m.group(1)); unit = m.group(2)
        delta = timedelta(days=n) if unit == "d" else (timedelta(hours=n) if unit == "h"
                                                       else timedelta(minutes=n))
        return base + delta, True
    m = _re.fullmatch(r"(today|tomorrow)(?:\s+(\d{1,2}):(\d{2}))?", a)
    if m:
        d = base.date() + timedelta(days=1 if m.group(1) == "tomorrow" else 0)
        hh, mm = (int(m.group(2)), int(m.group(3))) if m.group(2) else (8, 0)
        return datetime(d.year, d.month, d.day, hh, mm, tzinfo=finance.PP_TZ), True
    m = _re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2}))?", a)
    if m:
        y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mm = (int(m.group(4)), int(m.group(5))) if m.group(4) else (8, 0)
        return datetime(y, mo, dd, hh, mm, tzinfo=finance.PP_TZ), True
    return None, False


async def cmd_testclock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testclock — owner: set a frozen 'pretend now' for the test harness so time-driven behaviour
    can be rehearsed without waiting. Only effective in test mode; never touches the live clock.
      /testclock                  → show current
      /testclock +3d | tomorrow 08:00 | 2026-06-15 06:00
      /testclock off              → back to the real wall clock"""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    raw = " ".join(context.args or []).strip()
    if not raw:
        cur = gm_get_state("att_test_now")
        mode = "🧪 ON" if _att_test_mode() else "off (set it only matters in test mode)"
        await update.message.reply_text(
            "Test clock: %s\nTest mode: %s\nEffective now: %s\n\n"
            "Set: /testclock +3d  ·  /testclock tomorrow 08:00  ·  /testclock 2026-06-15 06:00\n"
            "Clear: /testclock off"
            % (cur or "(real wall clock)", mode, _now_pp().strftime("%a %Y-%m-%d %H:%M %Z")))
        return
    dt, ok = _parse_testclock(raw, datetime.now(finance.PP_TZ))
    if not ok:
        await update.message.reply_text("Couldn't parse '%s'. Try: +3d · tomorrow 08:00 · "
                                        "2026-06-15 06:00 · off" % raw)
        return
    if dt is None:
        gm_set_state("att_test_now", "")
        await update.message.reply_text("⏰ Test clock cleared — back to the real wall clock.")
        return
    gm_set_state("att_test_now", dt.isoformat())
    warn = "" if _att_test_mode() else "\n⚠ Test mode is OFF — this only takes effect once you /testmode on."
    await update.message.reply_text("⏰ Test clock set → %s%s" % (dt.strftime("%a %Y-%m-%d %H:%M %Z"), warn))


def _testrun_jobs():
    """Name → job body, for /testrun. Excludes _callout_job (spends Opus) and real-data jobs."""
    return {"checkin": _checkin_scheduler_job, "noshow": _no_show_sweep_job,
            "ladder": _payback_ladder_job, "booking": _booking_reminder_job,
            "sickdeadline": _sick_papers_deadline_job}


async def cmd_testrun(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testrun <job> — owner/test: fire a scheduled job's body ONCE right now, against the test
    clock, bypassing the live-only gate — so you can WATCH time-driven behaviour instead of waiting.
    Writes are is_test, messages route to you. Pair with /testclock (set the pretend day first).
      /testrun                → list jobs + the current test clock
      /testrun checkin        → the T−10/T0/T+5/checkout scheduler tick (auto-checkout too)
      /testrun ladder         → payback ignore-ladder (day-3 warn / day-4 auto-book)
      /testrun noshow         → yesterday's no-show sweep
      /testrun booking        → 12h-before booked-slot reminders
      /testrun sickdeadline   → paperless-sick papers deadline pass"""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    if not _att_test_mode():
        await update.message.reply_text("Turn on test mode first: /testmode on")
        return
    jobs = _testrun_jobs()
    name = (context.args or [""])[0].lower()
    if name not in jobs:
        await update.message.reply_text(
            "Fire a job now — test clock is %s.\nJobs: %s\nUsage: /testrun checkin"
            % (_now_pp().strftime("%a %Y-%m-%d %H:%M"), " · ".join(jobs)))
        return
    global _TEST_FORCE_RUN
    _TEST_FORCE_RUN = True
    try:
        await jobs[name](context)
    except Exception as e:
        logger.error("testrun %s failed: %s", name, e)
        await update.message.reply_text("⚠ '%s' errored: %s" % (name, e))
        return
    finally:
        _TEST_FORCE_RUN = False
    await update.message.reply_text(
        "✅ Fired '%s' at test-now %s — anything it produced was routed to you above."
        % (name, _now_pp().strftime("%a %H:%M")))


async def cmd_testmode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testmode on|off — owner: enter/leave the role-play test harness. In test mode every
    attendance message routes to YOU (labeled by recipient) with working buttons, every write is
    is_test-tagged, and real balances are never touched. attendance_live stays untouched."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    if update.message is None:      # edited /testmode message → no .message; ignore (prod Jun 9)
        return
    arg = (context.args or [""])[0].lower()
    if arg not in ("on", "off"):
        cur = "ON" if _att_test_mode() else "off"
        await update.message.reply_text("Test mode is currently %s.\nUse /testmode on  or  /testmode off"
                                        % cur)
        return
    on = arg == "on"
    gm_set_state("attendance_test_mode", "true" if on else "false")
    set_att_test(on)
    if on:
        await update.message.reply_text(
            "🧪 TEST MODE ON.\n"
            "• Open /test and act as anyone — buttons are REAL.\n"
            "• Every message (to staff, each senior, each group) comes HERE, labeled [→ who].\n"
            "• Everything you do is tagged test data — real balances are NOT touched.\n"
            "• /teststatus to see test rows · /testreset to wipe them · /testmode off when done.")
    else:
        await update.message.reply_text("✓ TEST MODE OFF. Messages now route to real recipients "
                                        "(only matters once attendance_live is on).")


async def cmd_testkhmer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testkhmer on|off — owner: in TEST mode, show the full Khmer+English bodies instead of the
    default English-only, so the real Khmer can be proof-read. No effect live (staff always get
    bilingual; the owner always gets English-only live)."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    arg = (context.args or [""])[0].lower()
    if arg not in ("on", "off"):
        cur = "ON — bilingual" if gm_get_state("att_test_khmer") == "true" else "off — English only"
        await update.message.reply_text(
            "Test Khmer view is currently %s.\nUse /testkhmer on  or  /testkhmer off\n"
            "(only changes what YOU see in /test — turn on to proof-read the Khmer.)" % cur)
        return
    gm_set_state("att_test_khmer", "true" if arg == "on" else "false")
    if arg == "on":
        await update.message.reply_text(
            "🇰🇭 Test Khmer view ON — /test messages now show the full Khmer + English, exactly as "
            "staff will see them. /testkhmer off to go back to English-only.\n"
            "(Tip: turn it on now, walk every flow once to read the Khmer, then off to test faster.)")
    else:
        await update.message.reply_text("✓ Test Khmer view OFF — back to English-only in /test.")


async def cmd_testreset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testreset — delete EXACTLY the test-tagged attendance rows (real data can't be caught)."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    deleted = attendance_testreset()
    total = sum(deleted.values())
    detail = ", ".join("%s:%d" % (k, v) for k, v in deleted.items() if v) or "nothing to clear"
    await update.message.reply_text("🧹 Test data wiped — %d rows.\n%s" % (total, detail))


async def cmd_teststatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/teststatus — current mode + outstanding test rows per table."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    counts = attendance_test_counts()
    mode = "🧪 ON" if _att_test_mode() else "off"
    body = "\n".join("• %s: %d" % (k, v) for k, v in counts.items()) or "• (no test rows)"
    await update.message.reply_text("Test mode: %s\nLive switch: %s\n\nTest rows:\n%s"
                                    % (mode, "ON" if _attendance_live() else "off", body))


async def cmd_pb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pb — owner: ONLY the staff who currently owe pay-back, each with how much is already
    'booked' (covered by an approved upcoming OT that will clear it at checkout). Mode-aware: shows
    test debts in test mode, real debts otherwise."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    from shared.database import payback_all_open, ot_pending_extension_min
    from gm_bot.attendance_ui import _hm
    today_iso = _today_pp().isoformat()
    lines = []
    for d in payback_all_open():
        bal = d.get("balance") or 0
        if bal <= 0:
            continue
        staff = next((s for s in staff_all("active") if s["id"] == d["staff_id"]), None)
        if not staff:
            continue
        nm = staff.get("call_name") or staff["canonical_name"]
        booked = min(ot_pending_extension_min(d["staff_id"], today_iso), bal)
        lines.append("• %s: %s%s" % (nm, _hm(bal), (" (%s booked)" % _hm(booked)) if booked else ""))
    if not lines:
        await update.message.reply_text("📒 No open pay-back debts. ✓")
        return
    head = "📒 Pay-back debts — %d staff%s:" % (len(lines), " · 🧪 test" if _att_test_mode() else "")
    await update.message.reply_text(head + "\n" + "\n".join(lines))


def _caps_call(s: dict) -> str:
    """The CAPSED call name (owner's staff-list convention); canonical when no call name."""
    cn = (s.get("call_name") or "").strip()
    return cn.upper() if cn else s["canonical_name"]


def _own_staff_sorted(org: str | None = "TWB", include_tyty: bool = False) -> list[dict]:
    """Active staff, alphabetical by call name — the owner-menu roster.
    org: 'TWB' (default — attendance views), 'DELIS', or None for everyone.
    Tyty is excluded from attendance views but INCLUDED in the pay views (owner: she's
    on the 1st pay at $1700, no bonus)."""
    rows = [s for s in staff_all("active")
            if (include_tyty or s["canonical_name"] != "Tyty")
            and (org is None or (s.get("org") or "").upper() == org.upper())]
    return sorted(rows, key=lambda r: (r.get("call_name") or r["canonical_name"]).lower())


def _own_pbot_text(today_iso: str) -> str:
    """PB + OT — only staff with something on the time ledger. Same no-double-count partition as
    My Schedule: booked = min(extension, debt) next to PB; only the leftover is upcoming OT."""
    from shared.database import payback_open_debt, ot_bank_balance, ot_pending_extension_min
    from gm_bot.attendance_ui import _hm
    from gm_bot import ot as ot_mod
    lines = []
    for s in _own_staff_sorted():
        debt = payback_open_debt(s["id"])
        pb = debt["balance"] if debt else 0
        bank = ot_bank_balance(s["id"])
        ext = ot_pending_extension_min(s["id"], today_iso)
        booked = min(ext, pb)
        upcoming = min(max(0, ext - pb), ot_mod.cap_room(bank))
        if not (pb or bank or upcoming):
            continue
        seg = []
        if pb:
            seg.append("PB %s%s" % (_hm(pb), (" (%s booked)" % _hm(booked)) if booked else ""))
        if bank or upcoming:
            seg.append("OT %s%s" % (_hm(bank), (" (+%s upcoming)" % _hm(upcoming)) if upcoming else ""))
        lines.append("• %s — %s" % (_caps_call(s), " · ".join(seg)))
    head = "⏱ PB + OT%s\n" % (" · 🧪 test" if _att_test_mode() else "")
    return head + ("\n".join(lines) if lines else "(nobody owes or banks time ✓)")


def _own_al_text() -> str:
    """AL + Joined — every staffer: CAPSED name, AL balance, hire date when known (/joined sets it)."""
    lines = []
    for s in _own_staff_sorted():
        line = "• %s — %g AL" % (_caps_call(s), float(s.get("al_left") or 0))
        j = s.get("joined_date")
        if j:
            line += " · %s" % (j.strftime("%m/%Y") if s.get("joined_month_only") else j.strftime("%d/%m/%Y"))
        lines.append(line)
    return "🏖 AL + Joined\n" + "\n".join(lines) + \
        "\n\n(no date = not on record — set with /joined <name> <date>)"


def _own_sal_text(which: int) -> str:
    """Salaries 1st/2nd pay — TWB and Delis sections, each with its own total, grand total last.
    2nd pay shows the bonus SEPARATELY ('ANAN — $30.00 +$20.00', owner): the stored second pay
    carries the bonus baked in, so base = second_pay − bonus, and the + is the earnable part."""
    out = ["💵 Salaries — %s pay" % ("1st" if which == 1 else "2nd")]
    grand = 0.0
    for org, label in (("TWB", "TWB"), ("DELIS", "Delis")):
        lines, total = [], 0.0
        for s in _own_staff_sorted(org, include_tyty=True):
            if s.get("salary_usd") is None:
                continue
            if which == 1:
                v = float(s.get("first_pay_usd") or 0)
                if not v:
                    continue          # nothing on the 1st → not listed there
                total += v
                lines.append("• %s — $%.2f" % (_caps_call(s), v))
            else:
                pay2 = float(s.get("second_pay_usd") or 0)
                bonus = float(s.get("bonus_usd") or 0)
                if not pay2 and not bonus:
                    continue          # 1st-pay-only staff (e.g. Tyty) don't clutter the 2nd list
                total += pay2
                lines.append("• %s — $%.2f%s"
                             % (_caps_call(s), pay2 - bonus, (" +$%.2f" % bonus) if bonus else ""))
        out.append("\n%s:" % label)
        if lines:
            out += lines
            grand += total
            out.append("%s total: $%.2f" % (label, total))
        else:
            out.append("(no pay data on record yet)")
    out.append("\nTotal: $%.2f" % grand)
    if which == 2:
        out.append("(base +bonus — the + pays only when earned)")
    return "\n".join(out)


_OWN_STAFF_KB_ROWS = [
    [("⏱ PB + OT", "own:pbot")],
    [("🏖 AL + Joined", "own:al")],
    [("💵 Salaries 1st", "own:sal1")],
    [("💵 Salaries 2nd", "own:sal2")],
    [("⬅ Back", "own:menu")],
]


def _own_kb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=c) for t, c in r]
                                 for r in rows])


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/menu — OWNER ONLY (salaries live in here, so not even Tyty)."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    await update.message.reply_text("🗂 Owner menu",
        reply_markup=_own_kb([[("👥 Staff info", "own:staff")]]))


async def _owner_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """own:* — the owner's private menu. Hard-gated to the owner uid."""
    query = update.callback_query
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        await query.answer()
        return
    await query.answer()
    a = query.data.split(":")[1]
    back = _own_kb([[("⬅ Back", "own:staff")]])
    if a == "menu":
        await query.edit_message_text("🗂 Owner menu",
                                      reply_markup=_own_kb([[("👥 Staff info", "own:staff")]]))
    elif a == "staff":
        await query.edit_message_text("👥 Staff info", reply_markup=_own_kb(_OWN_STAFF_KB_ROWS))
    elif a == "pbot":
        await query.edit_message_text(_own_pbot_text(_today_pp().isoformat()), reply_markup=back)
    elif a == "al":
        await query.edit_message_text(_own_al_text(), reply_markup=back)
    elif a in ("sal1", "sal2"):
        await query.edit_message_text(_own_sal_text(1 if a == "sal1" else 2), reply_markup=back)


def _parse_joined(raw: str):
    """Hire-date input → (iso, month_only) or None. Full: DD/MM/YYYY · YYYY-MM-DD.
    Month-only (day unknown): MM/YYYY · YYYY-MM — stored as the 1st, shown as mm/yyyy."""
    raw = (raw or "").strip()
    try:
        if "/" in raw:
            parts = [int(x) for x in raw.split("/")]
            if len(parts) == 3:
                d, m, y = parts
                return datetime(y, m, d).strftime("%Y-%m-%d"), False
            if len(parts) == 2:
                m, y = parts
                return datetime(y, m, 1).strftime("%Y-%m-%d"), True
        else:
            parts = [int(x) for x in raw.split("-")]
            if len(parts) == 3:
                y, m, d = parts
                return datetime(y, m, d).strftime("%Y-%m-%d"), False
            if len(parts) == 2:
                y, m = parts
                return datetime(y, m, 1).strftime("%Y-%m-%d"), True
    except Exception:
        pass
    return None


async def cmd_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/joined <name> <date> — owner: set a staffer's hire date.
    Full date: DD/MM/YYYY or YYYY-MM-DD · only month known: MM/YYYY or YYYY-MM."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    from shared.database import staff_set_joined
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /joined <name> <date>\nFull: 03/05/2023 or 2023-05-03 · month only: 05/2023 or 2023-05")
        return
    parsed = _parse_joined(args[-1])
    if not parsed:
        await update.message.reply_text(
            "Couldn't read the date — use DD/MM/YYYY (or MM/YYYY when you only know the month).")
        return
    iso, month_only = parsed
    name = " ".join(args[:-1]).lower()
    hits = [s for s in staff_all("active")
            if name in (s.get("call_name") or "").lower() or name in s["canonical_name"].lower()]
    if len(hits) != 1:
        await update.message.reply_text(
            "Matched %d staff for '%s' — be more specific." % (len(hits), name))
        return
    staff_set_joined(hits[0]["id"], iso, month_only)
    shown = iso[:7] if month_only else iso
    await update.message.reply_text("✓ %s joined %s saved.%s"
        % (_caps_call(hits[0]), shown, " (month only — day unknown)" if month_only else ""))
    # NEW HIRE this month → the join date is load-bearing: auto-prorate their first month's
    # split (owner rule in payroll.prorate_join_month) and register the automatic restore.
    note = _maybe_prorate_new_hire(hits[0], iso, month_only)
    if note:
        await update.message.reply_text(note)


def _maybe_prorate_new_hire(staff: dict, joined_iso: str, month_only: bool) -> str | None:
    """If the joined date is a full date in the CURRENT PP month (day > 1) and the staffer has a
    salary on record: apply the prorated join-month split and save a pay_restore record so the
    daily job restores their FULL split automatically once the join month passes.
    Returns the owner-facing note, or None when no proration applies (e.g. backfilling history)."""
    import json as _json
    from gm_bot import payroll as pr
    from shared.database import gm_get_state, gm_set_state, staff_set_pay_split
    if month_only or staff.get("salary_usd") is None:
        return None
    now = datetime.now(finance.PP_TZ)
    if joined_iso[:7] != now.strftime("%Y-%m") or int(joined_iso[8:10]) <= 1:
        return None
    sid = staff["id"]
    if gm_get_state("pay_restore:%d" % sid):
        return None                          # already prorated once — never stack
    salary = float(staff.get("salary_usd") or 0)
    bonus = float(staff.get("bonus_usd") or 0)
    orig_first = float(staff.get("first_pay_usd") or 0)
    orig_second = float(staff.get("second_pay_usd") or 0)
    p = pr.prorate_join_month(salary, int(joined_iso[8:10]))
    new_second = round(p["second_base"] + bonus, 2)
    staff_set_pay_split(sid, p["first"], new_second)
    gm_set_state("pay_restore:%d" % sid, _json.dumps(
        {"first": orig_first, "second": orig_second, "after": joined_iso[:7]}))
    return ("🧮 New hire this month → first month prorated automatically:\n"
            "salary $%g × %d/30 days = $%g · 1st pay $%g (80%% rounded up to 5/0) · "
            "2nd $%g base%s.\nFull split ($%g / $%g) restores automatically on the 1st of "
            "next month." % (salary, 30 - (int(joined_iso[8:10]) - 1), p["prorated"], p["first"],
                             p["second_base"], (" +$%g bonus" % bonus) if bonus else "",
                             orig_first, orig_second))


async def _pay_restore_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily: once a new hire's join month has PASSED, restore their full stored split (the
    join-month proration was temporary) and tell the owner. Real wall clock — never the test
    clock (real pay data, like the AL accrual jobs)."""
    import json as _json
    from shared.database import gm_state_prefix, gm_set_state, staff_set_pay_split
    cur_month = datetime.now(finance.PP_TZ).strftime("%Y-%m")
    for key, val in gm_state_prefix("pay_restore:"):
        try:
            rec = _json.loads(val)
        except Exception:
            continue
        if rec.get("after", "9999-12") >= cur_month:
            continue                          # join month not over yet
        sid = int(key.split(":")[1])
        staff_set_pay_split(sid, rec["first"], rec["second"])
        gm_set_state(key, "")
        staff = next((s for s in staff_all("active") if s["id"] == sid), None)
        nm = _caps_call(staff) if staff else ("staff id %d" % sid)
        try:
            await context.bot.send_message(config.OWNER_TELEGRAM_ID,
                "✓ %s's join-month proration ended — full pay split restored "
                "(1st $%g · 2nd $%g)." % (nm, rec["first"], rec["second"]))
        except Exception as e:
            logger.error("pay restore notify failed: %s", e)


async def _auto_audit_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Daily 07:30 PP: the invariant audit over the REAL ledger — SILENT when clean, owner DM only
    when something is up (so data-law violations chase the owner instead of waiting to be asked).
    Always real rows (test_rows=False), even if test mode was left on. Real wall clock."""
    from gm_bot.audit import run_audit
    try:
        problems, _stats = run_audit(datetime.now(finance.PP_TZ).date(), test_rows=False)
    except Exception as e:
        logger.error("auto-audit failed to run: %s", e)
        try:
            await context.bot.send_message(config.OWNER_TELEGRAM_ID,
                                           "⚠ Daily auto-audit FAILED to run: %s" % e)
        except Exception:
            pass
        return
    if not problems:
        logger.info("auto-audit: clean")
        return
    body = ("❌ DAILY AUTO-AUDIT — %d problem(s) in the REAL data. Copy this message to Claude:\n\n"
            % len(problems)) + "\n".join("• " + p for p in problems)
    for i in range(0, len(body), 3500):
        try:
            await context.bot.send_message(config.OWNER_TELEGRAM_ID, body[i:i + 3500])
        except Exception as e:
            logger.error("auto-audit DM failed: %s", e)
            break


async def cmd_audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/audit — owner: cross-check that every button input translated to the right stored result.
    Runs all data invariants (AL deductions, payback math, OT banking/cap, sessions, no-shows,
    bookings, swaps, staff sanity) over the CURRENT mode's rows — test rows during the role-play,
    real rows once live. Problems are self-contained lines the owner can paste to Claude."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    from gm_bot.audit import run_audit
    try:
        problems, stats = run_audit(_today_pp())
    except Exception as e:
        await update.message.reply_text("⚠ Audit itself failed: %s" % e)
        return
    mode = "🧪 TEST rows" if _att_test_mode() else "real rows"
    counts = " · ".join("%s %d" % (k, v) for k, v in stats.items())
    if not problems:
        await update.message.reply_text(
            "✅ AUDIT CLEAN (%s)\nEvery input → result invariant holds.\nChecked: %s"
            % (mode, counts))
        return
    head = "❌ AUDIT — %d problem(s) (%s). Copy this message to Claude:\n\n" % (len(problems), mode)
    body = head + "\n".join("• " + p for p in problems) + "\n\nChecked: " + counts
    for i in range(0, len(body), 3500):
        await update.message.reply_text(body[i:i + 3500])


async def cmd_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/commands — owner: the full list of GM commands, grouped, with one-line descriptions."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    await update.message.reply_text(
        "🤖 GM bot — your commands\n"
        "\n— Attendance · test harness (safe, gated OFF) —\n"
        "/test — open the role-play harness; walk any flow as any staff\n"
        "/testmode on|off — enter/leave test mode (all routes to you, nothing real is touched)\n"
        "/testclock — set a pretend 'now' (+3d · tomorrow 08:00 · 2026-06-15 06:00 · off)\n"
        "/testkhmer on|off — show the full Khmer+English in /test (to proof-read), or English-only\n"
        "/testrun <job> — fire a scheduled job now: checkin · ladder · noshow · booking · sickdeadline\n"
        "/teststatus — current test mode + how many test rows exist\n"
        "/testseed [name] — copy real ALs/paybacks into test so flows have realistic data\n"
        "/testreset — wipe all test data\n"
        "\n— Attendance · live overviews —\n"
        "/menu — your private menu: Staff info → PB+OT · AL+Joined · Salaries 1st/2nd\n"
        "/joined <name> <date> — set a hire date (03/05/2023, or 05/2023 if you only know the month)\n"
        "/pb — staff who owe pay-back, with how much is already booked by upcoming OT\n"
        "/audit — cross-check ALL data: did every button input produce the right result? "
        "✅ clean, or a paste-to-Claude problem list\n"
        "/holiday — manage paid public holidays (cost no AL; AL spans bridge them)\n"
        "/payroll [YYYY-MM] — payslip preview for a work-month (defaults to last month)\n"
        "/rollcall — who has pressed Start with the GM bot\n"
        "\n— GM intelligence (staff comms) —\n"
        "/check — run analysis now → new concerns to review (tap a name)\n"
        "/pending — send the analysed concerns\n"
        "/review — concerns sent but not yet reviewed\n"
        "/proposals — the GM's pending improvement proposals\n"
        "/approved — approved proposals (the GM's current playbook)\n"
        "/points — points summary, last 30 days\n"
        "\n— Staff & admin —\n"
        "/staff — staff registry (look up / list)\n"
        "/exstaff <name> — mark a staff member as departed\n"
        "/vendor — per-vendor receipt knowledge\n"
        "/rules — the staff rules screen\n"
        "/commands — this list")


async def cmd_holiday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/holiday — manage company-wide PAID free days (public holidays). These cost NO AL and NO
    points, and AL spans bridge across them automatically.
    /holiday                       → list
    /holiday add YYYY-MM-DD …      → add date(s)
    /holiday del YYYY-MM-DD …      → remove date(s)"""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    from shared.database import public_holidays, set_public_holidays
    from datetime import date as _d
    args = context.args or []
    cur = set(public_holidays())
    if not args:
        lst = "\n".join("• " + x for x in sorted(cur)) or "• (none set)"
        await update.message.reply_text(
            "📅 Public holidays / paid free days (no AL, no points; AL bridges across them):\n%s\n\n"
            "/holiday add YYYY-MM-DD  ·  /holiday del YYYY-MM-DD" % lst)
        return
    action = args[0].lower()
    dates = [a for a in args[1:] if _valid_iso(a)]
    if action == "add" and dates:
        set_public_holidays(cur | set(dates))
    elif action in ("del", "remove", "rm") and dates:
        set_public_holidays(cur - set(dates))
    else:
        await update.message.reply_text(
            "Use: /holiday  ·  /holiday add YYYY-MM-DD  ·  /holiday del YYYY-MM-DD")
        return
    now = sorted(public_holidays())
    await update.message.reply_text("✓ Updated. Public holidays now: %s" % (", ".join(now) or "(none)"))


def _valid_iso(s: str) -> bool:
    from datetime import date as _d
    try:
        _d.fromisoformat(s)
        return True
    except Exception:
        return False


async def cmd_testseed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testseed [name] — copy real approved ALs + open paybacks into is_test copies so TEST mode
    shows realistic data. Idempotent (clears prior test copies first). Then /testmode on to see it,
    /testreset to wipe. No name = everyone; a name = just that staffer."""
    if update.effective_user.id not in {config.OWNER_TELEGRAM_ID, _tyty_uid()}:
        return
    arg = " ".join(context.args or []).strip()
    sid, who = None, "everyone"
    if arg:
        act = [m for m in staff_find_by_name(arg) if m.get("status") == "active"]
        if len(act) == 1:
            sid, who = act[0]["id"], act[0].get("call_name") or act[0]["canonical_name"]
        else:
            await update.message.reply_text(
                "Couldn't match exactly one active staffer to '%s' (%d matches). "
                "Use /testseed with no name to seed everyone." % (arg, len(act)))
            return
    res = attendance_testseed(sid)
    total = sum(res.values())
    detail = ", ".join("%s:%d" % (k, v) for k, v in res.items() if v) or "nothing to copy"
    await update.message.reply_text(
        "🌱 Seeded test data from live for %s — %d rows (%s).\n"
        "Turn /testmode on to see it · /testreset to wipe." % (who, total, detail))


async def cmd_vendor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/vendor — owner manages per-vendor receipt knowledge.
    /vendor                      -> list
    /vendor atlas skip           -> never flag this vendor's receipts
    /vendor atlas <rule text...> -> inject rule into the clarity prompt"""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    args = context.args or []
    if not args:
        rules = gm_get_vendor_rules()
        if not rules:
            await update.message.reply_text(
                "No vendor rules yet.\n/vendor <name> <how their receipts look>\n"
                "/vendor <name> skip — never flag them")
            return
        await update.message.reply_text("Receipt vendor knowledge:\n" + "\n".join(
            "• %s — %s" % (v["vendor"], "SKIP (never flagged)" if v["mode"] == "skip" else v["rule"])
            for v in rules))
        return
    vendor = args[0].lower()
    rest = " ".join(args[1:]).strip()
    if rest.lower() == "skip":
        gm_set_vendor_rule(vendor, "skip", None)
        await update.message.reply_text("Saved ✓ %s receipts will never be flagged." % vendor)
    elif rest:
        gm_set_vendor_rule(vendor, "rule", rest)
        await update.message.reply_text("Saved ✓ %s: %s" % (vendor, rest))
    else:
        await update.message.reply_text("Usage: /vendor %s <rule text or 'skip'>" % vendor)


async def cmd_exstaff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/exstaff <name> — owner marks a staff member as departed."""
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    name = " ".join(context.args).strip() if context.args else ""
    if not name:
        await update.message.reply_text("Usage: /exstaff <name>")
        return
    await _resolve_and_offer_exstaff(context, name)


async def _resolve_and_offer_exstaff(context, name: str) -> None:
    matches = staff_find_by_name(name)
    matches = [m for m in matches if m.get("status") == "active"]
    if not matches:
        await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID,
            text="No active staff matched '%s'. Try their exact name or /exstaff <name>." % name)
        return
    if len(matches) == 1:
        await _offer_exstaff(context, matches[0])
        return
    # multiple -> let owner pick
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        m["canonical_name"] + (" (%s)" % m["call_name"] if m.get("call_name") else ""),
        callback_data="exstaff:pick:%d" % m["id"])] for m in matches[:6]])
    await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID,
        text="Which one left?", reply_markup=kb)


async def exstaff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action, staff_id = parts[1], int(parts[2])
    staff = next((s for s in staff_all() if s["id"] == staff_id), None)
    if not staff:
        await query.edit_message_text("Staff record not found."); return
    if action == "no":
        await query.edit_message_text("Okay, keeping %s as active." % staff["canonical_name"]); return
    if action == "pick":
        await query.edit_message_text("Selected %s." % staff["canonical_name"])
        await _offer_exstaff(context, staff); return
    if action == "go":
        await query.edit_message_text("Processing %s..." % staff["canonical_name"])
        await _do_exstaff(context, staff)


async def _private_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All loose private text. Owner -> test dispatch / departure detection. A live staffer ->
    complete a pending attendance flow, else open their own attendance menu, else roll-call.
    (One router because PTB lets only the first matching handler in a group fire.)"""
    if not update.message or not update.effective_user:
        return
    uid = update.effective_user.id
    if uid == config.OWNER_TELEGRAM_ID:
        if context.user_data.get("att_test_pending"):
            await _att_dispatch(update, context,
                                context.user_data.pop("att_test_pending", None), live=False)
            return
        await _owner_private_departure(update, context)
    else:
        # live attendance entry (gated): a typed reason completes a real flow; otherwise the
        # active staffer opens their own menu. Falls through to roll-call when not live.
        if _attendance_live():
            from shared.database import flow_load_or_expired, flow_clear
            from gm_bot import attendance_ui
            active, expired = flow_load_or_expired(uid)
            if active and active.get("flow") == "att_pending":
                pend = active.get("data") or {}
                flow_clear(uid)
                await _att_dispatch(update, context, pend, live=True)
                return
            if expired and expired.get("flow") == "att_pending":
                # F3/Law 6: they typed their reason AFTER the prompt expired. Don't let a cheerful
                # fresh menu eat it — push an honest 'NOT CONFIRMED — TRY AGAIN' with what expired.
                ep = expired.get("data") or {}
                await _expiry_nudge(context, update.effective_chat.id, ep.get("_summary") or "",
                                    old_chat=ep.get("_prompt_chat"), old_msg=ep.get("_prompt_msg"))
                return
            rec = staff_get_by_uid(uid)
            if rec and rec.get("status") == "active" and rec.get("org") == "TWB":
                # F8: opening a fresh menu RESETS the selection stashes — so a message typed
                # mid-pick would silently wipe the days/time/swap they were choosing. Guard it:
                # tell them they're mid-pick instead of destroying the selection.
                if (context.user_data.get("att_al_picked")
                        or context.user_data.get("att_do_day")
                        or context.user_data.get("att_al_from") is not None):
                    # in-message exit: a BUTTON bypasses this text guard, so the trap always has a way out
                    await update.message.reply_text(
                        "You're in the middle of picking — tap ✅ Done or ✕ Cancel on the message above,"
                        " or open a fresh menu below.\n"
                        "ប្អូនកំពុងជ្រើសរើស — សូមចុច ✅ រួចរាល់ ឬ ✕ បោះបង់ នៅសារខាងលើ ឬបើក menu ថ្មីខាងក្រោម។",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                            "📋 Open a fresh menu · បើក menu ថ្មី", callback_data="att:menu")]]))
                    return
                await attendance_ui.open_live_menu(update, context, rec)
                return
        from gm_bot import rollcall
        await rollcall.handle_staff_private(update, context)


async def _late_simarr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:simarr:{persona}:{early|ontime|late}[:{mins}] — TEST ONLY: simulate the staffer's actual
    arrival (they declared late but may arrive earlier) → run the REAL check-in verdict + messages.
    early >5 = +points, on-time (±5) = free, late >5 = combined verdict+payback picker."""
    query = update.callback_query
    await query.answer()
    if not _att_test_mode() or update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    from gm_bot import attendance_ui
    parts = query.data.split(":")
    persona = next((s for s in staff_all("active") if s["id"] == int(parts[2])), None)
    if not persona:
        return
    outcome = parts[3]
    nm = persona.get("call_name") or persona["canonical_name"]
    suid = (persona.get("telegram_ids") or [None])[0]
    try:
        await query.edit_message_text((query.message.text or "") + "\n\n📍 Arrived (simulated: %s)." % outcome)
    except Exception:
        pass
    if outcome == "early":
        await _att_send(context, suid, "Staff", nm, attendance_ui._V_EARLY % (10, 10))
    elif outcome == "ontime":
        await _att_send(context, suid, "Staff", nm, attendance_ui._V_ONTIME)
    else:   # late >5 — combined verdict + payback picker
        mins = int(parts[4])
        today = _today_pp().isoformat()
        # show the POINTS split (owner Jun 13: the sim never displayed it, so declaring 'Late' looked
        # like it earned nothing). Mirror the real verdict's split_late: declaring before arrival
        # credits the cheaper −1/min informed rate.
        try:
            from shared.database import late_declared_at
            from gm_bot.points import split_late
            from gm_bot.attendance import to_min
            ws = to_min(persona.get("work_start"))
            dec = late_declared_at(persona["id"], today)
            off = None
            if dec is not None and ws is not None:
                sd0 = datetime.fromisoformat(today).replace(tzinfo=finance.PP_TZ) + timedelta(minutes=ws)
                off = int((dec.astimezone(finance.PP_TZ) - sd0).total_seconds() // 60)
            un_min, inf_min = split_late(mins, off)
            pts = inf_min + un_min * 2
            await _att_send(context, config.OWNER_TELEGRAM_ID, "Staff", nm,
                "📊 Points (test): %d min late → %d informed (−1/min) + %d uninformed (−2/min) = −%d.\n"
                "Declaring 'Late' before you arrive earns the cheaper informed rate."
                % (mins, inf_min, un_min, pts))
        except Exception:
            pass
        payback_add_debt(persona["id"], mins, "late arrival (test)", today)
        d = payback_open_debt(persona["id"])
        if d:
            await _offer_payback(context, persona, d["balance"], config.OWNER_TELEGRAM_ID, late_min=mins)


async def _ci_simcheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:cisco:{persona} — TEST ONLY: simulate a FULL checkout end-to-end. Ensures a check-in
    session (at the shift's start), checks out at the shift's end, runs the REAL settle, and reports
    the banking (worked · OT earned vs normal length · payback cleared · OT banked) + sends the same
    thank-you the staffer would get. Prefers an approved shift-redefine (today or yesterday's
    overnight) so Give-OT → approve → checkout → banking is walkable; falls back to the normal shift
    (OT 0). No behaviour fork — it drives the same att_check_in/out + _settle_redefined_shift the
    live scheduler uses, only with simulated timestamps. Test-isolated (is_test rows; real bank
    untouched)."""
    query = update.callback_query
    await query.answer()
    if not _att_test_mode() or update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    persona = next((s for s in staff_all("active") if s["id"] == int(query.data.split(":")[2])), None)
    if not persona:
        return
    from datetime import date as _date, timedelta as _td
    from shared.database import (shift_change_active, att_check_in, att_check_out, payback_open_debt)
    from gm_bot.attendance_ui import shift_len_min, _hm
    from gm_bot.attendance import to_min
    from gm_bot import attendance_ui as ui
    nm = persona.get("call_name") or persona["canonical_name"]
    suid = (persona.get("telegram_ids") or [None])[0]
    today = _today_pp()

    # which shift? prefer an approved redefine on today, then yesterday (overnight tail)
    sc, sd = None, today.isoformat()
    for cand in (today.isoformat(), (today - _td(days=1)).isoformat()):
        g = shift_change_active(persona["id"], cand)
        if g:
            sc, sd = g, cand
            break
    if sc:
        start_min, end_min, normal_len = int(sc["start_min"]), int(sc["end_min"]), int(sc["normal_len"] or 0)
    else:
        ws = to_min(persona.get("work_start"))
        ln = shift_len_min(persona.get("work_start"), persona.get("work_end")) or 0
        if ws is None or not ln:
            await query.edit_message_text((query.message.text or "") +
                "\n\n⚠ %s has no shift times set — can't simulate." % nm)
            return
        start_min, end_min, normal_len = ws, ws + ln, ln

    base = datetime.combine(_date.fromisoformat(sd), datetime.min.time(), tzinfo=finance.PP_TZ)
    ci_dt, co_dt = base + _td(minutes=start_min), base + _td(minutes=end_min)

    debt0 = payback_open_debt(persona["id"])
    pb0 = max(0, debt0["balance"]) if debt0 else 0
    att_check_in(persona["id"], sd, ci_dt.isoformat(), True, 0, 0)
    att_check_out(persona["id"], sd, co_dt.isoformat())
    banked, new_bal = _settle_redefined_shift(persona, sd, co_dt)
    debt1 = payback_open_debt(persona["id"])
    pb1 = max(0, debt1["balance"]) if debt1 else 0

    worked = end_min - start_min
    earned = max(0, worked - normal_len)
    pb_cleared = max(0, pb0 - pb1)
    win = "%s–%s" % (_fmt_min(start_min), _fmt_min(end_min))
    summary = ("🧪 Simulated checkout — %s, %s %s.\n"
               "Worked %s · normal %s · OT earned %s.\n"
               "→ cleared %s payback, banked %s OT.\n"
               "(test only: the shift-change row is marked done; the real OT bank is untouched.)"
               % (nm, sd, win, _hm(worked), _hm(normal_len), _hm(earned),
                  _hm(pb_cleared), _hm(banked)))
    try:
        await query.edit_message_text((query.message.text or "") + "\n\n" + summary)
    except Exception:
        await _att_send(context, config.OWNER_TELEGRAM_ID, "Owner", "", summary)
    await _att_send(context, suid, "Staff", nm, ui._CO_DONE)
    if banked > 0:                                   # close the loop: offer to take the OT back as rest
        await _offer_buyback(context, persona, new_bal, suid, banked)


async def _att_paused(query, uid) -> bool:
    """A5/F12: ANY staff-reachable att:* handler — if attendance is paused (live OFF) and the tapper
    isn't the owner, tell them it's paused instead of acting. Returns True if paused (caller returns)."""
    if uid != config.OWNER_TELEGRAM_ID and not _attendance_live():
        try:
            await query.answer("🔧 Attendance is paused for maintenance — please talk to your senior."
                               " · ប្រព័ន្ធត្រូវបានផ្អាក — សូមនិយាយទៅបងៗ។", show_alert=True)
        except Exception:
            pass
        return True
    return False


async def _att_go_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """att:go — tap-to-confirm for the no-reason flows (replaces typing 'go'). Owner test uses the
    user_data pending; a live staffer uses flow_state. Fires the real submit_* via _att_dispatch."""
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if await _att_paused(query, uid):
        return
    btn_nonce = (query.data or "").split(":")[2] if len((query.data or "").split(":")) > 2 else None
    # PEEK the current pend (don't consume yet) so a stale/cross-flow tap can't eat a live pend (A3).
    pend, live, is_owner = None, False, (uid == config.OWNER_TELEGRAM_ID)
    if is_owner:
        pend = context.user_data.get("att_test_pending")
    elif _attendance_live():
        from shared.database import flow_load
        fs = flow_load(uid)
        if fs and fs.get("flow") == "att_pending":
            pend = fs.get("data") or {}
            live = True
    # A3: a stale confirm card whose nonce ≠ the CURRENT pend must NOT submit that pend.
    if pend and btn_nonce is not None and pend.get("_go_nonce") and str(pend["_go_nonce"]) != btn_nonce:
        await query.answer("↩ Replaced — please use the newest message.\n↩ សូមប្រើសារថ្មីបំផុត។",
                           show_alert=True)
        return
    if not pend:
        # A2: a double-tap of an ALREADY-confirmed card → say so calmly, don't push a scary nudge.
        if "✅ Confirmed" in (query.message.text or ""):
            await query.answer("Already confirmed ✓ · បានបញ្ជាក់រួចហើយ", show_alert=True)
            return
        # F2/Law 6: a genuinely expired/dead tap-confirm → honest push + remove the stale card.
        await _expiry_nudge(context, update.effective_chat.id, (query.message.text or "").strip(),
                            old_chat=query.message.chat_id, old_msg=query.message.message_id)
        return
    # matched (or a legacy no-nonce button) → CONSUME the pend now, then submit
    if is_owner:
        context.user_data.pop("att_test_pending", None)
    elif live:
        from shared.database import flow_clear
        flow_clear(uid)
    try:
        await query.edit_message_text((query.message.text or "") + "\n\n✅ Confirmed.")
    except Exception:
        pass
    await _att_dispatch(update, context, pend, live=live, reason="(confirmed)")


def _al_requested_amount(persona: dict, kind: str, days: list, hours_start, hours_end) -> float:
    """The AL days this request would deduct — mirrors _al_finalize (hours → fractional; day-offs and
    other absences are never double-charged) so a staff-side balance check matches the real deduction."""
    from gm_bot import al as alm
    from gm_bot.attendance import to_min
    nw = staff_absent_dates(persona["id"])
    sl = (((to_min(persona.get("work_end")) or 0) - (to_min(persona.get("work_start")) or 0)) % 1440) or 1440
    frac = (alm.fractional_al(to_min(hours_start), to_min(hours_end), sl)
            if kind == "hours" and hours_start else 1.0)
    return alm.al_day_count(days, kind, frac, day_off=persona.get("day_off"), non_working=nw)


async def _att_dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        pend: dict | None, *, live: bool, reason: str | None = None) -> None:
    """Complete a reason/'go' terminal by firing the REAL submit_* — for a live staffer acting as
    THEMSELVES (live=True; routes to the real seniors/Supervisors/owner) or the owner role-playing
    a persona (live=False; every message routes to the owner, rows is_test-tagged). ONE code path
    for both: the only differences are the actor, the requester uid, the late collapse, and copy."""
    if not pend:
        return
    # A1 (Fable): a flow is being submitted — the selection is captured in the pend, so the per-flow
    # selection stashes are now stale. Clear them, or a leftover att_al_picked/att_do_day/att_al_from
    # makes the F8 mid-pick guard fire forever on the staffer's later typed text.
    try:
        from gm_bot.attendance_ui import reset_selection
        reset_selection(context)
    except Exception:
        pass
    if reason is None:   # typed-reason flows read the message; tap-to-confirm flows pass it in
        reason = (((update.message.text or "").strip()) if update.message else "") or "(no reason)"
    if live:
        persona = staff_get_by_uid(update.effective_user.id)
        if not persona or persona.get("status") != "active":
            return
        req_uid = update.effective_user.id
    else:
        persona = next((s for s in staff_all("active") if s["id"] == pend.get("persona_id")), None)
        if not persona:
            await update.message.reply_text("🧪 test persona not found — pick again via /test.")
            return
        req_uid = config.OWNER_TELEGRAM_ID

    async def confirm(live_text: str, test_text: str) -> None:
        # If the flow captured its reason-PROMPT message (pend['_summary'] + coords), edit it in place
        # into an "awaiting approval" card carrying the same info + the typed reason, so the prompt no
        # longer sits stale after the reason is sent.
        pc, pm, summ = pend.get("_prompt_chat"), pend.get("_prompt_msg"), pend.get("_summary")
        if pc and pm and summ:
            card = ("%s\n\n📝 %s\n\n⏳ Awaiting approval · កំពុងរង់ចាំការអនុម័ត" % (summ, reason))
            try:
                await context.bot.edit_message_text(card, chat_id=pc, message_id=pm)
            except Exception:
                pass
        txt = live_text if live else test_text
        if update.message is not None:
            await update.message.reply_text(txt)
        else:   # came from a tap (att:go) — no message to reply to
            await context.bot.send_message(update.effective_chat.id, txt)

    flow = pend.get("flow")
    if flow == "al":
        # Balance guard (owner, session 32): if the request needs more AL than they have, tell the
        # STAFF to pick a smaller amount — don't bother the seniors with an impossible request.
        # (Special leave — marriage/death/birth — has its own flows that MAY go negative; not here.)
        bal = persona.get("al_left")
        if bal is not None:
            amount = _al_requested_amount(persona, pend["kind"], pend["days"],
                                          pend.get("hours_start"), pend.get("hours_end"))
            if amount > float(bal) + 1e-9:
                over = ("⚠ You only have %g AL day(s) left, but this request needs %g.\n"
                        "Please choose a smaller amount — you can request up to %g.\n"
                        "⚠ ប្អូននៅសល់ AL តែ %g ថ្ងៃប៉ុណ្ណោះ ប៉ុន្តែសំណើនេះត្រូវប្រើ %g ថ្ងៃ។\n"
                        "សូមជ្រើសចំនួនតិចជាងនេះ — ប្អូនអាចស្នើបានច្រើនបំផុត %g ថ្ងៃ។"
                        % (float(bal), amount, float(bal), float(bal), amount, float(bal)))
                if update.message is not None:
                    await update.message.reply_text(over)
                else:
                    await context.bot.send_message(update.effective_chat.id, over)
                return
        req_id = await submit_al_request(context, persona, pend["kind"], pend["days"],
                                         pend.get("hours_start"), pend.get("hours_end"), reason, req_uid)
        if req_id is None:
            return   # blocked: a day is already approved leave / a scheduled change (requester told)
        # the requester's OWN card: rich (carries the persistent 👁 Show-who's-working toggle), edited
        # in place over the reason prompt + registered so _al_finalize can flip it to 'decided'.
        pc, pm = pend.get("_prompt_chat"), pend.get("_prompt_msg")
        req_obj = al_get_request(req_id)
        if req_obj and pc and pm:
            rbody, rkb = _al_card(req_obj, persona, audience="staff", show_cov=False)
            try:
                await context.bot.edit_message_text(rbody, chat_id=pc, message_id=pm,
                                                    reply_markup=rkb, parse_mode="HTML")
                context.bot_data.setdefault("al_staff_cards", {})[req_id] = (pc, pm)
            except Exception:
                pass
        pend.pop("_summary", None)   # AL renders its own rich card — skip the generic prompt edit
        await confirm(
            "✅ AL request sent — your seniors will review it. I'll message you when it's decided.\n"
            "✅ បានផ្ញើសំណើ AL — បងៗនឹងពិនិត្យ ហើយខ្ញុំនឹងប្រាប់ពេលមានការសម្រេច។",
            "🧪 AL request submitted (test) — the senior approval cards were routed to you. Tap ✅ to "
            "reach quorum (2 seniors; 1 if the requester is a senior), then watch the requester + "
            "Supervisors messages. /testreset to wipe.")
    elif flow == "late":
        from gm_bot.attendance import to_min
        mins = int(pend.get("mins") or 0)
        today = _today_pp().isoformat()
        ws = to_min(persona.get("work_start"))
        nm = persona.get("call_name") or persona["canonical_name"]
        from gm_bot.attendance_ui import _hm
        if pend.get("_declared"):
            # declare-Late-first: the declaration + heads-up already went out at pick time. ATTACH the
            # reason to that same record (no duplicate row → split-late moment preserved) and send the
            # reason as an addendum.
            from shared.database import late_set_reason
            late_set_reason(persona["id"], today, reason)
            await _att_send(context, None, "Supervisors group", "",
                "Reason from %s (late ~%s today) · មូលហេតុពី %s៖ %s"
                % (nm, _hm(mins), nm, reason), group=True)
        else:
            # legacy path (not declared-first): full heads-up carrying the reason
            late_declare(persona["id"], today, (ws + mins) if ws is not None else mins, reason)
            await _att_send(context, None, "Supervisors group", "",
                "%s will be ~%s late for today's shift.\n"
                "%s នឹងមកយឺតប្រហែល %s សម្រាប់វេនថ្ងៃនេះ។\n"
                "Reason · មូលហេតុ៖ %s"
                % (nm, _hm(mins), nm, _hm(mins), reason), group=True)
        # Law 8: the late reason-prompt is consumed — delete it so it doesn't sit stale above the
        # outcome (the live confirm / test sim-arrival buttons are the fresh message). Best-effort.
        _pc, _pm = pend.get("_prompt_chat"), pend.get("_prompt_msg")
        if _pc and _pm:
            try:
                await context.bot.delete_message(_pc, _pm)
            except Exception:
                pass
        if not live:
            # TEST: mirror the LIVE split — declare = heads-up only; the outcome appears on ARRIVAL.
            # They CLICKED late, but might actually arrive early / on-time / late — so offer all three
            # to simulate, each running the REAL check-in verdict (5-min grace included).
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📍 Arrived >5 min EARLY (in zone)",
                                      callback_data="att:simarr:%d:early" % persona["id"])],
                [InlineKeyboardButton("📍 Arrived on-time (±5 min — free)",
                                      callback_data="att:simarr:%d:ontime" % persona["id"])],
                [InlineKeyboardButton("📍 Arrived >5 min LATE (~%d min)" % mins,
                                      callback_data="att:simarr:%d:late:%d" % (persona["id"], mins))]])
            await update.message.reply_text(
                "🧪 Late declared (test) — Supervisors heads-up sent. In LIVE the outcome appears when "
                "they ARRIVE & share live location. Simulate the arrival (they may be earlier than they "
                "thought):", reply_markup=kb)
            return
        # LIVE: heads-up only — payback appears on real arrival via _handle_staff_location.
        await confirm(
            "✅ Thanks for letting us know — travel safely. Share your live location when you arrive "
            "and I'll work out the time.\n"
            "✅ អរគុណដែលប្រាប់ — សូមធ្វើដំណើរដោយសុវត្ថិភាព។ ពេលមកដល់ សូមចែករំលែកទីតាំងផ្ទាល់ ខ្ញុំនឹងគណនាម៉ោងឱ្យ។",
            "🧪 Late declared (test) — Supervisors heads-up + the payback slot picker were routed to "
            "you. Tap a slot to book it. /testreset to wipe.")
    elif flow == "shift":
        receiver = next((s for s in staff_all("active") if s["id"] == pend.get("staff_id")), None)
        if not receiver:
            await update.message.reply_text("staff not found." if live else "🧪 staff not found.")
            return
        await submit_shift_change(context, persona, receiver, pend["when_date"],
                                  pend["start_min"], pend["end_min"], pend["normal_len"], reason)
        await confirm(
            "✅ Shift change sent — the staff is asked to approve.\n"
            "✅ បានផ្ញើការស្នើប្តូរវេនហើយ — កំពុងរង់ចាំបុគ្គលិកយល់ព្រម។",
            "🧪 Shift change submitted (test) — you got the staff's Approve/Can't card. On Approve, that "
            "day uses the new times; OT (beyond normal length) banks at checkout, clearing payback first. "
            "/testreset to wipe.")
    elif flow == "swap":
        partner = next((s for s in staff_all("active") if s["id"] == pend.get("partner_id")), None)
        if not partner:
            await update.message.reply_text("swap partner not found." if live
                                            else "🧪 swap partner not found.")
            return
        swap_id = await submit_swap(context, persona, partner, pend["req_off_date"],
                                    pend["partner_off_date"], reason)
        # the requester's OWN card: rich, carries the both-days toggle, edited over the reason prompt
        # + registered so the partner/senior decisions flip it in place.
        pc, pm = pend.get("_prompt_chat"), pend.get("_prompt_msg")
        sw_obj = swap_get(swap_id)
        if sw_obj and pc and pm:
            rbody, rkb = _swap_card(sw_obj, persona, partner, audience="requester", show_cov=False)
            try:
                await context.bot.edit_message_text(rbody, chat_id=pc, message_id=pm,
                                                    reply_markup=rkb, parse_mode="HTML")
                context.bot_data.setdefault("swap_req_cards", {})[swap_id] = (pc, pm)
            except Exception:
                pass
        pend.pop("_summary", None)   # swap renders its own rich card — skip the generic prompt edit
        await confirm(
            "✅ Day-off swap sent — your partner agrees first, then the seniors approve.\n"
            "✅ បានផ្ញើសំណើប្តូរថ្ងៃឈប់ — ដៃគូយល់ព្រមមុន បន្ទាប់មកបងៗអនុម័ត។",
            "🧪 Swap submitted (test) — the partner agree-card was routed to you. Tap ✅ I agree, then "
            "approve as the seniors (2; or 1 if the requester is a senior), then watch the Supervisors "
            "notice. /testreset to wipe.")
    elif flow == "marriage":
        from datetime import date as _date, timedelta as _td
        d0 = _date.fromisoformat(pend["start_date"])
        days = ([pend["start_date"]] if pend.get("child")
                else [(d0 + _td(days=i)).isoformat() for i in range(3)])
        await submit_al_request(context, persona, "days", days, None, None,
                                "Marriage leave", req_uid)   # own wedding — no reason needed
        await confirm(
            "✅ Marriage leave sent for senior approval. Congratulations 🎉\n"
            "✅ បានផ្ញើសំណើច្បាប់រៀបការសម្រាប់អនុម័ត។ សូមអបអរសាទរ 🎉",
            "🧪 Marriage leave submitted (test, via the AL approval engine) — senior cards routed to "
            "you; approve as the seniors (2; or 1 if the requester is a senior). /testreset to wipe.")
    elif flow == "death":
        await book_family_death(context, persona, pend["who"], pend["start_date"])
        await confirm(
            "🤍 Sorry for your loss — the leave is booked and the Supervisors are notified.\n"
            "🤍 សូមរំលែកមរណទុក្ខ — ច្បាប់ត្រូវបានកត់ត្រា ហើយបានជូនដំណឹងដល់បងៗ។",
            "🧪 Family-death leave booked (test) — condolence + Supervisors notice routed to you; for "
            "a sibling/grandparent the owner upgrade card too. /testreset to wipe.")
    elif flow == "birth":
        await book_wife_birth(context, persona, pend["start_date"])
        await confirm(
            "👶 Congratulations! The leave is booked and the Supervisors are notified.\n"
            "👶 សូមអបអរសាទរ! ច្បាប់ត្រូវបានកត់ត្រា ហើយបានជូនដំណឹងដល់បងៗ។",
            "🧪 Wife-birth leave booked (test) — congratulations + Supervisors notice routed to you. "
            "/testreset to wipe.")
    elif flow == "sick_me":
        # provisional case + paperless payback + rest-well + the FYI carrying the typed reason
        # (papers are mentioned ONCE; pay-back never spelled out) — shared with the auto-resolve.
        await _sickme_book(context, persona, pend["date"], reason)
        await confirm(
            "🤍 Rest well — I've noted your sick leave. If you see a doctor, send a photo of the papers.\n"
            "🤍 សម្រាកឱ្យបានល្អ — ខ្ញុំបានកត់ត្រាច្បាប់ឈឺ។ បើបានជួបពេទ្យ សូមផ្ញើរូបថតឯកសារមក។",
            "🧪 Provisional own-sick case opened (test). Now SEND A PHOTO to this chat to test the "
            "doctor-papers → owner-card → accept/part-duty flow. /testreset to wipe.")
    elif flow == "sick_fam":
        sick_create(persona["id"], pend["who"], pend["date"], "open")
        nm = persona.get("call_name") or persona["canonical_name"]
        await _att_send(context, None, "Supervisors group", "",
            "FYI: %s takes sick leave for their %s today.\n"
            "FYI: %s សុំច្បាប់ឈឺសម្រាប់%sថ្ងៃនេះ។" % (nm, pend["who"], nm, _who_kh(pend["who"])), group=True)
        await confirm(
            "🤍 Noted — take care of your %s. The Supervisors are informed.\n"
            "🤍 បានកត់ត្រា — សូមថែទាំ%sរបស់អ្នក។ បានជូនដំណឹងដល់បងៗ។" % (pend["who"], _who_kh(pend["who"])),
            "🧪 Family-sick day booked (test) — the Supervisors FYI was routed to you. /testreset to wipe.")
    elif flow == "sfam_exp":
        # the typed reason for NOT coming after a family-sick day → books tomorrow (burns another
        # of the 7) + the reason goes to the Supervisors. Status-first → re-sends can't double-book.
        case = sick_get(pend["case_id"])
        if case and case.get("status") == "open":
            await _sfam_book(context, case, reason)
        await confirm(
            "Noted — tomorrow is covered. Take care 🤍\n"
            "កត់ចំណាំហើយ — ស្អែកបានរៀបចំការឈប់ឱ្យរួចហើយ។ ថែទាំឱ្យបានល្អ 🤍",
            "🧪 Family-sick extended with reason (test) — the group FYI was routed to you.")
    elif flow == "rej_exp":
        # a decliner's typed reason → relayed to whoever the decision already reached
        # (the destination never changes; only the explanation is added)
        tgt = next((s for s in staff_all("active") if s["id"] == pend.get("to_sid")), None)
        if tgt:
            # bilingual (owner: some staff won't understand English)
            await _att_send(context, (tgt.get("telegram_ids") or [None])[0], "Staff",
                tgt.get("call_name") or tgt["canonical_name"],
                "📝 About your %s — %s:\n📝 អំពី %s របស់ប្អូន — %s៖\n%s"
                % (pend.get("what", "request"), pend.get("frm", "—"),
                   pend.get("what_kh", pend.get("what", "request")), pend.get("frm", "—"), reason))
        await confirm("Sent 🤍\nផ្ញើរួចហើយ 🤍", "🧪 Reason relayed (test) — routed to you.")
    elif flow == "sret_exp":
        # the typed reason for still-resting (own sick) → the Supervisors read it
        nm = persona.get("call_name") or persona["canonical_name"]
        await _att_send(context, None, "Supervisors group", "",
            "FYI: %s is still resting — NOT back tomorrow.\n"
            "FYI: %s នៅតែសម្រាក — ស្អែកមិនទាន់មកធ្វើការទេ។\n"
            "Reason · មូលហេតុ៖ %s"
            % (nm, nm, reason), group=True)
        await confirm(
            "Rest well 🤍 get better.\nសម្រាកឱ្យបានល្អ 🤍 ឆាប់ជាសះស្បើយ។",
            "🧪 Still-resting reason (test) — the group FYI was routed to you.")


async def _owner_private_departure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner DMs GM in plain language that someone left -> offer the ex-staff flow.
    Silent on anything that isn't a clear departure message (won't disturb other flows)."""
    if not update.message or update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    text = (update.message.text or "").strip()
    if not text or not any(p in text.lower() for p in _DEPARTURE_PHRASES):
        return
    tl = text.lower()
    hits = [s for s in staff_all("active")
            if any(a and len(a) >= 3 and a.lower() in tl
                   for a in [s["canonical_name"], s.get("call_name")] + s.get("aliases", []))]
    if not hits:
        await update.message.reply_text("Got it — who left? I couldn't match a name. Use /exstaff <name>.")
        return
    # de-dup by id, offer
    seen, uniq = set(), []
    for s in hits:
        if s["id"] not in seen:
            seen.add(s["id"]); uniq.append(s)
    if len(uniq) == 1:
        await _offer_exstaff(context, uniq[0])
    else:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            s["canonical_name"], callback_data="exstaff:pick:%d" % s["id"])] for s in uniq[:6]])
        await update.message.reply_text("Which one left?", reply_markup=kb)


async def _new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A member JOINED an internal group -> if they're registered active staff who haven't
    pressed Start with the GM yet, post a friendly in-group nudge tagging them to do so
    (session 28). Safe by design: fires ONLY for registered active staff, only if not yet
    greeted, once per uid (throttled in gm_state), never for customers/bots/unknowns."""
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    if msg.chat_id not in [cid for _, cid in _internal_groups()]:
        return
    for member in msg.new_chat_members:
        if member.is_bot:
            continue
        uid = member.id
        staff = staff_get_by_uid(uid)
        if not staff or staff.get("status") != "active":
            # unknown / ex-staff: say nothing in-group, but tell the OWNER once (session 28) —
            # could be a new hire, someone's new account, or a stranger to remove.
            if not staff and gm_get_state("unknown_join_noted:%d" % uid) != "true":
                gm_set_state("unknown_join_noted:%d" % uid, "true")
                label = next((l for l, c in _internal_groups() if c == msg.chat_id), str(msg.chat_id))
                who = member.full_name + (" @" + member.username if member.username else "")
                try:
                    await context.bot.send_message(
                        config.OWNER_TELEGRAM_ID,
                        "❓ Unknown account joined %s: %s (uid %d).\n"
                        "New hire, someone's new account, or to remove?" % (label, who, uid))
                except Exception:
                    pass
            continue  # offboarding handles leavers
        if gm_get_state("rollcall_greeted:%d" % uid) == "true":
            continue  # already started with the GM
        if gm_get_state("welcome_nudged:%d" % uid) == "true":
            continue  # throttle: re-adds don't re-spam
        gm_set_state("welcome_nudged:%d" % uid, "true")
        call = staff.get("call_name") or staff["canonical_name"]
        try:
            await context.bot.send_message(
                chat_id=msg.chat_id,
                text=("👋 Welcome %s! Please open @twb_gm_bot and press START so I can help "
                      "you with attendance.\n"
                      "សូមស្វាគមន៍ %s! សូមបើក @twb_gm_bot ហើយចុច START ដើម្បីឱ្យខ្ញុំអាចជួយ"
                      "អ្នកអំពីវត្តមាន។" % (_staff_mention(call, uid), call)),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("welcome nudge failed: %s", e)


async def _left_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A member left an internal group -> if they're known active staff, ask the owner
    whether they left the company."""
    msg = update.message
    if not msg or not msg.left_chat_member:
        return
    if msg.chat_id not in [cid for _, cid in _internal_groups()]:
        return
    uid = msg.left_chat_member.id
    staff = staff_get_by_uid(uid)
    if not staff or staff.get("status") != "active":
        return
    label = next((l for l, c in _internal_groups() if c == msg.chat_id), str(msg.chat_id))
    await _offer_exstaff(context, staff,
                         why="%s just left the %s group." % (staff["canonical_name"], label))


def _weekly_brain_block(facts: dict, today, mix: dict | None = None):
    """BRAIN: render the exact weekly facts the owner sees (time-ledger, counts, open debts), the
    frequency pattern flags, AND — for the staffers that matter — their 30-day reason MIX, which Brain
    aggregated from the model's category labels (`mix` = {staff: {category: count}}). Deterministic;
    Opus never counts. Returns (owner_text, facts_summary for Opus, reasons_block, flags)."""
    from gm_bot.attendance_ui import _hm
    from gm_bot import frequency as fq
    mix = mix or {}
    flags = []
    for staff, dates in sorted((facts.get("late_dates_by_staff") or {}).items()):
        f = fq.detect(dates, today)
        if f:
            flags.append((staff, f["detail"]))
    lines = [
        "📊 This week (from button check-ins):",
        "Time ledger: staff owe %s (%d debts) · shop owes %s (%d banks)"
        % (_hm(facts["owe_min"]), len(facts["open_debts"]), _hm(facts["bank_min"]), facts["bank_count"]),
        "Late: %d · No-show: %d · AL approved: %d · Special leave: %d"
        % (len(facts["lates"]), len(facts["no_shows"]), len(facts["als"]), len(facts["specials"])),
    ]
    if flags:
        lines.append("Patterns: " + " · ".join("%s — %s" % (s, d) for s, d in flags))
    # reason MIX for flagged staffers (Brain's exact tally of the model's category labels, 30d)
    for staff, _d in flags:
        m = mix.get(staff)
        if m:
            top = sorted(m.items(), key=lambda kv: -kv[1])
            lines.append("  %s reasons (30d): %s" % (staff, ", ".join("%s×%d" % (k, v) for k, v in top)))
    if facts["open_debts"]:
        top = sorted(facts["open_debts"], key=lambda x: -x["min"])[:8]
        lines.append("Open debts: " + ", ".join("%s %s" % (d["staff"], _hm(d["min"])) for d in top))
    owner_text = "\n".join(lines)
    facts_summary = "\n".join(lines[1:])  # the figures, minus the header (Opus must not recount these)
    reasons = []
    for l in facts["lates"]:
        if l["reason"]:
            reasons.append("%s (late %dm on %s%s): %s"
                           % (l["staff"], l["min"], l["date"],
                              "" if l["informed"] else ", uninformed", l["reason"]))
    for a in facts["als"]:
        if a.get("reason"):
            reasons.append("%s (AL): %s" % (a["staff"], a["reason"]))
    return owner_text, facts_summary, "\n".join(reasons), flags


async def _weekly_attendance_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Once a week (Monday, Phnom Penh): Opus digests the week's lateness + attendance
    notes and DMs the owner. Skips quietly when there's nothing to report."""
    now_pp = datetime.now(finance.PP_TZ)
    if now_pp.weekday() != 0:  # 0 = Monday
        return
    try:
        if _attendance_live():
            # SPLIT DIGEST: Brain computes ALL the numbers + pattern flags (exact, never miscounts);
            # Opus 4.8 only narrates over the verbatim REASONS. Best of both — facts free + insight.
            from shared.database import gm_weekly_attendance_facts, gm_lateness_reasons_since
            today_iso = now_pp.date().isoformat()
            facts = gm_weekly_attendance_facts(today_iso)
            has = any(facts[k] for k in ("lates", "no_shows", "als", "specials", "open_debts")) \
                or facts["bank_min"]
            if not has:
                logger.info("Weekly digest (live): no data, skipping")
                return
            # Reason MIX: model (Haiku) labels each 30-day reason → category; Brain tallies the labels
            # into exact per-staff trends (analysis-time, one cheap batched call).
            rows = gm_lateness_reasons_since(today_iso, 30)
            mix: dict = {}
            if rows:
                cats = await categorize_reasons([r["reason"] for r in rows])
                for r, c in zip(rows, cats):
                    bucket = mix.setdefault(r["staff"], {})
                    bucket[c] = bucket.get(c, 0) + 1
            brain_text, facts_summary, reasons_block, _flags = _weekly_brain_block(facts, now_pp.date(), mix)
            narrative = await narrate_attendance_week(facts_summary, reasons_block)
            header = "🗓️ Weekly attendance digest (%s)\n\n" % now_pp.strftime("%d %b %Y")
            body = brain_text + (("\n\n📝 " + narrative) if narrative else "")
            await context.bot.send_message(chat_id=config.OWNER_TELEGRAM_ID, text=header + body)
            logger.info("Weekly split digest sent (%d late, %d no-show, %d debts)",
                        len(facts["lates"]), len(facts["no_shows"]), len(facts["open_debts"]))
            return
        # PRE-LIVE fallback: the AI digest read from group-chat cases (no button data yet)
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
    # UNDERSTAND-WITHOUT-REPLY (session 28): exactly ONE open clarification in this chat ->
    # a plain staff message is its candidate answer (the Sonnet judge validates it next).
    if len(text.strip()) >= 3 and not finance.is_daily_report(finance.parse_report_text(text)):
        opens = gm_get_active_clarifications_for_chat(chat_id)
        if len(opens) == 1:
            clar = opens[0]
            gm_answer_clarification(clar["id"], text.strip())
            logger.info("Clarification %s answered via loose message", clar["id"])
            return {"clar": clar, "answer": text.strip()}
    return None


async def _judge_clarification(context, clar: dict, answer: str, answer_msg=None) -> None:
    """Sonnet checks whether the staff reply actually resolves the clarification.
    Resolved -> acknowledge IN-GROUP (session 28: staff must see their fix landed).
    If it doesn't add up, escalate to the owner with the answer + the reason."""
    verdict = await judge_clarification_answer(
        clar.get("question_text") or "", answer, clar["topic"],
    )
    if verdict.get("resolved", True):
        try:
            await context.bot.send_message(
                chat_id=clar["chat_id"],
                text="✓ Got it — thank you!\n✓ បានទទួលហើយ — អរគុណ!",
                reply_to_message_id=answer_msg.message_id if answer_msg else None,
            )
        except Exception:
            pass
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
        # Leave questioning is being replaced by the private-DM flow — don't nudge it.
        if clar.get("topic") == "leave_clarify" and not config.GM_ATTENDANCE_GROUP_ACTIVE:
            continue
        action, new_next = clarify.decide_ladder_action(
            clar["status"], clar["created_at"], now, clar.get("next_action_at"),
        )
        try:
            if action == "nudge":
                reply_to = clar.get("question_msg_id") or clar.get("target_msg_id")
                nudge = clarify.nudge_text(clar["topic"], clar.get("nudge_count", 0))
                try:
                    sent = await context.bot.send_message(
                        chat_id=clar["chat_id"], text=nudge, reply_to_message_id=reply_to,
                    )
                except Exception:
                    sent = await context.bot.send_message(chat_id=clar["chat_id"], text=nudge)
                # replies to this nudge must count as answers (session 28 fix)
                try:
                    gm_add_clarification_nudge_msg(clar["id"], sent.message_id)
                except Exception:
                    pass
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
    """Download a TWB REPORT photo, assess clarity, reply in-group if unclear.
    Per-vendor knowledge (session 28): known vendor rules ride the same Haiku call;
    vendors marked 'skip' are never flagged."""
    try:
        photo_file = await msg.photo[-1].get_file()
        photo_bytes = bytes(await photo_file.download_as_bytearray())
        examples = receipt_get_answered_examples(msg.chat_id)
        vendors = gm_get_vendor_rules()
        result = await assess_receipt_photo(photo_bytes, past_examples=examples,
                                            vendor_rules=vendors)

        # level-1 reconciliation (session 28): expense sheets + POS screens become rows
        if result.get("doc_type") in ("expense_sheet", "pos_screen"):
            try:
                save_report_doc(msg.chat_id, msg.message_id,
                                finance.business_day_for(msg.date).isoformat(),
                                result["doc_type"], result.get("fields") or {})
                logger.info("report doc stored: %s %s", result["doc_type"], result.get("fields"))
            except Exception as e:
                logger.error("save_report_doc failed: %s", e)

        if not result["is_receipt"]:
            return
        vend = (result.get("vendor") or "").lower()
        if vend and any(v["mode"] == "skip" and v["vendor"] in vend for v in vendors):
            logger.info("Receipt from skip-listed vendor %r — not flagged", vend)
            return
        if result["is_clear"]:
            # A clear receipt arrived — resolves any pending "send again / clarify" in this chat.
            gm_resolve_open_clarifications(msg.chat_id, "receipt_clarity", "(clear receipt received)")
            return

        sender = msg.from_user.full_name if msg.from_user else "Staff"
        partial = result.get("readable_partial", "")

        if result.get("is_handwritten") and partial:
            question = (f"Can you tell me what this says? I can see \"{partial}\" but hard to read.\n"
                        f"អាចប្រាប់ខ្ញុំបានទេថានេះសរសេរថាម៉េច? ខ្ញុំមើលឃើញ \"{partial}\" តែអក្សរផ្សេងៗពិបាកអាន។")
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
                reply = (f"Please send this photo again — {issue_text}.\n"
                         f"សូមផ្ញើរូបនេះម្តងទៀត។")
            else:
                reply = ("Please send this photo again — not clear enough to record.\n"
                         "សូមផ្ញើរូបនេះម្តងទៀត — មិនច្បាស់គ្រប់គ្រាន់សម្រាប់កត់ត្រាទេ។")
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
        text="Saved ✓ — I'll use this to read similar receipts.",
        reply_to_message_id=msg.message_id,
    )
    logger.info("Receipt clarification saved for photo_msg %s: %s", clarification["photo_msg_id"], answer[:60])


_PHOTO_WINDOW = 600  # seconds — how long to look back/forward for related photos
_msg_buffer: dict = defaultdict(lambda: deque(maxlen=30))   # (chat_id, uid) → recent messages
_concern_tracker: dict = defaultdict(list)                  # (chat_id, uid) → [(concern_id, ts)]

# GROUP-REDIRECT (zero-API): leave/AL/sick chatter in an internal group → the GM replies to that
# message, tags the SENDER (uid-safe — never parses the named person, so misspellings can't break it),
# and warns it won't count unless they DM the GM. Worded differently each time by rotating these
# variants (no API). The leading "—" makes "{name} — …" read naturally. KH drafts → docs/KH_REVIEW.md.
_GROUP_REDIRECT_LINES = [
    "— AL, sick and days off only count when you tell me directly. Open @twb_gm_bot, or it won't be "
    "recorded 🙂\n— AL, ឈឺ និងថ្ងៃឈប់ នឹងរាប់បានតែពេលប្អូនប្រាប់ខ្ញុំផ្ទាល់។ សូមបើក @twb_gm_bot "
    "បើមិនដូច្នេះ វានឹងមិនត្រូវបានកត់ត្រាទេ 🙂",
    "— quick reminder 🙏 time off has to come to me, not the group. Message @twb_gm_bot so it counts.\n"
    "— រំលឹកបន្តិច 🙏 រឿងសុំឈប់ត្រូវផ្ញើមកខ្ញុំផ្ទាល់ មិនមែនផ្ញើក្នុង group ទេ។ សូមផ្ញើសារទៅ @twb_gm_bot "
    "ដើម្បីឱ្យវារាប់។",
    "— I can only record this if it comes to me 🙂 Please tap @twb_gm_bot; group messages don't count.\n"
    "— ខ្ញុំអាចកត់ត្រារឿងនេះបានតែបើប្អូនផ្ញើមកខ្ញុំផ្ទាល់ 🙂 សូមចុច @twb_gm_bot; សារក្នុង group មិនរាប់ទេ។",
    "— leave, sick and day-off only register when you tell me at @twb_gm_bot. The group chat doesn't "
    "count 🙏\n— AL, ឈឺ និងថ្ងៃឈប់ នឹងត្រូវកត់ត្រាតែពេលប្អូនប្រាប់ខ្ញុំតាម @twb_gm_bot ប៉ុណ្ណោះ។ "
    "សារក្នុង group មិនរាប់ទេ 🙏",
    "— this won't be counted from here 🙂 For AL, sick or time off, message me directly at "
    "@twb_gm_bot.\n— រឿងនេះមិនរាប់ពី group នេះទេ 🙂 សម្រាប់ AL, ឈឺ ឬសុំឈប់ សូមផ្ញើសារមកខ្ញុំផ្ទាល់តាម "
    "@twb_gm_bot។",
]
_REDIRECT_COOLDOWN = 1800   # one nudge per sender per 30 min (never spam a burst of messages)
_redirect_last: dict = {}   # (chat_id, uid) → last-nudged ts


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

    # ops_messages persistence (session 28): the Telethon listener is the canonical recorder —
    # EXCEPT Supervisors + Management, where the GM bot is the PERMANENT sole writer.
    # OWNER DECISION (final): the listener account (TheWineBakery24PP) must NEVER join those
    # groups — junior staff use that account and must not read senior messages. Bot API can't
    # backfill history, so the watchdog also monitors the twbshop-gm service itself.
    if chat_id in (config.SUPERVISORS_CHAT_ID, config.MANAGEMENT_CHAT_ID):
        try:
            media_type = ("photo" if msg.photo else
                          "video" if msg.video else
                          "document" if msg.document else None)
            save_ops_message(chat_id, msg_id, msg.chat.title or None,
                             msg.from_user.id if msg.from_user else None, sender,
                             text or None, media_type,
                             msg.date.isoformat() if msg.date else None)
        except Exception as _e:
            logger.debug("ops_messages log failed: %s", _e)

    logger.debug("Group msg: chat_id=%s title=%r sender=%s", chat_id, msg.chat.title, sender)

    # Did staff respond to a GM clarification question? (any group) — records their reason,
    # then Sonnet checks whether the answer actually adds up.
    if text.strip():
        try:
            resolved = _resolve_clarification_response(chat_id, msg, text)
            if resolved:
                await _judge_clarification(context, resolved["clar"], resolved["answer"], answer_msg=msg)
        except Exception as e:
            logger.error("clarification resolve failed: %s", e)

    # Stock Checks: a photo might be the daily stock-count sheet -> read + store.
    if chat_id == config.STOCK_CHECKS_CHAT_ID and msg.photo:
        try:
            await _handle_stock_photo(context, msg)
        except Exception as e:
            logger.error("stock photo handling failed: %s", e)

    # Supervisors / Management: lateness reports + leave/time-off questioning.
    # OFF by default — replaced by the private-DM attendance system (no group spam).
    if (config.GM_ATTENDANCE_GROUP_ACTIVE and text.strip()
            and chat_id in (config.SUPERVISORS_CHAT_ID, config.MANAGEMENT_CHAT_ID)):
        try:
            await _handle_lateness(context, msg, text, sender)
        except Exception as e:
            logger.error("lateness handling failed: %s", e)
        try:
            await _handle_leave(context, msg, text, sender)
        except Exception as e:
            logger.error("leave handling failed: %s", e)

    # GROUP-REDIRECT (gated, SUPERVISORS group only): attendance talk → point the person to DM the
    # GM (no processing here — forces the private channel). Keyword, zero-API.
    if (_attendance_live() and text.strip() and chat_id == config.SUPERVISORS_CHAT_ID):
        try:
            kws = ("late", "មកយឺត", "off ", "day off", "ឈប់", "leave", "al ", "sick", "ឈឺ", "ច្បាប់")
            if any(k in text.lower() for k in kws) and msg.from_user:
                sender_staff = staff_get_by_uid(msg.from_user.id)
                key = (chat_id, msg.from_user.id)
                if (sender_staff and sender_staff.get("status") == "active"
                        and now - _redirect_last.get(key, 0) >= _REDIRECT_COOLDOWN):
                    _redirect_last[key] = now
                    call = sender_staff.get("call_name") or sender_staff["canonical_name"]
                    # reply to THEIR message + tag the SENDER by uid (never the named person → no
                    # misspelling risk), with a different wording each time (zero-API rotation).
                    await context.bot.send_message(
                        chat_id,
                        "%s %s" % (_staff_mention(call, msg.from_user.id),
                                   random.choice(_GROUP_REDIRECT_LINES)),
                        reply_to_message_id=msg.message_id, parse_mode="HTML")
        except Exception as e:
            logger.error("group redirect failed: %s", e)

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
                    await _maybe_flag_sales_anomaly(context, full)
                    # a re-posted CORRECT report closes the open math case + gets thanked
                    await _resolve_report_math_if_fixed(context, chat_id, full, msg, "new report")
                    # level-1 reconciliation: on the FINAL, compare photos vs the typed numbers
                    if full["report_kind"] == "final":
                        await _send_reconciliation(context, full["business_day"])
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
    from shared.error_handler import make_error_handler
    app.add_error_handler(make_error_handler("GM"))   # nothing dies silently (the gm_save_concern lesson)

    # Restore the test-mode process flag from the DB so a restart can't silently flip
    # att_test_on() to False while attendance_test_mode='true' (which would make TEST mode show
    # real rows instead of the is_test sandbox). The DB is the source of truth across restarts.
    try:
        set_att_test(gm_get_state("attendance_test_mode") == "true")
    except Exception as e:
        logger.error("test-mode flag restore failed: %s", e)

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
    app.add_handler(CommandHandler("exstaff",   cmd_exstaff))
    app.add_handler(CommandHandler("vendor",    cmd_vendor))
    app.add_handler(CommandHandler("rollcall",  cmd_rollcall))
    app.add_handler(CommandHandler("payroll",   cmd_payroll))
    app.add_handler(CommandHandler("testmode",   cmd_testmode))
    app.add_handler(CommandHandler("testclock",  cmd_testclock))
    app.add_handler(CommandHandler("testrun",    cmd_testrun))
    app.add_handler(CommandHandler("testkhmer",  cmd_testkhmer))
    app.add_handler(CommandHandler("testreset",  cmd_testreset))
    app.add_handler(CommandHandler("teststatus", cmd_teststatus))
    app.add_handler(CommandHandler("testseed",   cmd_testseed))
    app.add_handler(CommandHandler("holiday",     cmd_holiday))
    app.add_handler(CommandHandler("pb",          cmd_pb))
    app.add_handler(CommandHandler("audit",       cmd_audit))
    app.add_handler(CommandHandler("menu",        cmd_menu))
    app.add_handler(CommandHandler("joined",      cmd_joined))
    app.add_handler(CallbackQueryHandler(_owner_menu_callback, pattern=r"^own:"))
    app.add_handler(CommandHandler("commands",    cmd_commands))
    app.add_handler(CommandHandler("help",        cmd_commands))
    app.add_handler(CallbackQueryHandler(staff_button_callback, pattern=r"^ss:"))
    app.add_handler(CallbackQueryHandler(exstaff_callback, pattern=r"^exstaff:"))
    from gm_bot import rollcall
    app.add_handler(CallbackQueryHandler(rollcall.bind_callback, pattern=r"^bind:"))
    # attendance role-play shell — OWNER ONLY, test mode (no staff interaction at all)
    from gm_bot import attendance_ui
    app.add_handler(CommandHandler("test", attendance_ui.cmd_test))
    app.add_handler(CallbackQueryHandler(_payback_callback, pattern=r"^att:pb:"))
    app.add_handler(CallbackQueryHandler(_sick_family_nudge_callback, pattern=r"^att:sfam:"))
    app.add_handler(CallbackQueryHandler(_al_approval_callback, pattern=r"^att:alapp:"))
    app.add_handler(CallbackQueryHandler(_al_coverage_toggle, pattern=r"^att:alcov:"))
    app.add_handler(CallbackQueryHandler(_swap_partner_callback, pattern=r"^att:swp:"))
    app.add_handler(CallbackQueryHandler(_swap_senior_callback, pattern=r"^att:swps:"))
    app.add_handler(CallbackQueryHandler(_swap_coverage_toggle, pattern=r"^att:swcov:"))
    app.add_handler(CallbackQueryHandler(_ot_buyback_callback, pattern=r"^att:otb:"))
    app.add_handler(CallbackQueryHandler(_sc_cov_callback, pattern=r"^att:sccov:"))
    app.add_handler(CallbackQueryHandler(_shift_change_callback, pattern=r"^att:sc:"))
    app.add_handler(CallbackQueryHandler(_sick_paper_callback, pattern=r"^att:sp:(cov|duty|come|rest):"))
    app.add_handler(CallbackQueryHandler(_sick_return_callback, pattern=r"^att:sret:"))
    app.add_handler(CallbackQueryHandler(_death_upgrade_callback, pattern=r"^att:dth:"))
    app.add_handler(CallbackQueryHandler(_att_go_callback, pattern=r"^att:go"))  # att:go or att:go:{nonce}
    app.add_handler(CallbackQueryHandler(_late_simarr_callback, pattern=r"^att:simarr:"))
    app.add_handler(CallbackQueryHandler(_ci_simcheckout_callback, pattern=r"^att:cisco:"))
    # private photo from staff → reason capture / sick papers (gated); harmless otherwise
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.PHOTO, _private_photo_router))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.VOICE | filters.Sticker.ALL | filters.VIDEO_NOTE
                                    | filters.VIDEO | filters.AUDIO | filters.ANIMATION),  # A7: widen
        _private_voice_router))
    app.add_handler(CallbackQueryHandler(attendance_ui.callback, pattern=r"^att:"))
    # private location router: real staff check-in first (gated by attendance_live),
    # else the owner-only test handler (pin template + geofence readout)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.LOCATION, _private_location_router))
    # per-minute check-in scheduler (gated; inert until attendance_live='true')
    app.job_queue.run_repeating(_checkin_scheduler_job, interval=60, first=30,
                                name="gm_checkin_scheduler")
    # payback ignore-ladder: daily 07:10 PP (00:10 UTC), gated
    app.job_queue.run_daily(_payback_ladder_job,
                            time=__import__("datetime").time(hour=0, minute=10),
                            name="gm_payback_ladder")
    # 12h-before booking reminders: hourly, gated
    app.job_queue.run_repeating(_booking_reminder_job, interval=3600, first=120,
                                name="gm_booking_reminder")
    # paperless-sick papers deadline: daily 07:20 PP (00:20 UTC), gated
    app.job_queue.run_daily(_sick_papers_deadline_job,
                            time=__import__("datetime").time(hour=0, minute=20),
                            name="gm_sick_papers_deadline")
    # no-show sweep: daily 08:00 PP (01:00 UTC), gated
    app.job_queue.run_daily(_no_show_sweep_job,
                            time=__import__("datetime").time(hour=1, minute=0),
                            name="gm_no_show_sweep")
    # weekly call-outs: daily 08:30 PP (01:30 UTC), job fires Mondays only, gated
    app.job_queue.run_daily(_callout_job,
                            time=__import__("datetime").time(hour=1, minute=30),
                            name="gm_callout")
    # new-hire join-month proration restore: daily 07:05 PP (00:05 UTC), real clock, ungated
    app.job_queue.run_daily(_pay_restore_job,
                            time=__import__("datetime").time(hour=0, minute=5),
                            name="gm_pay_restore")
    # daily auto-audit: 07:30 PP (00:30 UTC), REAL rows, silent when clean, owner DM on problems
    app.job_queue.run_daily(_auto_audit_job,
                            time=__import__("datetime").time(hour=0, minute=30),
                            name="gm_auto_audit")
    # bounded reason-nudge ladder (10/20/30): every 5 min, gated
    app.job_queue.run_repeating(_reason_nudge_job, interval=300, first=90,
                                name="gm_reason_nudge")
    app.add_handler(teach_conv)
    # Paperless /stock entry (owner-only test mode) — conversation, registered before
    # the loose private-text handler so count entry isn't intercepted.
    from gm_bot.stock_entry import build_stock_conversation
    app.add_handler(build_stock_conversation())
    # A known staff member leaving an internal group -> ask the owner if they left.
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, _left_member_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, _new_member_handler))
    # Owner DMs GM in plain language that someone left (silent unless it's a departure).
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, _private_text_router))
    # edited REPORT messages (staff fix reports by editing) — must come BEFORE the
    # generic group handler so the edit isn't swallowed and dropped
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.UpdateType.EDITED_MESSAGE, _edited_group_handler))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, _live_group_handler))
    # CATCH-ALL for buttons NO handler recognises — MUST be the LAST handler registered (same
    # group 0: only unmatched taps fall through to it; conversations register their own callback
    # handlers above). Collapses orphaned/legacy messages into an honest expired note (EN+KH)
    # and records the tap for the daily auto-audit (owner, Jun 11).
    app.add_handler(CallbackQueryHandler(_expired_button_callback))

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
    # Planned-AL deduction: 07:05 PP (00:05 UTC) — take passed AL days off balances.
    app.job_queue.run_daily(
        _al_deduction_job,
        time=__import__("datetime").time(hour=0, minute=5),
        name="gm_al_deduction",
    )
    # Monthly AL accrual: runs daily 07:15 PP (00:15 UTC), credits only on the 1st.
    app.job_queue.run_daily(
        _al_accrual_job,
        time=__import__("datetime").time(hour=0, minute=15),
        name="gm_al_accrual",
    )
    # Report existence watchdog (session 28): mid by 17:30 PP (10:30 UTC),
    # final for the just-closed day by 06:30 PP (23:30 UTC).
    app.job_queue.run_daily(
        _missing_mid_report_job,
        time=__import__("datetime").time(hour=10, minute=30),
        name="gm_missing_mid_report",
    )
    app.job_queue.run_daily(
        _missing_final_report_job,
        time=__import__("datetime").time(hour=23, minute=30),
        name="gm_missing_final_report",
    )
    # Daily stock order list: 07:00 Phnom Penh = 00:00 UTC.
    app.job_queue.run_daily(
        _stock_order_job,
        time=__import__("datetime").time(hour=0, minute=0),
        name="gm_stock_order",
    )

    return app
