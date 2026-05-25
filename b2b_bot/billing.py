"""B2B billing — payment tracking and reminders."""

import logging
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode

import config
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.pricing import item_price
from shared.ai_client import read_payment_amount, read_payment_amount_pdf, classify_b2b_image
from shared.database import (
    get_unpaid_b2b_orders,
    get_unpaid_b2b_cake_orders,
    get_groups_with_unpaid_orders,
    get_groups_with_unpaid_on_date,
    mark_b2b_orders_paid,
    mark_b2b_cake_orders_paid,
    save_b2b_payment,
    get_valid_payment_accounts,
    save_pending_verification,
    get_pending_verifications,
    get_pending_verification,
    set_verification_owner_msg,
    set_verification_status,
    save_wrong_account_alert,
    get_pending_wrong_account_alerts,
    set_wrong_alert_owner_msg,
    set_wrong_alert_seen,
)

logger = logging.getLogger(__name__)


# ─── Balance helpers ──────────────────────────────────────────────────────────

def _unpaid_rows_with_price(group_chat_id: int) -> list[dict]:
    """Return all unpaid order rows (bread + cake) sorted oldest delivery first."""
    rows = []

    for r in get_unpaid_b2b_orders(group_chat_id):
        it = {"item": r["item"], "qty": r["quantity"], "grams": r["grams"]}
        rows.append({
            "source": "bread", "id": r["id"],
            "delivery_date": r["delivery_date"], "created_at": r["created_at"],
            "item": r["item"], "price": item_price(it),
        })

    for r in get_unpaid_b2b_cake_orders(group_chat_id):
        it = {
            "item": r["item"], "qty": r["quantity"],
            "order_type": r["order_type"], "slices": r["slices"],
        }
        rows.append({
            "source": "cake", "id": r["id"],
            "delivery_date": r["delivery_date"], "created_at": r["created_at"],
            "item": r["item"], "price": item_price(it),
        })

    return sorted(rows, key=lambda r: (r["delivery_date"], r["created_at"]))


def get_unpaid_total(group_chat_id: int) -> float:
    return round(sum(r["price"] for r in _unpaid_rows_with_price(group_chat_id)), 2)


def _unpaid_by_date(group_chat_id: int) -> dict[str, dict]:
    """Group unpaid rows by delivery_date: {date: {rows, total}}."""
    by_date: dict[str, dict] = defaultdict(lambda: {"rows": [], "total": 0.0})
    for row in _unpaid_rows_with_price(group_chat_id):
        d = row["delivery_date"]
        by_date[d]["rows"].append(row)
        by_date[d]["total"] = round(by_date[d]["total"] + row["price"], 2)
    return by_date


# ─── Apply payment (oldest delivery date first) ───────────────────────────────

def apply_payment(group_chat_id: int, amount: float) -> dict:
    """Mark oldest delivery dates as paid until amount runs out.

    Returns:
        applied       — amount actually applied to orders
        remaining     — outstanding balance after payment
        paid_dates    — delivery dates fully covered
        paid_count    — number of order rows marked paid
    """
    by_date = _unpaid_by_date(group_chat_id)
    remaining = round(amount, 2)
    paid_dates: list[str] = []
    bread_ids: list[int] = []
    cake_ids:  list[int] = []

    for delivery_date in sorted(by_date.keys()):
        day = by_date[delivery_date]
        if remaining >= day["total"]:
            remaining = round(remaining - day["total"], 2)
            paid_dates.append(delivery_date)
            for row in day["rows"]:
                (bread_ids if row["source"] == "bread" else cake_ids).append(row["id"])
        else:
            break  # can't cover this date's full total

    if bread_ids:
        mark_b2b_orders_paid(bread_ids)
    if cake_ids:
        mark_b2b_cake_orders_paid(cake_ids)

    new_balance = get_unpaid_total(group_chat_id)

    return {
        "applied":     round(amount - remaining, 2),
        "remaining":   new_balance,
        "paid_dates":  paid_dates,
        "paid_count":  len(bread_ids) + len(cake_ids),
    }


# ─── Outstanding balance summary (for /balance command) ───────────────────────

def get_all_outstanding_summary() -> list[str]:
    groups = get_groups_with_unpaid_orders()
    if not groups:
        return []
    lines = ["B2B OUTSTANDING BALANCES", ""]
    for row in groups:
        total = get_unpaid_total(row["group_chat_id"])
        lines.append(f"  {row['business_name']}: ${total:.2f}")
    return lines


