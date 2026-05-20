"""Deadline checks and missing photo alerts (scheduled jobs)."""

import logging
from telegram import Bot

import config

logger = logging.getLogger(__name__)

# Placeholder: implement with APScheduler or python-telegram-bot's JobQueue
async def check_missing_photos(bot: Bot) -> None:
    """Alert staff group if expected photos haven't arrived by deadline."""
    logger.info("Running missing photo check...")
    # TODO: query photo storage for today's expected submissions
    # and send a reminder to config.STAFF_GROUP_ID if any are missing
