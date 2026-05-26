"""B2B recurring (Daily/Weekly) orders — day helpers, reminders, auto-skip."""

import json
import logging
from datetime import date, timedelta, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAY_SHORT  = {"mon": "Mon", "tue": "Tue", "wed": "Wed",
               "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
_DAY_FULL   = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
               "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}


def days_label(days: list[str]) -> str:
    """["fri","mon","wed"] → "Mon/Wed/Fri" (sorted by calendar order)."""
    return "/".join(_DAY_SHORT[d] for d in sorted(days, key=_DAY_ORDER.index))


def is_in_grace_period(created_at_iso: str, fulfillment_date: date) -> bool:
    """True when the recurring order was created ≤1 day before this fulfillment."""
    try:
        created = datetime.fromisoformat(created_at_iso).date()
    except Exception:
        return False
    return (fulfillment_date - created).days <= 1


async def send_recurring_reminders(bot, reminder_num: int) -> None:
    """Send recurring-order reminder messages. reminder_num: 1=7am, 2=1pm, 3=6pm."""
    from shared.database import (
        get_active_recurring_orders_for_date,
        get_or_create_recurring_confirmation,
        update_recurring_reminder_count,
        get_recurring_order,
    )

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    orders = get_active_recurring_orders_for_date(tomorrow)

    for rec in orders:
        if is_in_grace_period(rec["created_at"], date.fromisoformat(tomorrow)):
            continue

        conf = get_or_create_recurring_confirmation(rec["id"], tomorrow)
        if conf["status"] != "pending":
            continue
        if conf["reminder_sent"] != reminder_num - 1:
            continue

        items      = json.loads(rec["items_json"])
        days       = json.loads(rec["days_of_week"])
        bread_list = items.get("bread_items", [])
        cake_list  = items.get("cake_items", [])

        from b2b_bot.pricing import order_total, price_summary
        from shared.database import get_b2b_customer
        customer = get_b2b_customer(rec["group_chat_id"])
        delivery_cost = (
            float(customer["delivery_cost"])
            if customer and customer.get("delivery_cost") and rec["delivery_method"] == "delivery"
            else None
        )
        bread_priced = [{"item": it["item"], "qty": it["qty"], "grams": it.get("grams")} for it in bread_list]
        cake_priced  = [{"item": it["item"], "qty": it["qty"], "order_type": it.get("order_type"), "slices": it.get("slices")} for it in cake_list]
        total = order_total(bread_priced, cake_priced)

        method_label = "Delivery" if rec["delivery_method"] == "delivery" else "Pickup"
        lines = [
            f"📅 Recurring order — {days_label(days)}",
            f"🕐 {method_label} at {rec['delivery_time']}",
            "",
        ]
        for it in bread_list:
            line = f"  • {it['qty']}× {it['item']}"
            if it.get("grams"):
                line += f" — {it['grams']}g"
            if it.get("notes"):
                line += f" ({it['notes']})"
            lines.append(line)
        for it in cake_list:
            lines.append(f"  • {it['qty']}× {it['item']}")
        lines += ["", price_summary(total, delivery_cost), "", "Confirm for tomorrow?"]

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirm", callback_data=f"b2b_rec_confirm_{rec['id']}_{tomorrow}"),
            InlineKeyboardButton("⏭ Skip tomorrow", callback_data=f"b2b_rec_skip_{rec['id']}_{tomorrow}"),
        ]])

        try:
            await bot.send_message(rec["group_chat_id"], "\n".join(lines), reply_markup=kb)
            update_recurring_reminder_count(rec["id"], tomorrow, reminder_num)
        except Exception as e:
            logger.warning("Recurring reminder failed for group %s: %s", rec["group_chat_id"], e)


async def auto_skip_unconfirmed(bot) -> None:
    """Called at 10:10pm — skip any still-pending recurring instances for tomorrow."""
    from shared.database import get_pending_recurring_for_date, skip_recurring_instance

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    for row in get_pending_recurring_for_date(tomorrow):
        skip_recurring_instance(row["recurring_order_id"], tomorrow)
        logger.info("Auto-skipped recurring order %s for %s", row["recurring_order_id"], tomorrow)
