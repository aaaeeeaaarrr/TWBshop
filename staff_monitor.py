"""Staff message logging and AI monitoring."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


async def check_staff_message(text: str, prior_context: list) -> dict:
    if not getattr(config, "ANTHROPIC_API_KEY", None):
        return {"action": "none", "flag": False, "reason": ""}

    from ai_client import check_staff_message_ai
    return await check_staff_message_ai(text, prior_context)


async def handle_staff_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    user_id = update.effective_user.id
    staff_name = config.STAFF_NAMES.get(user_id, str(user_id))

    result = await check_staff_message(text, [])
    logger.info("Staff msg from %s: %r | result: %s", staff_name, text, result)

    if not result.get("flag"):
        return

    action = result.get("action", "alert")
    reason = result.get("reason", "")
    prefix = "URGENT" if action == "urgent" else "ALERT"

    alert = f"[{prefix}] Staff message flagged — {staff_name}"
    if reason:
        alert += f"\nReason: {reason}"

    await context.bot.send_message(config.STAFF_GROUP_ID, alert)
    logger.warning("Flagged staff message from %s: %r — %s", staff_name, text, reason)