# ─── Scheduled reminders ──────────────────────────────────────────────────────

async def send_daily_reminders(bot) -> None:
    """6am PNH reminder about yesterday's deliveries that are unpaid.

    Job fires at 23:00 UTC; at that moment date.today() UTC == yesterday in PNH.
    """
    today_utc = date.today().isoformat()
    groups = get_groups_with_unpaid_on_date(today_utc)

    for row in groups:
        group_chat_id = row["group_chat_id"]
        total = get_unpaid_total(group_chat_id)
        if total <= 0:
            continue
        try:
            await bot.send_message(
                group_chat_id,
                f"Hi {row['business_name']}! A reminder that yesterday's delivery "
                f"has an outstanding balance of ${total:.2f}.\n"
                "Please send payment when ready and attach a screenshot. Thank you!",
            )
        except Exception as exc:
            logger.error("Daily reminder failed for %s: %s", row["business_name"], exc)


async def send_weekly_reminders(bot) -> None:
    """Monday 6am PNH — accumulated outstanding balance for all customers."""
    groups = get_groups_with_unpaid_orders()

    for row in groups:
        group_chat_id = row["group_chat_id"]
        total = get_unpaid_total(group_chat_id)
        if total <= 0:
            continue
        try:
            await bot.send_message(
                group_chat_id,
                f"Hi {row['business_name']}! Weekly balance reminder — "
                f"your total outstanding is ${total:.2f}.\n"
                "Please send payment when you can and share a screenshot. Thank you!",
            )
        except Exception as exc:
            logger.error("Weekly reminder failed for %s: %s", row["business_name"], exc)


# ─── Payment helpers ─────────────────────────────────────────────────────────

def _build_cust_confirmation(chat_id: int, amount: float) -> str:
    remaining = get_unpaid_total(chat_id)
    if remaining <= 0:
        return f"Thank you! Payment of ${amount:.2f} confirmed. ✓\n<b>Remaining balance: $0.00</b>"
    return f"Thank you! Payment of ${amount:.2f} confirmed. ✓\n<b>Remaining balance: ${remaining:.2f}</b>"


def _verification_keyboard(verification_id: int):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Received", callback_data=f"b2b_pay_received_{verification_id}"),
        InlineKeyboardButton("❌ Not Received", callback_data=f"b2b_pay_notreceived_{verification_id}"),
    ]])


async def _send_owner_nudge(bot, verification_id: int | None, business: str, amount: float, chat_id: int):
    if not config.OWNER_TELEGRAM_ID:
        return None
    amount_str = f"${amount:.2f}" if amount else "amount unclear"
    text = f"💳 Payment verification needed\n{business} — {amount_str}\nDid you receive this?"
    kb = _verification_keyboard(verification_id) if verification_id else None
    try:
        return await bot.send_message(config.OWNER_TELEGRAM_ID, text, reply_markup=kb)
    except Exception as e:
        logger.error("Failed to send owner nudge: %s", e)
        return None


async def run_verification_nudge_tick(bot) -> None:
    """Hourly — re-nudge owner for any still-pending payment verifications."""
    for rec in get_pending_verifications():
        if rec["owner_msg_id"]:
            try:
                await bot.delete_message(config.OWNER_TELEGRAM_ID, rec["owner_msg_id"])
            except Exception:
                pass
        msg = await _send_owner_nudge(bot, rec["id"], rec["business_name"], rec["amount"], rec["group_chat_id"])
        if msg:
            set_verification_owner_msg(rec["id"], msg.message_id)


