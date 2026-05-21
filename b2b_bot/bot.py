"""B2B bot — handler registration and startup."""

import datetime
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
from shared import database
from b2b_bot.orders import handle_group_message, handle_callback
from b2b_bot.summaries import send_b2b_summary

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 9pm Phnom Penh (UTC+7) = 14:00 UTC
_SUMMARY_HOUR_UTC   = 14
_SUMMARY_MINUTE_UTC = 0


async def _job_b2b_summary(context) -> None:
    await send_b2b_summary(context.bot)


async def cmd_summary(update: Update, context) -> None:
    if config.B2B_STAFF_USER_IDS and update.effective_user.id not in config.B2B_STAFF_USER_IDS:
        await update.message.reply_text("Not authorised.")
        return
    await send_b2b_summary(context.bot)
    await update.message.reply_text("B2B summary sent.")


def main() -> None:
    database.init_db()

    app = Application.builder().token(config.B2B_BOT_TOKEN).build()

    # All text messages in groups → order handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        handle_group_message,
    ))

    # Inline button callbacks (all prefixed b2b_)
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^b2b_"))

    # Manual summary trigger for staff
    app.add_handler(CommandHandler("summary", cmd_summary))

    # Nightly summary at 9pm Phnom Penh time
    summary_time = datetime.time(
        hour=_SUMMARY_HOUR_UTC,
        minute=_SUMMARY_MINUTE_UTC,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_b2b_summary, time=summary_time)
    logger.info(
        "B2B nightly summary scheduled at %02d:%02d UTC (21:00 Phnom Penh)",
        _SUMMARY_HOUR_UTC, _SUMMARY_MINUTE_UTC,
    )

    logger.info("B2B bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
