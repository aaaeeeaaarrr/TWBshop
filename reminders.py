"""Deadline checks and missing photo alerts."""

import logging
from datetime import date
from telegram import Bot

import config
from database import get_submissions_today

logger = logging.getLogger(__name__)


async def check_missing_photos(bot: Bot) -> None:
    """Alert staff group if any required photos haven't been submitted today."""
    if not config.STAFF_USER_IDS:
        logger.info("STAFF_USER_IDS is empty — skipping missing photo check.")
        return

    today = date.today().isoformat()
    missing: list[str] = []

    for photo_type in config.REQUIRED_PHOTO_TYPES:
        submitted_ids = {
            row["user_id"] for row in get_submissions_today(photo_type, today)
        }
        for uid in config.STAFF_USER_IDS:
            if uid not in submitted_ids:
                name = config.STAFF_NAMES.get(uid, f"user {uid}")
                label = photo_type.replace("_", " ").title()
                missing.append(f"  {name} — {label}")

    if not missing:
        logger.info("All required photos submitted for %s.", today)
        return

    lines = [f"REMINDER — Missing photos for {today}:", ""] + missing
    await bot.send_message(config.STAFF_GROUP_ID, "\n".join(lines))
    logger.info("Sent missing photo reminder for %s: %d missing.", today, len(missing))
