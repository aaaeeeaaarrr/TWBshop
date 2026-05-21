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
from b2b_bot.billing import (
    handle_payment_photo,
    handle_payment_document,
    handle_payment_callback,
    send_daily_reminders,
    send_weekly_reminders,
    get_all_outstanding_summary,
)
from b2b_bot.orders import handle_group_message, handle_callback
from b2b_bot.summaries import send_b2b_summary, send_b2b_mini_reminder

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 9pm Phnom Penh (UTC+7) = 14:00 UTC
_SUMMARY_HOUR_UTC   = 14
_SUMMARY_MINUTE_UTC = 0

# 9am Phnom Penh (UTC+7) = 02:00 UTC — mini order 48h-before reminder
_REMINDER_HOUR_UTC   = 2
_REMINDER_MINUTE_UTC = 0

# 6am Phnom Penh (UTC+7) = 23:00 UTC (previous calendar day)
_PAYMENT_REMINDER_HOUR_UTC   = 23
_PAYMENT_REMINDER_MINUTE_UTC = 0


async def _job_b2b_summary(context) -> None:
    await send_b2b_summary(context.bot)


async def _job_mini_reminder(context) -> None:
    await send_b2b_mini_reminder(context.bot)


async def _job_daily_payment_reminder(context) -> None:
    await send_daily_reminders(context.bot)


async def _job_weekly_payment_reminder(context) -> None:
    await send_weekly_reminders(context.bot)


async def cmd_summary(update: Update, context) -> None:
    if config.B2B_STAFF_USER_IDS and update.effective_user.id not in config.B2B_STAFF_USER_IDS:
        await update.message.reply_text("Not authorised.")
        return
    await send_b2b_summary(context.bot)
    await update.message.reply_text("B2B summary sent.")


async def cmd_balance(update: Update, context) -> None:
    if config.B2B_STAFF_USER_IDS and update.effective_user.id not in config.B2B_STAFF_USER_IDS:
        await update.message.reply_text("Not authorised.")
        return
    lines = get_all_outstanding_summary()
    await update.message.reply_text(
        "\n".join(lines) if lines else "All B2B accounts are paid up."
    )


def main() -> None:
    database.init_db()

    app = Application.builder().token(config.B2B_BOT_TOKEN).build()

    # Text messages in groups → order handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        handle_group_message,
    ))

    # Photos in groups → payment or order photo detection
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.GROUPS,
        handle_payment_photo,
    ))

    # PDF and image documents in groups → payment or order detection (uncompressed)
    app.add_handler(MessageHandler(
        (filters.Document.PDF | filters.Document.IMAGE) & filters.ChatType.GROUPS,
        handle_payment_document,
    ))

    # Payment callbacks (owner approve/reject + customer yes/no/order)
    app.add_handler(CallbackQueryHandler(handle_payment_callback, pattern=r"^b2b_pay_"))

    # Order callbacks (confirm, edit, cancel, extra, mini)
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^b2b_(?!pay_)"))

    # Staff commands
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("balance", cmd_balance))

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

    # Mini order reminder at 9am Phnom Penh — fires 48h before delivery date
    reminder_time = datetime.time(
        hour=_REMINDER_HOUR_UTC,
        minute=_REMINDER_MINUTE_UTC,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_mini_reminder, time=reminder_time)
    logger.info(
        "B2B mini reminder scheduled at %02d:%02d UTC (09:00 Phnom Penh)",
        _REMINDER_HOUR_UTC, _REMINDER_MINUTE_UTC,
    )

    # Daily payment reminder at 6am Phnom Penh (= 23:00 UTC) — yesterday's unpaid
    pay_reminder_time = datetime.time(
        hour=_PAYMENT_REMINDER_HOUR_UTC,
        minute=_PAYMENT_REMINDER_MINUTE_UTC,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_daily_payment_reminder, time=pay_reminder_time)
    logger.info(
        "B2B daily payment reminder scheduled at %02d:%02d UTC (06:00 Phnom Penh)",
        _PAYMENT_REMINDER_HOUR_UTC, _PAYMENT_REMINDER_MINUTE_UTC,
    )

    # Weekly payment reminder — Monday 6am Phnom Penh (= 23:00 UTC Sunday)
    app.job_queue.run_daily(
        _job_weekly_payment_reminder,
        time=pay_reminder_time,
        days=(6,),  # Sunday UTC = Monday morning PNH
    )
    logger.info("B2B weekly payment reminder scheduled for Sunday 23:00 UTC (Monday 06:00 PNH)")

    logger.info("B2B bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
