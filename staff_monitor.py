"""Staff message logging and check_staff_message() stub."""

import logging
from telegram import Update

logger = logging.getLogger(__name__)


def check_staff_message(text: str, context: list) -> dict:
    # Placeholder: will connect to Claude API later
    return {"action": "none", "flag": False}


async def handle_staff_message(update: Update, context) -> None:
    text = update.message.text or ""
    user_id = update.effective_user.id

    result = check_staff_message(text, [])
    logger.info("Staff msg from %s: %r | check: %s", user_id, text, result)

    if result.get("flag"):
        logger.warning("Flagged staff message from %s: %r", user_id, text)