async def handle_payment_received(update, context) -> None:
    query = update.callback_query
    await query.answer()
    verification_id = int(query.data.split("_")[3])
    rec = get_pending_verification(verification_id)
    if not rec or rec["status"] != "pending":
        await query.edit_message_text("Already resolved.")
        return

    set_verification_status(verification_id, "received")

    # Apply payment and update balance if amount known
    if rec["amount"] > 0:
        save_b2b_payment(rec["group_chat_id"], rec["business_name"], rec["amount"], rec["file_path"] or "", rec["photo_msg_id"])
        cust_msg = _build_cust_confirmation(rec["group_chat_id"], rec["amount"])
    else:
        cust_msg = "Thank you! Payment confirmed. ✓\nWe'll update your balance shortly."

    # Edit the group "awaiting verification" message
    if rec["group_ack_msg_id"]:
        try:
            await context.bot.edit_message_text(
                cust_msg, chat_id=rec["group_chat_id"],
                message_id=rec["group_ack_msg_id"], parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(rec["group_chat_id"], cust_msg, parse_mode="HTML")

    await query.edit_message_text(f"✅ Marked received — {rec['business_name']} ${rec['amount']:.2f}")


async def handle_payment_not_received(update, context) -> None:
    query = update.callback_query
    await query.answer()
    verification_id = int(query.data.split("_")[3])
    rec = get_pending_verification(verification_id)
    if not rec or rec["status"] != "pending":
        await query.edit_message_text("Already resolved.")
        return

    set_verification_status(verification_id, "not_received")

    if rec["group_ack_msg_id"]:
        try:
            await context.bot.edit_message_text(
                "❌ Amount not received — please double-check and resend if needed.",
                chat_id=rec["group_chat_id"],
                message_id=rec["group_ack_msg_id"],
            )
        except Exception:
            pass

    await query.edit_message_text(f"❌ Marked not received — {rec['business_name']}")


async def _send_wrong_alert_nudge(bot, alert_id: int, business: str, amount: float, wrong_detail: str):
    if not config.OWNER_TELEGRAM_ID:
        return None
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    amount_str = f"${amount:.2f}" if amount else "amount unclear"
    text = f"⚠️ Wrong account payment — {business}\n{wrong_detail}\nAmount: {amount_str}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 Have you seen this?", callback_data=f"b2b_wrongseen_{alert_id}"),
    ]])
    try:
        return await bot.send_message(config.OWNER_TELEGRAM_ID, text, reply_markup=kb)
    except Exception as e:
        logger.error("Failed to send wrong alert nudge: %s", e)
        return None


async def run_wrong_alert_nudge_tick(bot) -> None:
    """Every 6 hours — re-nudge owner for unacknowledged wrong-account payments."""
    for alert in get_pending_wrong_account_alerts():
        if alert["owner_msg_id"]:
            try:
                await bot.delete_message(config.OWNER_TELEGRAM_ID, alert["owner_msg_id"])
            except Exception:
                pass
        msg = await _send_wrong_alert_nudge(bot, alert["id"], alert["business_name"], alert["amount"], alert["wrong_detail"] or "")
        if msg:
            set_wrong_alert_owner_msg(alert["id"], msg.message_id)


async def handle_wrong_alert_seen(update, context) -> None:
    query = update.callback_query
    await query.answer()
    alert_id = int(query.data.split("_")[2])
    set_wrong_alert_seen(alert_id)
    await query.edit_message_text(query.message.text + "\n\n✅ Acknowledged")


# ─── Payment photo flow ───────────────────────────────────────────────────────

