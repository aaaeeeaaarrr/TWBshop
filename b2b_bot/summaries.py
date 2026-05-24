"""B2B nightly summary — production totals and per-customer breakdown.

Sent at 10:10pm Phnom Penh time (15:10 UTC) to the B2B staff group.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from telegram import Bot

import config
from b2b_bot.menu import MINI_ITEMS
from shared.database import (
    get_b2b_daily_totals,
    get_b2b_cake_daily_totals,
    get_b2b_orders_by_group,
    get_b2b_cake_orders_by_group,
    get_b2b_customer,
    get_b2b_mini_orders_for_reminder,
    get_bot_meta, set_bot_meta,
)

logger = logging.getLogger(__name__)

_pre_summary_msg_id: int | None = None


def _cake_total_label(row) -> str:
    order_type = row["order_type"]
    slices = row["slices"]
    if order_type == "full":
        return f"{row['item']} (full)"
    if order_type == "sliced":
        s = f"{slices}-slice" if slices else "sliced"
        return f"{row['item']} ({s})"
    if order_type == "tray":
        return f"{row['item']} (tray)"
    return f"{row['item']} (piece)"


def _cake_order_label(row) -> str:
    order_type = row["order_type"]
    slices = row["slices"]
    qty = row["quantity"]
    if order_type == "full":
        return f"  • {qty}x {row['item']} — full"
    if order_type == "sliced":
        s = f"{slices}-slice" if slices else "sliced"
        return f"  • {qty}x {row['item']} — {s}"
    if order_type == "tray":
        return f"  • {qty}x {row['item']} — tray"
    return f"  • {qty}x {row['item']} — piece"


async def send_b2b_pre_summary(bot: Bot, target_date: str | None = None) -> None:
    global _pre_summary_msg_id
    day = target_date or (date.today() + timedelta(days=1)).isoformat()
    bread_totals = get_b2b_daily_totals(day)
    cake_totals  = get_b2b_cake_daily_totals(day)

    lines = ["⏳ Wait till 10:10pm for full order list", ""]
    if not bread_totals and not cake_totals:
        lines.append(f"No B2B orders yet for {day}.")
    else:
        lines.append(f"B2B TOTALS — {day}")
        lines.append("")
        if bread_totals:
            lines.append("TOTAL BREADS:")
            for row in bread_totals:
                lines.append(f"  {row['item']}: {row['total']}")
            lines.append("")
        if cake_totals:
            lines.append("TOTAL CAKES:")
            for row in cake_totals:
                lines.append(f"  {_cake_total_label(row)}: {row['total']}")

    msg = await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines).rstrip())
    _pre_summary_msg_id = msg.message_id
    set_bot_meta("last_pre_summary_date", day)
    logger.info("Sent B2B pre-summary for %s (msg_id=%s)", day, msg.message_id)


async def send_b2b_summary(bot: Bot, target_date: str | None = None) -> None:
    global _pre_summary_msg_id
    if _pre_summary_msg_id:
        try:
            await bot.delete_message(config.B2B_STAFF_GROUP_ID, _pre_summary_msg_id)
        except Exception:
            pass
        _pre_summary_msg_id = None

    # Default: tomorrow's orders only. Same-day cake orders (delivery_date = today)
    # are excluded here — they were already handled by the instant notification on confirm.
    day = target_date or (date.today() + timedelta(days=1)).isoformat()

    bread_totals = get_b2b_daily_totals(day)
    cake_totals = get_b2b_cake_daily_totals(day)

    if not bread_totals and not cake_totals:
        msg = await bot.send_message(config.B2B_STAFF_GROUP_ID, f"No B2B orders for {day}.")
        set_bot_meta("last_summary_date", day)
        set_bot_meta("last_summary_msg_id", str(msg.message_id))
        set_bot_meta("last_summary_has_orders", "0")
        return

    lines = [f"B2B PRODUCTION — {day}", ""]

    if bread_totals:
        lines.append("TOTAL BREADS:")
        for row in bread_totals:
            lines.append(f"  {row['item']}: {row['total']}")
        lines.append("")

    if cake_totals:
        lines.append("TOTAL CAKES:")
        for row in cake_totals:
            lines.append(f"  {_cake_total_label(row)}: {row['total']}")
        lines.append("")

    lines += ["─" * 28, ""]

    # Per-customer breakdown — merge bread and cake rows by business
    bread_rows = get_b2b_orders_by_group(day)
    cake_rows = get_b2b_cake_orders_by_group(day)

    bread_by_group: dict[str, list] = defaultdict(list)
    for row in bread_rows:
        bread_by_group[row["business_name"]].append(row)

    cake_by_group: dict[str, list] = defaultdict(list)
    for row in cake_rows:
        cake_by_group[row["business_name"]].append(row)

    all_businesses = sorted(set(bread_by_group) | set(cake_by_group))

    for i, business_name in enumerate(all_businesses):
        if i > 0:
            lines += ["─" * 28, ""]

        lines.append(f"{business_name}:")

        # Combine duplicate bread rows (same item+grams+notes)
        combined_bread: dict[tuple, dict] = {}
        order: list[tuple] = []
        for o in bread_by_group.get(business_name, []):
            key = (o["item"], o["grams"], o["notes"])
            if key in combined_bread:
                combined_bread[key]["quantity"] += o["quantity"]
            else:
                combined_bread[key] = dict(o)
                order.append(key)
        for key in order:
            o = combined_bread[key]
            line = f"  • {o['quantity']}x {o['item']}"
            if o["grams"]:
                line += f" — {o['grams']}g"
            if o["notes"]:
                line += f" ({o['notes']})"
            lines.append(line)

        for o in cake_by_group.get(business_name, []):
            lines.append(_cake_order_label(o))

        # Delivery / pickup info
        bread_list = bread_by_group.get(business_name, [])
        cake_list = cake_by_group.get(business_name, [])
        group_chat_id = (bread_list or cake_list)[0]["group_chat_id"]
        customer = get_b2b_customer(group_chat_id)
        if customer and customer["delivery_method"]:
            if customer["delivery_method"] == "delivery":
                loc = f" — {customer['location']}" if customer["location"] else ""
                lines.append(f"  Delivery at {customer['delivery_time']}{loc}")
            else:
                lines.append(f"  Pickup at {customer['delivery_time']}")
        lines.append("")

    msg = await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines).rstrip())
    set_bot_meta("last_summary_date", day)
    set_bot_meta("last_summary_msg_id", str(msg.message_id))
    set_bot_meta("last_summary_has_orders", "1")
    logger.info("Sent B2B summary for %s (msg_id=%s)", day, msg.message_id)


async def send_b2b_mini_reminder(bot: Bot, target_date: str | None = None) -> None:
    """Remind bakery group about mini orders due in 48h (delivery_date = day+2)."""
    day = target_date or (date.today() + timedelta(days=2)).isoformat()
    rows = get_b2b_mini_orders_for_reminder(day, tuple(MINI_ITEMS))
    if not rows:
        return  # silent when no mini orders due

    lines = [f"MINI ORDER REMINDER — delivery: {day}", "(48h advance notice)", ""]
    by_group: dict[str, list] = defaultdict(list)
    for row in rows:
        by_group[row["business_name"]].append(row)

    for business_name, orders in sorted(by_group.items()):
        lines.append(f"{business_name}:")
        for o in orders:
            lines.append(f"  • {o['quantity']}x {o['item']}")
        customer = get_b2b_customer(orders[0]["group_chat_id"])
        if customer and customer["delivery_method"]:
            if customer["delivery_method"] == "delivery":
                loc = f" — {customer['location']}" if customer["location"] else ""
                lines.append(f"  Delivery at {customer['delivery_time']}{loc}")
            else:
                lines.append(f"  Pickup at {customer['delivery_time']}")
        lines.append("")

    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines).rstrip())
    logger.info("Sent B2B mini reminder for %s", day)


def _sort_key(time_str: str) -> int:
    """Convert '8:00am' / '12:30pm' to minutes since midnight for sorting."""
    try:
        t = datetime.strptime(time_str.upper().replace(" ", ""), "%I:%M%p")
        return t.hour * 60 + t.minute
    except ValueError:
        return 9999


def _build_dispatch_list(day: str) -> str:
    """Build the customer/time sorted dispatch list for a delivery day."""
    bread_rows = get_b2b_orders_by_group(day)
    cake_rows  = get_b2b_cake_orders_by_group(day)

    seen: dict[int, str] = {}
    for row in list(bread_rows) + list(cake_rows):
        gid = row["group_chat_id"]
        if gid not in seen:
            seen[gid] = row["business_name"]

    entries = []
    for gid, biz_name in seen.items():
        cust = get_b2b_customer(gid)
        time_str = (cust["delivery_time"] or "?") if cust else "?"
        method   = (cust["delivery_method"] or "?") if cust else "?"
        entries.append((time_str, method, biz_name))

    entries.sort(key=lambda x: _sort_key(x[0]))

    n = len(entries)
    lines = [f"{n} CUSTOMER{'S' if n != 1 else ''} — {day}", ""]
    for time_str, method, biz_name in entries:
        method_label = "Delivery" if method == "delivery" else "Pickup" if method == "pickup" else method
        lines.append(f"{time_str}  {method_label} — {biz_name}")

    return "\n".join(lines)


async def send_b2b_dispatch_reminder(bot: Bot, reminder_num: int) -> None:
    """Reply to tonight's 10:10pm summary with the dispatch list.

    reminder_num=1: 4:30am PNH — detailed list. Skips if no orders.
    reminder_num=2: 6:10am PNH — deletes the 4:30am message, sends fresh list.
                    If no orders: sends 'No B2B orders today' instead.
    Skips silently if no summary was sent for today or msg_id not stored.
    """
    today_pnh = (datetime.now(timezone.utc) + timedelta(hours=7)).date().isoformat()

    if get_bot_meta("last_summary_date") != today_pnh:
        logger.info("Dispatch reminder %s: no summary for %s — skipping", reminder_num, today_pnh)
        return

    summary_msg_id_str = get_bot_meta("last_summary_msg_id")
    if not summary_msg_id_str:
        logger.info("Dispatch reminder %s: summary_msg_id not stored — skipping", reminder_num)
        return

    has_orders = get_bot_meta("last_summary_has_orders") == "1"

    if reminder_num == 1 and not has_orders:
        logger.info("Dispatch reminder 1: no orders for %s — skipping", today_pnh)
        return

    if reminder_num == 2:
        dispatch_msg_id_str  = get_bot_meta("last_dispatch_msg_id")
        dispatch_msg_id_date = get_bot_meta("last_dispatch_msg_id_date")
        if dispatch_msg_id_str and dispatch_msg_id_date == today_pnh:
            try:
                await bot.delete_message(config.B2B_STAFF_GROUP_ID, int(dispatch_msg_id_str))
            except Exception:
                pass

    text = _build_dispatch_list(today_pnh) if has_orders else "No B2B orders today"

    try:
        msg = await bot.send_message(
            config.B2B_STAFF_GROUP_ID,
            text,
            reply_to_message_id=int(summary_msg_id_str),
            allow_sending_without_reply=True,
        )
        if reminder_num == 1:
            set_bot_meta("last_dispatch_msg_id", str(msg.message_id))
            set_bot_meta("last_dispatch_msg_id_date", today_pnh)
        logger.info("Sent dispatch reminder %s for %s (msg_id=%s)", reminder_num, today_pnh, msg.message_id)
    except Exception as e:
        logger.error("Dispatch reminder %s failed: %s", reminder_num, e)
