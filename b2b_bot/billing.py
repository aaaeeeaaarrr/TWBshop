"""B2B billing — payment tracking and reminders."""

import logging
import os
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

        business = get_business_name(chat_id)
        balance_before = get_unpaid_total(chat_id)

        os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
        ext = "pdf" if is_pdf else "jpg"
        filename = f"payment_{chat_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{ext}"
        file_path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        save_b2b_payment(chat_id, business, amount, file_path, message_id)

        if amount > 0:
            res = apply_payment(chat_id, amount)
            if res["remaining"] <= 0:
                cust_msg = f"Thank you! Payment of ${amount:.2f} confirmed. Your balance is now $0. ✓"
            else:
                cust_msg = f"Thank you! Payment of ${amount:.2f} confirmed. ✓\n<b>Remaining balance: ${res['remaining']:.2f}</b>"
            owner_detail = (f"Dates covered: {', '.join(res['paid_dates'])}\n<b>Remaining: ${res['remaining']:.2f}</b>"
                            if res["paid_dates"] else f"Doesn't cover any full delivery date.\n<b>Balance: ${res['remaining']:.2f}</b>")
            caption = f"Payment — {business}\n\nAmount: ${amount:.2f}\nBalance before: ${balance_before:.2f}\n{owner_detail}"
        else:
            cust_msg = "Thank you! Payment received — we'll update your balance shortly."
            caption = f"Payment — {business}\n\nAmount: unclear — check manually\n<b>Outstanding: ${balance_before:.2f}</b>"

        await bot.send_message(chat_id, cust_msg, reply_to_message_id=message_id, parse_mode=ParseMode.HTML)
        if config.OWNER_TELEGRAM_ID:
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