async def _process_b2b_image(bot, chat_id: int, file_id: str, message_id: int, is_pdf: bool, mime_type: str) -> None:
    """Download, classify, and route a B2B group image automatically."""
    dl_file = await bot.get_file(file_id)
    file_bytes = bytes(await dl_file.download_as_bytearray())

    if is_pdf:
        # PDFs are always payment receipts
        result = {"type": "payment", "amount": None}
        ai_pay = await read_payment_amount_pdf(file_bytes)
        result["amount"] = ai_pay.get("amount") or 0.0
    else:
        result = await classify_b2b_image(file_bytes, mime_type)

    if result["type"] == "order":
        from b2b_bot.orders import handle_order_photo, _ai_items_to_orders
        items = result.get("items", [])
        await handle_order_photo(bot, chat_id, file_bytes, message_id, mime_type=mime_type, ai_items=items)

    elif result["type"] == "payment":
        amount = result.get("amount") or 0.0
        if not amount and not is_pdf:
            # Re-read for amount if classify didn't extract it
            ai_pay = await read_payment_amount(file_bytes)
            amount = ai_pay.get("amount") or 0.0

        # Validate destination account / seller name against DB-stored valid accounts
        to_account = result.get("to_account")
        seller     = result.get("seller")
        accounts   = get_valid_payment_accounts()
        valid_banks   = [re.sub(r"[\s\-]", "", a) for a in accounts["bank"]]
        valid_sellers = [s.lower().strip() for s in accounts["seller"]]

        wrong = False
        wrong_detail = ""
        if to_account and valid_banks:
            extracted = re.sub(r"[\s\-]", "", str(to_account))
            # suffix match handles partially visible numbers (***1234)
            if not any(v.endswith(extracted) or extracted.endswith(v) for v in valid_banks):
                wrong = True
                wrong_detail = f"Sent to account: {to_account}"
        elif seller and valid_sellers:
            if not any(seller.lower().strip() == s for s in valid_sellers):
                wrong = True
                wrong_detail = f"Seller shown: {seller}"

        business = get_business_name(chat_id)

        if wrong:
            acct_list = "\n".join(f"  • {a}" for a in accounts["bank"])
            cust_guide = f"Please send to:\n{acct_list}" if acct_list else "Please contact us for the correct account."
            await bot.send_message(
                chat_id,
                f"⚠️ This payment was sent to the wrong account.\n\n{cust_guide}",
                reply_to_message_id=message_id,
            )
            if config.SHOP_QR_PATH and os.path.exists(config.SHOP_QR_PATH):
                with open(config.SHOP_QR_PATH, "rb") as qr_file:
                    await bot.send_photo(chat_id, qr_file)
            alert_id = save_wrong_account_alert(None, business, amount, wrong_detail)
            msg = await _send_wrong_alert_nudge(bot, alert_id, business, amount, wrong_detail)
            if msg:
                set_wrong_alert_owner_msg(alert_id, msg.message_id)
            return

        # Can't verify (no account/seller visible) — manual owner confirmation
        if not to_account and not seller and (valid_banks or valid_sellers):
            os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
            ext = "pdf" if is_pdf else "jpg"
            filename = f"payment_{chat_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{ext}"
            file_path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            ack_msg = await bot.send_message(
                chat_id,
                "Thanks! Payment received — awaiting verification.",
                reply_to_message_id=message_id,
            )
            # Save first to get the ID, then send nudge with proper buttons
            verification_id = save_pending_verification(
                chat_id, message_id, ack_msg.message_id, None, amount, business, file_path,
            )
            owner_msg = await _send_owner_nudge(bot, verification_id, business, amount, chat_id)
            if owner_msg:
                set_verification_owner_msg(verification_id, owner_msg.message_id)
            return

        balance_before = get_unpaid_total(chat_id)

        os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
        ext = "pdf" if is_pdf else "jpg"
        filename = f"payment_{chat_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{ext}"
        file_path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        save_b2b_payment(chat_id, business, amount, file_path, message_id)
        cust_msg = _build_cust_confirmation(chat_id, amount)
        await bot.send_message(chat_id, cust_msg, reply_to_message_id=message_id, parse_mode=ParseMode.HTML)
        if config.OWNER_TELEGRAM_ID:
            balance_after = get_unpaid_total(chat_id)
            caption = f"Payment — {business}\n\nAmount: ${amount:.2f}\nBalance before: ${balance_before:.2f}\n<b>Remaining: ${balance_after:.2f}</b>"
            send = bot.send_document if is_pdf else bot.send_photo
            kwarg = "document" if is_pdf else "photo"
            await send(chat_id=config.OWNER_TELEGRAM_ID, caption=caption, parse_mode=ParseMode.HTML, **{kwarg: file_id})
    # type == "other": ignore silently


async def handle_payment_photo(update: Update, context) -> None:
    """Photo sent to a B2B group — AI classifies and routes automatically."""
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id) or not update.message.photo:
        return
    msg = update.message
    await _process_b2b_image(context.bot, chat_id, msg.photo[-1].file_id, msg.message_id, is_pdf=False, mime_type="image/jpeg")


async def handle_payment_document(update: Update, context) -> None:
    """Document (PDF or image file) sent to a B2B group — AI classifies and routes automatically."""
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return
    doc = update.message.document
    if not doc:
        return
    is_pdf = doc.mime_type == "application/pdf"
    is_image = (doc.mime_type or "").startswith("image/")
    if not is_pdf and not is_image:
        return
    mime = doc.mime_type if is_image else "image/jpeg"
    await _process_b2b_image(context.bot, chat_id, doc.file_id, update.message.message_id, is_pdf=is_pdf, mime_type=mime)


async def handle_payment_callback(update: Update, context) -> None:
    """No payment buttons anymore — kept for any stale messages still in chat."""
    await update.callback_query.answer("Already handled.")


