"""B2B dispatch reminders — 1h pre-fulfillment nudge to owner with snooze buttons."""

import logging
from datetime import date, datetime, timedelta, timezone

import config
from b2b_bot.customers import get_business_name
from b2b_bot.pricing import price_summary, order_total
from shared.database import (
    get_b2b_bread_orders_for_group_date,
    get_b2b_cake_orders_for_date,
    get_b2b_customer,
    get_b2b_orders_by_group,
    get_b2b_cake_orders_by_group,
    ensure_b2b_dispatch_reminder,
    get_pending_dispatch_reminders,
    get_dispatch_reminder,
    set_dispatch_reminder_reminded,
    set_dispatch_reminder_snoozed,
    set_dispatch_reminder_confirmed,
    set_dispatch_reminder_escalated,
)

logger = logging.getLogger(__name__)

_TZ_PNH = timezone(timedelta(hours=7))


def _parse_fulfillment_dt(date_str: str, time_str: str) -> datetime | None:
    try:
        t = datetime.strptime(time_str.upper().replace(" ", ""), "%I:%M%p")
        d = date.fromisoformat(date_str)
        pnh_dt = datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=_TZ_PNH)
        return pnh_dt.astimezone(timezone.utc)
    except Exception:
        return None


def _mins_remaining(fulfillment_utc: datetime) -> int:
    return int((fulfillment_utc - datetime.now(timezone.utc)).total_seconds() / 60)


def _build_text(group_chat_id: int, fulfillment_date: str, delivery_method: str, fulfillment_time: str) -> str:
    business = get_business_name(group_chat_id) or "Customer"
    bread_rows = get_b2b_bread_orders_for_group_date(group_chat_id, fulfillment_date)
    cake_rows  = get_b2b_cake_orders_for_date(group_chat_id, fulfillment_date)

    method_label = "Delivery" if delivery_method == "delivery" else "Pickup"
    lines = [business, f"📅 {fulfillment_date}  |  {method_label} at {fulfillment_time}", ""]

    for o in bread_rows:
        line = f"  • {o['quantity']}x {o['item']}"
        if o["grams"]:
            line += f" — {o['grams']}g"
        if o["notes"]:
            line += f" ({o['notes']})"
        lines.append(line)

    for o in cake_rows:
        line = f"  • {o['quantity']}x {o['item']}"
        if o.get("order_type") == "full":
            line += " — full"
        elif o.get("order_type") == "sliced":
            s = f"{o['slices']}-slice" if o.get("slices") else "sliced"
            line += f" — {s}"
        elif o.get("order_type") == "tray":
            line += " — tray"
        lines.append(line)

    bread_items = [{"item": r["item"], "qty": r["quantity"], "grams": r["grams"]} for r in bread_rows]
    cake_items  = [{"item": r["item"], "qty": r["quantity"], "order_type": r.get("order_type"), "slices": r.get("slices")} for r in cake_rows]
    total = order_total(bread_items, cake_items)

    customer = get_b2b_customer(group_chat_id)
    delivery_cost = (
        float(customer["delivery_cost"])
        if customer and customer.get("delivery_cost") and delivery_method == "delivery"
        else None
    )

    lines += ["", price_summary(total, delivery_cost)]
    return "\n".join(lines)


