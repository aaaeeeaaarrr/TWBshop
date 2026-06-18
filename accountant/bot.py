"""accountant/bot.py — the Telegram shell for the accountant (P1 capture).

A thin layer over the pure logic (accountant/capture.py) + the DB (accountant/db.py):
receipt photo → assess_receipt_photo → numbered living card → confirm / cash|ABA / ✏️ Fix.
Payment matching + the owner→supplier slip relay are P2 (not here).

NOT real-path-tested yet — gated on ACCOUNTANT_BOT_TOKEN (owner creates the bot via @BotFather).
The pure logic + DB lifecycle it calls ARE proven (tests/test_accountant_capture.py).
"""
import hashlib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

from accountant import capture
from accountant.db import (add_receipt, confirm_receipt, edit_receipt, get_receipt,
                           set_payment, vendor_by_group, vendor_link)
from shared.ai_client import assess_receipt_photo

try:
    from config import OWNER_TELEGRAM_ID
except Exception:
    OWNER_TELEGRAM_ID = 0

logger = logging.getLogger(__name__)


def _kb(r):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for (label, data) in row]
         for row in capture.card_buttons(r)])


async def _send_card(update, rid):
    r = get_receipt(rid)
    await update.effective_message.reply_text(capture.render_card(r), reply_markup=_kb(r))


async def cmd_start(update, context):
    await update.message.reply_text(
        "🧾 Accountant — send a receipt photo here (or in the Expense group) and I'll log it as a "
        "numbered receipt.\nOwner: run /vendor link <name> inside a supplier group to map it.")


async def cmd_vendor(update, context):
    """/vendor link <name> — owner, INSIDE a supplier group → map group→vendor (the paid-signal)."""
    if update.effective_user.id != OWNER_TELEGRAM_ID:
        return
    args = context.args or []
    if len(args) >= 2 and args[0] == "link":
        name = " ".join(args[1:])
        vid = vendor_link(name, update.effective_chat.id)
        await update.message.reply_text(f"✅ Linked this group → {name} (vendor #{vid}).")
    else:
        await update.message.reply_text("Usage: /vendor link <name>  (run inside the supplier group)")


async def on_photo(update, context):
    """Receipt photo → 1 Haiku assess → numbered living card. Cash/ABA + ✏️ Fix from the card."""
    msg = update.effective_message
    photo = msg.photo[-1]
    raw = bytes(await (await photo.get_file()).download_as_bytearray())
    sha = hashlib.sha256(raw).hexdigest()
    try:
        assess = await assess_receipt_photo(raw)
    except Exception:
        logger.exception("assess_receipt_photo failed")
        return
    if capture.route(assess) != "receipt":
        return  # expense sheets / POS screens / other are the report engine's job (P3)

    v = vendor_by_group(update.effective_chat.id)  # zero-read vendor if posted in a supplier group
    rid = add_receipt(
        vendor_id=(v["id"] if v else None),
        amount_cents=capture.parse_amount_cents(assess.get("readable_partial")),
        items_text=((assess.get("readable_partial") or "")[:300] or None),
        is_handwritten=assess.get("is_handwritten", False),
        photo_file_id=photo.file_id,
        photo_sha=sha,
        tg_chat_id=update.effective_chat.id,
        tg_msg_id=msg.message_id,
        captured_by=update.effective_user.id,
    )
    await _send_card(update, rid)


async def on_callback(update, context):
    q = update.callback_query
    await q.answer()
    parts = (q.data or "").split(":")
    if len(parts) != 3:
        return
    _, action, sid = parts
    try:
        rid = int(sid)
    except ValueError:
        return
    if action == "ok":
        confirm_receipt(rid)
    elif action == "cash":
        set_payment(rid, "cash")
    elif action == "aba":
        set_payment(rid, "aba")
    elif action == "fix":
        context.user_data["acc_fix"] = rid
        await q.message.reply_text("✏️ Send the correction — a number = the total, otherwise a note.")
        return
    r = get_receipt(rid)
    await q.edit_message_text(capture.render_card(r), reply_markup=_kb(r))


async def on_text(update, context):
    """A ✏️ Fix reply: a number updates the total, anything else updates the item note."""
    rid = context.user_data.pop("acc_fix", None)
    if not rid:
        return
    text = (update.message.text or "").strip()
    cents = capture.parse_amount_cents(text)
    if cents is None and text.replace(".", "", 1).isdigit():
        cents = int(round(float(text) * 100))
    edit_receipt(rid, amount_cents=cents) if cents is not None else edit_receipt(rid, items_text=text)
    await _send_card(update, rid)


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    from shared.error_handler import make_error_handler
    app.add_error_handler(make_error_handler("Accountant"))   # crashes are never silent
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("vendor", cmd_vendor))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^acc:"))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, on_text))
    return app
