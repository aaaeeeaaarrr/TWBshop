"""Production totals and per-customer fulfillment lists."""

import logging
from datetime import date
from telegram import Bot

import config
from database import get_daily_totals, get_orders_by_user

logger = logging.getLogger(__name__)


async def send_production_summary(bot: Bot, target_date: str | None = None) -> None:
    """Post daily production totals to the staff group."""
    day = target_date or date.today().isoformat()
    totals = get_daily_totals(day)

    if not totals:
        await bot.send_message(config.STAFF_GROUP_ID, f"No orders for {day}.")
        return

    lines = [f"Production totals for {day}:"]
    for row in totals:
        lines.append(f"  • {row['item']}: {row['total']}")

    await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines))
    logger.info("Sent production summary for %s", day)


async def send_fulfillment_list(bot: Bot, target_date: str | None = None) -> None:
    """Post per-customer fulfillment list to the staff group."""
    day = target_date or date.today().isoformat()
    rows = get_orders_by_user(day)

    if not rows:
        await bot.send_message(config.STAFF_GROUP_ID, f"No fulfillment items for {day}.")
        return

    # Group by user
    by_user: dict[int, list] = {}
    for row in rows:
        by_user.setdefault(row["user_id"], []).append(
            f"    {row['quantity']}x {row['item']}"
        )

    lines = [f"Fulfillment list for {day}:"]
    for user_id, items in by_user.items():
        lines.append(f"  User {user_id}:")
        lines.extend(items)

    await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines))
    logger.info("Sent fulfillment list for %s", day)