def _build_keyboard(reminder_id: int, mins: int, delivery_method: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    if delivery_method == "delivery":
        confirm_label = "🚗 Already in delivery"
    else:
        confirm_label = "✅ Ready for Pickup"
    row1 = [InlineKeyboardButton(confirm_label, callback_data=f"b2b_dispatch_confirm_{reminder_id}")]
    row2 = [
        InlineKeyboardButton(f"Remind me in {snooze_mins} min", callback_data=f"b2b_dispatch_snooze_{reminder_id}_{snooze_mins}")
        for snooze_mins, threshold in [(30, 45), (20, 35), (10, 25)]
        if mins > threshold
    ]
    return InlineKeyboardMarkup([row1] + ([row2] if row2 else []))


async def _send_reminder(bot, rec: dict) -> None:
    if not config.DISPATCH_REMINDER_TELEGRAM_ID:
        return
    fulfillment_utc = _parse_fulfillment_dt(rec["fulfillment_date"], rec["fulfillment_time"])
    if not fulfillment_utc:
        return
    mins = _mins_remaining(fulfillment_utc)
    text = _build_text(rec["group_chat_id"], rec["fulfillment_date"], rec["delivery_method"], rec["fulfillment_time"])
    kb   = _build_keyboard(rec["id"], mins, rec["delivery_method"])
    try:
        msg = await bot.send_message(config.DISPATCH_REMINDER_TELEGRAM_ID, text, reply_markup=kb)
        set_dispatch_reminder_reminded(rec["id"], msg.message_id)
        logger.info("Dispatch reminder sent for group %s on %s (msg_id=%s)", rec["group_chat_id"], rec["fulfillment_date"], msg.message_id)
    except Exception as e:
        logger.error("Failed to send dispatch reminder for group %s: %s", rec["group_chat_id"], e)


async def run_dispatch_reminder_tick(bot) -> None:
    """Called every 60s — creates records for today's orders, fires reminders, escalates."""
    now_utc   = datetime.now(timezone.utc)
    today_pnh = (now_utc + timedelta(hours=7)).date().isoformat()

    # Ensure a reminder record exists for every customer with orders today
    bread_rows = get_b2b_orders_by_group(today_pnh)
    cake_rows  = get_b2b_cake_orders_by_group(today_pnh)

    seen: set[int] = set()
    for row in list(bread_rows) + list(cake_rows):
        gid = row["group_chat_id"]
        if gid in seen:
            continue
        seen.add(gid)
        customer = get_b2b_customer(gid)
        if customer and customer.get("delivery_time"):
            ensure_b2b_dispatch_reminder(
                gid, today_pnh,
                customer["delivery_time"],
                customer["delivery_method"] or "delivery",
            )

    # Process all non-confirmed reminders for today
    for rec in get_pending_dispatch_reminders(today_pnh):
        fulfillment_utc = _parse_fulfillment_dt(rec["fulfillment_date"], rec["fulfillment_time"])
        if not fulfillment_utc:
            continue

        mins = _mins_remaining(fulfillment_utc)

        # Fire initial 1h reminder
        if rec["status"] == "pending" and mins <= 60:
            await _send_reminder(bot, rec)

        # Fire snooze reminder when snooze_until has passed
        elif rec["status"] == "snoozed" and rec["snooze_until"]:
            snooze_dt = datetime.fromisoformat(rec["snooze_until"])
            if snooze_dt.tzinfo is None:
                snooze_dt = snooze_dt.replace(tzinfo=timezone.utc)
            if now_utc >= snooze_dt:
                await _send_reminder(bot, rec)

        # 5-min escalation to staff group if still unconfirmed
        if not rec["escalated"] and mins <= 5:
            business = get_business_name(rec["group_chat_id"]) or "Customer"
            method_label = "delivery" if rec["delivery_method"] == "delivery" else "pickup"
            try:
                await bot.send_message(
                    config.B2B_STAFF_GROUP_ID,
                    f"⚠️ Not yet dispatched — {business}, {method_label} at {rec['fulfillment_time']}",
                )
                set_dispatch_reminder_escalated(rec["id"])
                logger.info("Escalated dispatch reminder for group %s", rec["group_chat_id"])
            except Exception as e:
                logger.error("Escalation failed for group %s: %s", rec["group_chat_id"], e)


async def handle_dispatch_confirm(update, context) -> None:
    query = update.callback_query
    await query.answer()
    reminder_id = int(query.data.split("_")[3])
    rec = get_dispatch_reminder(reminder_id)
    if not rec:
        return

    fulfillment_utc = _parse_fulfillment_dt(rec["fulfillment_date"], rec["fulfillment_time"])
    late = fulfillment_utc is not None and datetime.now(timezone.utc) > fulfillment_utc

    if rec["delivery_method"] == "delivery":
        label = "⚠️ LATE DELIVERED" if late else "✅ DELIVERED"
    else:
        label = "⚠️ LATE READY FOR PICKUP" if late else "✅ READY FOR PICKUP"

    base_text = _build_text(rec["group_chat_id"], rec["fulfillment_date"], rec["delivery_method"], rec["fulfillment_time"])
    try:
        await query.edit_message_text(f"{label}\n\n{base_text}")
    except Exception:
        pass
    set_dispatch_reminder_confirmed(reminder_id)


async def handle_dispatch_snooze(update, context) -> None:
    query = update.callback_query
    await query.answer()
    parts       = query.data.split("_")
    reminder_id = int(parts[3])
    snooze_mins = int(parts[4])

    snooze_until = (datetime.now(timezone.utc) + timedelta(minutes=snooze_mins)).isoformat()
    set_dispatch_reminder_snoozed(reminder_id, snooze_until)

    try:
        await query.delete_message()
    except Exception:
        pass
