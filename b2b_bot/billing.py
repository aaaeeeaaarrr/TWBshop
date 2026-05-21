"""B2B billing — payment tracking, reminders, and owner approval flow."""

import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

import config
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.pricing import item_price
from shared.ai_client import read_payment_amount
from shared.database import (
    get_unpaid_b2b_orders,
    get_unpaid_b2b_cake_orders,
    get_groups_with_unpaid_orders,
    get_groups_with_unpaid_on_date,
    mark_b2b_orders_paid,
    mark_b2b_cake_orders_paid,
    save_b2b_payment,
    get_b2b_payment,
    update_b2b_payment_status,
)

logger = logging.getLogger(__name__)

# Pending payment photos: {group_chat_id: {"file_id": str}}
_pending_payment_photo: dict[int, dict] = {}


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

async def handle_payment_photo(update: Update, context) -> None:
    """Catch any photo in a B2B group and ask if it's a payment receipt."""
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    msg = update.message
    if not msg.photo:
        return

    _pending_payment_photo[chat_id] = {"file_id": msg.photo[-1].file_id}

    await msg.reply_text(
        "Is this a payment receipt?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Yes ✓", callback_data=f"b2b_pay_yes:{chat_id}"),
            InlineKeyboardButton("No",    callback_data=f"b2b_pay_no:{chat_id}"),
        ]]),
    )


async def handle_payment_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Customer group: Yes this is a payment receipt ─────────────────────────
    if data.startswith("b2b_pay_yes:"):
        group_chat_id = int(data.split(":", 1)[1])
        pending = _pending_payment_photo.pop(group_chat_id, None)
        if not pending:
            await query.edit_message_text("Receipt already processed.")
            return

        await query.edit_message_text("Received — forwarding to the team for verification.")

        photo_file = await context.bot.get_file(pending["file_id"])
        image_bytes = bytes(await photo_file.download_as_bytearray())

        os.makedirs(config.PHOTO_STORAGE_DIR, exist_ok=True)
        filename = f"payment_{group_chat_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = os.path.join(config.PHOTO_STORAGE_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(image_bytes)

        ai_result  = await read_payment_amount(image_bytes)
        amount     = ai_result.get("amount") or 0.0
        balance    = get_unpaid_total(group_chat_id)
        business   = get_business_name(group_chat_id)

        payment_id = save_b2b_payment(group_chat_id, business, amount, file_path)

        amount_str  = f"${amount:.2f}" if amount else "unclear — check screenshot"
        balance_str = f"${balance:.2f}"
        caption = (
            f"Payment receipt — {business}\n\n"
            f"Amount detected: {amount_str}\n"
            f"Outstanding balance: {balance_str}"
        )
        if not amount:
            caption += "\n\nAmount could not be read automatically. Verify against your bank before approving."

        if not config.OWNER_TELEGRAM_ID:
            logger.warning("OWNER_TELEGRAM_ID not set — payment receipt not forwarded")
            return

        await context.bot.send_photo(
            chat_id=config.OWNER_TELEGRAM_ID,
            photo=pending["file_id"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Approve ✓", callback_data=f"b2b_pay_approve:{payment_id}"),
                InlineKeyboardButton("Reject ✗",  callback_data=f"b2b_pay_reject:{payment_id}"),
            ]]),
        )

    # ── Customer group: No, not a payment receipt ─────────────────────────────
    elif data.startswith("b2b_pay_no:"):
        group_chat_id = int(data.split(":", 1)[1])
        _pending_payment_photo.pop(group_chat_id, None)
        await query.edit_message_text("Got it, ignored.")

    # ── Owner private chat: Approve payment ───────────────────────────────────
    elif data.startswith("b2b_pay_approve:"):
        payment_id = int(data.split(":", 1)[1])
        payment = get_b2b_payment(payment_id)

        if not payment or payment["status"] != "pending":
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\nAlready processed."
            )
            return

        group_chat_id = payment["group_chat_id"]
        amount = payment["amount"]

        if amount <= 0:
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\n✗ Cannot apply — amount was not detected. Handle manually."
            )
            update_b2b_payment_status(payment_id, "manual")
            return

        result = apply_payment(group_chat_id, amount)
        update_b2b_payment_status(payment_id, "approved")

        # Notify owner with breakdown
        if result["paid_dates"]:
            dates_str = ", ".join(result["paid_dates"])
            owner_note = (
                f"\n\n✓ APPROVED\n"
                f"Applied: ${result['applied']:.2f} to {result['paid_count']} order row(s)\n"
                f"Dates covered: {dates_str}\n"
                f"Remaining balance: ${result['remaining']:.2f}"
            )
        else:
            owner_note = (
                f"\n\n✓ APPROVED — but payment of ${amount:.2f} doesn't cover "
                f"any full delivery date (oldest date total exceeds this amount).\n"
                f"Remaining balance: ${result['remaining']:.2f}\n"
                "Check with customer."
            )

        await query.edit_message_caption(caption=(query.message.caption or "") + owner_note)

        # Notify customer group
        if result["remaining"] <= 0:
            cust_msg = f"Payment of ${amount:.2f} confirmed. Your balance is now $0. Thank you!"
        else:
            cust_msg = (
                f"Payment of ${amount:.2f} confirmed. Thank you!\n"
                f"Remaining balance: ${result['remaining']:.2f}"
            )
        await context.bot.send_message(group_chat_id, cust_msg)

    # ── Owner private chat: Reject payment ────────────────────────────────────
    elif data.startswith("b2b_pay_reject:"):
        payment_id = int(data.split(":", 1)[1])
        payment = get_b2b_payment(payment_id)

        if not payment or payment["status"] != "pending":
            await query.edit_message_caption(
                caption=(query.message.caption or "") + "\n\nAlready processed."
            )
            return

        update_b2b_payment_status(payment_id, "rejected")
        await query.edit_message_caption(caption=(query.message.caption or "") + "\n\n✗ REJECTED")
        await context.bot.send_message(
            payment["group_chat_id"],
            "Payment receipt could not be verified. Please contact us directly.",
        )
