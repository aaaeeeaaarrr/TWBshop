"""Production totals and per-customer fulfillment lists."""

import logging
from collections import defaultdict
from datetime import date
from telegram import Bot

import config
from shared.database import get_daily_totals, get_orders_by_user

logger = logging.getLogger(__name__)


async def send_production_summary(bot: Bot, target_date: str | None = None) -> None:
    """Post daily production totals to the staff group."""
    day = target_date or date.today().isoformat()
    totals = get_daily_totals(day)

    if not totals:
        await bot.send_message(config.STAFF_GROUP_ID, f"No confirmed orders for {day}.")
        return

    lines = [f"PRODUCTION TOTALS — {day}", ""]
    for row in totals:
        lines.append(f"  {row['item']}: {row['total']}")

    await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines))
    logger.info("Sent production summary for %s", day)


async def send_fulfillment_list(bot: Bot, target_date: str | None = None) -> None:
    """Post per-customer fulfillment list to the staff group."""
    day = target_date or date.today().isoformat()
    rows = get_orders_by_user(day)

    if not rows:
        await bot.send_message(config.STAFF_GROUP_ID, f"No fulfillment items for {day}.")
        return

    # Group rows by customer name
    by_customer: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_customer[row["customer_name"]].append(
            f"    {row['quantity']}x {row['item']}"
        )

    lines = [f"FULFILLMENT LIST — {day}", ""]
    for name, items in sorted(by_customer.items()):
        lines.append(f"  {name}:")
        lines.extend(items)
        lines.append("")

    await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines).rstrip())
    logger.info("Sent fulfillment list for %s", day)
