"""adapters.telegram_onboarding — the Telegram adapter for DISCOVER-CONFIRM staff onboarding
(core/onboarding_flow.py).

Wired onto a TENANT's bot: anyone who posts in the designated staff group gets STAGED automatically; the
owner runs /onboard and confirms each discovered person into a staff record (or skips) via inline buttons —
one tap, no typing. Channel-specific → lives in adapters/, never core/ (core stays channel-free). The
handlers are bound to (org_id, staff_chat_id) by make_handlers, so they're pure + testable with mocks.
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

from core.onboarding_flow import (record_seen_member, list_candidates, confirm_candidate, skip_candidate,
                                  record_group, group_id_for_role)

logger = logging.getLogger("onboard")


def _candidate_card(c: dict):
    """(text, keyboard) for one discovered candidate — Add / Not-staff buttons carry their telegram id."""
    who = c.get("tg_name") or "Unknown"
    uname = (" @" + c["tg_username"]) if c.get("tg_username") else ""
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ Add as staff", callback_data="onb:ok:%d" % c["tg_user_id"]),
        InlineKeyboardButton("✗ Not staff", callback_data="onb:skip:%d" % c["tg_user_id"]),
    ]])
    return "👤 Found: <b>%s</b>%s\nAdd them as staff?" % (who, uname), kb


def make_handlers(org_id: str):
    """Build the three bound handlers (group recorder + staff-group stager · /onboard · confirm callback).
    The STAFF group is whichever the owner tagged in the wizard (group_id_for_role) — so the bot discovers
    every group it's in, and only stages people from the one you marked as staff."""

    async def on_group_message(update, context):
        chat, u = update.effective_chat, update.effective_user
        if not chat or getattr(chat, "type", None) not in ("group", "supergroup"):
            return
        try:
            record_group(org_id, chat.id, getattr(chat, "title", None))           # discover the group
        except Exception:
            logger.exception("[ONBOARD] record_group failed (harmless)")
        if u and not u.is_bot and chat.id == group_id_for_role(org_id, "staff"):    # stage only from the staff group
            try:
                record_seen_member(org_id, u.id, u.full_name, u.username, chat_id=chat.id)
            except Exception:
                logger.exception("[ONBOARD] stage failed (harmless)")

    async def cmd_onboard(update, context):
        cands = list_candidates(org_id)
        if not cands:
            await update.effective_message.reply_text(
                "No new people to confirm yet. Make sure I'm added to your staff group and people have posted there.")
            return
        text, kb = _candidate_card(cands[0])
        await update.effective_message.reply_text("%d to review.\n\n%s" % (len(cands), text),
                                                  reply_markup=kb, parse_mode="HTML")

    async def on_callback(update, context):
        q = update.callback_query
        await q.answer()
        try:
            _, action, raw = q.data.split(":")
            uid = int(raw)
        except (ValueError, AttributeError):
            return
        if action == "ok":
            cand = next((c for c in list_candidates(org_id) if c["tg_user_id"] == uid), None)
            name = (cand or {}).get("tg_name") or "Staff"
            confirm_candidate(org_id, uid, name)
            await q.edit_message_text("✓ Added <b>%s</b>. Set their hours/skills in the wizard." % name,
                                     parse_mode="HTML")
        elif action == "skip":
            skip_candidate(org_id, uid)
            await q.edit_message_text("✗ Skipped.")
        rest = list_candidates(org_id)
        if rest:
            text, kb = _candidate_card(rest[0])
            await q.message.reply_text("Next (%d left):\n\n%s" % (len(rest), text), reply_markup=kb, parse_mode="HTML")
        else:
            await q.message.reply_text("✅ All done — everyone's been reviewed. Set hours/skills in the wizard.")

    return on_group_message, cmd_onboard, on_callback


def register(app, org_id: str) -> None:
    """Attach the discover-confirm handlers to a tenant's bot Application (the staff group comes from the
    wizard's group mapping, not a fixed id)."""
    on_msg, cmd, cb = make_handlers(org_id)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, on_msg), group=5)
    app.add_handler(CommandHandler("onboard", cmd))
    app.add_handler(CallbackQueryHandler(cb, pattern=r"^onb:"))
