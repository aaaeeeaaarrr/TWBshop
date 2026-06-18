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
                           get_receipt_lines, save_receipt_lines, set_payment, to_usd_cents,
                           vendor_by_group, vendor_by_name, vendor_link)
from shared.ai_client import extract_receipt

try:
    from config import OWNER_TELEGRAM_ID
except Exception:
    OWNER_TELEGRAM_ID = 0

EXPENSE_GROUP_ID = -5417163768   # "Expenses TWB" — the one internal capture group
LISTENER_ACTOR = 1271537077      # the shop/listener account (Café Wine O'clock / TheWineBakery24PP)
CARD_ACTORS = {OWNER_TELEGRAM_ID, LISTENER_ACTOR}  # who may capture + tap cards (Tyty only observes)

logger = logging.getLogger(__name__)


def _allowed(update):
    """Who may capture / act: the OWNER in a private DM; OWNER + the listener/shop account in the
    Expenses group. Everyone else (incl. Tyty, who observes) is ignored; other groups are ignored."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return False
    if chat.type == "private":
        return user.id == OWNER_TELEGRAM_ID
    if chat.id == EXPENSE_GROUP_ID:
        return user.id in CARD_ACTORS
    return False


def _kb(r):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for (label, data) in row]
         for row in capture.card_buttons(r)])


async def _send_card(update, rid):
    r = get_receipt(rid)
    r["lines"] = get_receipt_lines(rid)
    items_sum = sum(li["line_total_cents"] for li in r["lines"]
                    if li.get("line_total_cents") is not None)
    if r["lines"] and items_sum and r.get("amount_cents"):
        ok, msg = capture.math_check(items_sum + (r.get("tax_cents") or 0), r["amount_cents"])
        r["math_msg"] = msg if not ok else "✓ items add up"
    await update.effective_message.reply_text(capture.render_card(r), reply_markup=_kb(r))


async def cmd_start(update, context):
    if not _allowed(update):
        return
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
    """Receipt photo → one focused Sonnet read → numbered living card. Cash/ABA + ✏️ Fix from the card."""
    if not _allowed(update):
        return
    msg = update.effective_message
    photo = msg.photo[-1]
    raw = bytes(await (await photo.get_file()).download_as_bytearray())
    sha = hashlib.sha256(raw).hexdigest()
    try:
        rec = await extract_receipt(raw)
    except Exception:
        logger.exception("extract_receipt failed")
        return
    if not rec.get("is_receipt"):
        return  # POS screens / expense sheets / other are the report engine's job (P3)

    v = vendor_by_group(update.effective_chat.id)  # zero-read vendor if posted in a supplier group
    if not v:  # else learn from the printed name (vendor-learning lite): "SONG HENG" → "Song Heng Gas"
        v = vendor_by_name(rec.get("vendor"))
    total, cur = rec.get("total_amount"), (rec.get("total_currency") or "USD")
    cents = to_usd_cents(total, cur) if total is not None else None
    rid = add_receipt(
        vendor_id=(v["id"] if v else None),
        amount_cents=cents,
        orig_currency=cur,
        orig_amount=total,
        items_text=(rec.get("items_text") or None),
        is_handwritten=rec.get("is_handwritten", False),
        invoice_no=rec.get("invoice_no"),
        receipt_date=rec.get("date"),
        tax_cents=(to_usd_cents(rec["tax_amount"], cur) if rec.get("tax_amount") else None),
        supplier_account=rec.get("supplier_account"),
        bank_name=rec.get("bank_name"),
        photo_file_id=photo.file_id,
        photo_sha=sha,
        tg_chat_id=update.effective_chat.id,
        tg_msg_id=msg.message_id,
        captured_by=update.effective_user.id,
    )
    save_receipt_lines(rid, rec.get("line_items"), cur)
    await _send_card(update, rid)


async def on_callback(update, context):
    q = update.callback_query
    await q.answer()
    if not _allowed(update):
        return
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
    if not _allowed(update):
        return
    rid = context.user_data.pop("acc_fix", None)
    if not rid:
        return
    text = (update.message.text or "").strip()
    cents, currency, orig = capture.parse_amount_cents(text)
    if cents is None and text.replace(".", "", 1).isdigit():
        cents, currency, orig = int(round(float(text) * 100)), "USD", float(text)
    if cents is not None:
        edit_receipt(rid, amount_cents=cents, orig_currency=(currency or "USD"), orig_amount=orig)
    else:
        edit_receipt(rid, items_text=text)
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
