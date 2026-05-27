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
from shared.database import (
    gm_get_unsent_concerns, gm_mark_sent, gm_review_concern,
    gm_get_concern_by_msg_id, gm_save_rule, init_gm_db,
    gm_get_related_photos, gm_get_unsent_by_sender, gm_get_pending_by_sender,
    gm_get_unreviewed_by_sender, gm_get_unreviewed_by_sender_name,
)
from gm_bot.analyzer import run_analysis, analyze_live_message

logger = logging.getLogger(__name__)

TEACH_WAITING = 1  # ConversationHandler state


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
    sender = c.get("sender_name") or "Unknown"
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


# ─── Command handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return
    await update.message.reply_text(
        "GM Manager active.\n"
        "/check — run analysis, show new concerns by staff\n"
        "/review — resend concerns waiting for your button tap\n"
        "/staff — list pending concerns by staff member\n"
        "/staff <name> — send that person's concerns\n"
        "/rules — show learned rules"
    )


def _staff_list_keyboard(rows: list[dict], bot_data: dict) -> InlineKeyboardMarkup:
    bot_data["staff_index"] = {str(i): r["sender_name"] for i, r in enumerate(rows)}
    buttons = []
    for i, r in enumerate(rows):
        name = r["sender_name"] or "Unknown"
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
            lines.append("• %s — %s" % (r["sender_name"] or "Unknown", ", ".join(parts)))
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
            lines.append("• %s (%d concerns)" % (r["sender_name"], r["count"]))
        await update.message.reply_text("\n".join(lines))
        return

    if not concerns:
        await update.message.reply_text("No pending concerns matching '%s'." % query)
        return

    sender_display = concerns[0]["sender_name"]
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
        context.user_data["teaching_msg_text"] = query.message.text
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "📚 What should I know about this concern?\n"
            "Reply with your explanation. I'll remember it for similar cases.\n\n"
            "(Send /cancel to skip)"
        )
        return TEACH_WAITING

    return ConversationHandler.END


async def teach_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != config.OWNER_TELEGRAM_ID:
        return ConversationHandler.END

    note = update.message.text.strip()
    concern_id = context.user_data.get("teaching_concern_id")

    if concern_id:
        gm_review_concern(concern_id, "teach", teaching_note=note)
        concern = gm_get_concern_by_msg_id(None)  # we have the id already

        # Save as a rule — use first 60 chars of note as the pattern
        pattern = note[:60]
        from shared.database import _db
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT concern_type FROM gm_concerns WHERE id = %s", (concern_id,))
                row = cur.fetchone()
                ctype = row["concern_type"] if row else None

        gm_save_rule(
            concern_type=ctype,
            pattern=pattern,
            action="ignore",
            note=note,
        )
        await update.message.reply_text("✓ Got it. I'll remember this for future concerns of this type.")

    context.user_data.pop("teaching_concern_id", None)
    return ConversationHandler.END


async def teach_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("teaching_concern_id", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


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
    logger.info("Group msg: chat_id=%s title=%r sender=%s", chat_id, msg.chat.title, sender)

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

    concerns = analyze_live_message(chat_id, msg_id, sender, text)
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


# ─── Application builder ──────────────────────────────────────────────────────

def build_app() -> Application:
    if not config.GM_BOT_TOKEN:
        raise ValueError("GM_BOT_TOKEN not set in config/secrets")

    app = Application.builder().token(config.GM_BOT_TOKEN).build()

    # ConversationHandler wraps the teach flow
    teach_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern=r"^gm:")],
        states={TEACH_WAITING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, teach_receive),
            CommandHandler("cancel", teach_cancel),
        ]},
        fallbacks=[CommandHandler("cancel", teach_cancel)],
        per_message=False,
        per_chat=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("review", cmd_review))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("staff", cmd_staff))
    app.add_handler(CommandHandler("rules", cmd_rules))
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

    return app
