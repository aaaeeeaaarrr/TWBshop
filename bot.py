"""Telegram bot entry point — handler registration and startup."""

import datetime
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import database
from orders import handle_order_text, handle_callback, handle_menu_command
from photos import handle_incoming_photo, handle_photo_type_callback
from reminders import check_missing_photos
from staff_monitor import handle_staff_message
from summaries import send_production_summary, send_fulfillment_list

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Customer commands
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! Just send your order as a message and I'll confirm it with you.\n"
        "Type /menu to see what's available."
    )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Sorry, I don't know that command.")


# ---------------------------------------------------------------------------
# Staff commands
# ---------------------------------------------------------------------------

def _is_staff(user_id: int) -> bool:
    return not config.STAFF_USER_IDS or user_id in config.STAFF_USER_IDS


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send production totals + fulfillment list to the staff group right now."""
    if not _is_staff(update.effective_user.id):
        await update.message.reply_text("Not authorised.")
        return
    await send_production_summary(context.bot)
    await send_fulfillment_list(context.bot)
    await update.message.reply_text("Summary sent to staff group.")


# ---------------------------------------------------------------------------
# Scheduled job callbacks
# ---------------------------------------------------------------------------

async def _job_daily_summary(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_production_summary(context.bot)
    await send_fulfillment_list(context.bot)


async def _job_check_missing_photos(context: ContextTypes.DEFAULT_TYPE) -> None:
    await check_missing_photos(context.bot)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

def main() -> None:
    database.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Customer handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", handle_menu_command))

    # Staff group text messages — must be registered before the general order handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(config.STAFF_GROUP_ID),
        handle_staff_message,
    ))
    # All other text → customer ordering
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_text))

    # Staff handlers
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(MessageHandler(filters.PHOTO, handle_incoming_photo))

    # Callback handlers — pattern-matched so order and photo buttons don't conflict
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^(confirm|edit|cancel)$"))
    app.add_handler(CallbackQueryHandler(handle_photo_type_callback, pattern=r"^photo:"))

    # Catch-all for unknown commands (must be last)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Schedule daily summary
    summary_time = datetime.time(
        hour=config.SUMMARY_HOUR,
        minute=config.SUMMARY_MINUTE,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_daily_summary, time=summary_time)
    logger.info("Daily summary scheduled at %02d:%02d UTC", config.SUMMARY_HOUR, config.SUMMARY_MINUTE)

    # Schedule missing-photo reminder
    reminder_time = datetime.time(
        hour=config.REMINDER_HOUR,
        minute=config.REMINDER_MINUTE,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_check_missing_photos, time=reminder_time)
    logger.info("Photo reminder scheduled at %02d:%02d UTC", config.REMINDER_HOUR, config.REMINDER_MINUTE)

    logger.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
