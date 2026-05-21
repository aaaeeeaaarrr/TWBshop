"""B2B nightly summary — production totals and per-customer breakdown.

Sent at 9pm Phnom Penh time (14:00 UTC) to the B2B staff group.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
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
)

logger = logging.getLogger(__name__)


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


async def send_b2b_summary(bot: Bot, target_date: str | None = None) -> None:
    # Default: tomorrow's orders only. Same-day cake orders (delivery_date = today)
    # are excluded here — they were already handled by the instant notification on confirm.
    day = target_date or (date.today() + timedelta(days=1)).isoformat()

    bread_totals = get_b2b_daily_totals(day)
    cake_totals = get_b2b_cake_daily_totals(day)

    if not bread_totals and not cake_totals:
        await bot.send_message(config.B2B_STAFF_GROUP_ID, f"No B2B orders for {day}.")
        return

    lines = [f"B2B PRODUCTION — {day}", ""]

    if bread_totals:
        lines.append("BREADS:")
        for row in bread_totals:
            lines.append(f"  {row['item']}: {row['total']}")
        lines.append("")

    if cake_totals:
        lines.append("CAKES:")
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

    for business_name in all_businesses:
        lines.append(f"{business_name}:")

        for o in bread_by_group.get(business_name, []):
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

    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines).rstrip())
    logger.info("Sent B2B summary for %s", day)


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
