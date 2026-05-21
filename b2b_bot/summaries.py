"""B2B nightly summary — production totals and per-customer breakdown.

Sent at 9pm Phnom Penh time (14:00 UTC) to the B2B staff group.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from telegram import Bot

import config
from shared.database import get_b2b_daily_totals, get_b2b_orders_by_group, get_b2b_customer

logger = logging.getLogger(__name__)


async def send_b2b_summary(bot: Bot, target_date: str | None = None) -> None:
    # Default: show what needs to be baked tonight = delivery_date tomorrow
    day = target_date or (date.today() + timedelta(days=1)).isoformat()
    totals = get_b2b_daily_totals(day)

    if not totals:
        await bot.send_message(config.B2B_STAFF_GROUP_ID, f"No B2B orders for {day}.")
        return

    lines = [f"B2B PRODUCTION — {day}", ""]
    for row in totals:
        lines.append(f"  {row['item']}: {row['total']}")

    lines += ["", "─" * 28, ""]

    rows = get_b2b_orders_by_group(day)
    by_group: dict[str, list] = defaultdict(list)
    for row in rows:
        by_group[row["business_name"]].append(row)

    for business_name, orders in sorted(by_group.items()):
        lines.append(f"{business_name}:")
        for o in orders:
            line = f"  • {o['quantity']}x {o['item']}"
            if o["grams"]:
                line += f" — {o['grams']}g"
            if o["notes"]:
                line += f" ({o['notes']})"
            lines.append(line)

        customer = get_b2b_customer(orders[0]["group_chat_id"])
        if customer and customer["delivery_method"]:
            if customer["delivery_method"] == "delivery":
                loc = f" — {customer['location']}" if customer["location"] else ""
                lines.append(f"  Delivery at {customer['delivery_time']}{loc}")
            else:
                lines.append(f"  Pickup at {customer['delivery_time']}")
        lines.append("")

    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines).rstrip())
    logger.info("Sent B2B summary for %s", day)
