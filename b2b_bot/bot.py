"""B2B bot — handler registration and startup."""

import datetime
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
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
from b2b_bot.menu_flow import (
    handle_menu_command, handle_menu_callback, handle_welcome,
    handle_qty_input, qty_pending_filter,
)
from b2b_bot.orders import handle_group_message, handle_callback
from b2b_bot.summaries import send_b2b_summary, send_b2b_pre_summary, send_b2b_mini_reminder
from b2b_bot.recurring import send_recurring_reminders, auto_skip_unconfirmed

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 9pm Phnom Penh (UTC+7) = 14:00 UTC — pre-summary (totals only)
_PRE_SUMMARY_HOUR_UTC   = 14
_PRE_SUMMARY_MINUTE_UTC = 0

# 10:10pm Phnom Penh (UTC+7) = 15:10 UTC — full summary
_SUMMARY_HOUR_UTC   = 15
_SUMMARY_MINUTE_UTC = 10

# 9am Phnom Penh (UTC+7) = 02:00 UTC — mini order 48h-before reminder
_REMINDER_HOUR_UTC   = 2
_REMINDER_MINUTE_UTC = 0

# 6am Phnom Penh (UTC+7) = 23:00 UTC (previous calendar day)
_PAYMENT_REMINDER_HOUR_UTC   = 23
_PAYMENT_REMINDER_MINUTE_UTC = 0

# Recurring order reminders (1 day before fulfillment) — Phnom Penh → UTC
_REC_REMINDER_1_HOUR_UTC = 0   # 7am PNH
_REC_REMINDER_2_HOUR_UTC = 6   # 1pm PNH
_REC_REMINDER_3_HOUR_UTC = 11  # 6pm PNH


async def _startup_summary_check(app) -> None:
    from datetime import timezone, timedelta
    from shared.database import get_bot_meta
    now_utc  = datetime.datetime.now(timezone.utc)
    today_pp = (now_utc + timedelta(hours=7)).date().isoformat()
    past_full = now_utc.hour > _SUMMARY_HOUR_UTC or (now_utc.hour == _SUMMARY_HOUR_UTC and now_utc.minute >= _SUMMARY_MINUTE_UTC)
    past_pre  = now_utc.hour >= _PRE_SUMMARY_HOUR_UTC
    if past_full and get_bot_meta("last_summary_date") != today_pp:
        logger.info("Startup: missed full summary — sending now")
        await send_b2b_summary(app.bot)
    elif past_pre and not past_full and get_bot_meta("last_pre_summary_date") != today_pp:
        logger.info("Startup: missed pre-summary — sending now")
        await send_b2b_pre_summary(app.bot)


async def _job_b2b_pre_summary(context) -> None:
    await send_b2b_pre_summary(context.bot)


async def _job_b2b_summary(context) -> None:
    await auto_skip_unconfirmed(context.bot)
    await send_b2b_summary(context.bot)


async def _job_recurring_reminder_1(context) -> None:
    await send_recurring_reminders(context.bot, reminder_num=1)


async def _job_recurring_reminder_2(context) -> None:
    await send_recurring_reminders(context.bot, reminder_num=2)


async def _job_recurring_reminder_3(context) -> None:
    await send_recurring_reminders(context.bot, reminder_num=3)


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

    app = (
        Application.builder()
        .token(config.B2B_BOT_TOKEN)
        .post_init(_startup_summary_check)
        .connect_timeout(20.0)
        .read_timeout(20.0)
        .write_timeout(20.0)
        .pool_timeout(20.0)
        .build()
    )

    # Bot added to a group → auto-welcome with menu
    app.add_handler(ChatMemberHandler(handle_welcome, ChatMemberHandler.MY_CHAT_MEMBER))

    # /menu and /B2Bmenu commands
    app.add_handler(CommandHandler("menu", handle_menu_command))
    app.add_handler(CommandHandler("B2Bmenu", handle_menu_command))

    # Interactive menu callbacks (bm_*)
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^bm_"))

    # Typed quantity when a qty prompt is pending (must be before order handler)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS & qty_pending_filter,
        handle_qty_input,
    ))

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

    # Pre-summary at 9pm Phnom Penh — totals only, deleted when full summary fires
    pre_summary_time = datetime.time(
        hour=_PRE_SUMMARY_HOUR_UTC,
        minute=_PRE_SUMMARY_MINUTE_UTC,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_b2b_pre_summary, time=pre_summary_time)
    logger.info("B2B pre-summary scheduled at %02d:%02d UTC (21:00 Phnom Penh)", _PRE_SUMMARY_HOUR_UTC, _PRE_SUMMARY_MINUTE_UTC)

    # Full summary at 10:10pm Phnom Penh
    summary_time = datetime.time(
        hour=_SUMMARY_HOUR_UTC,
        minute=_SUMMARY_MINUTE_UTC,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_job_b2b_summary, time=summary_time)
    logger.info("B2B full summary scheduled at %02d:%02d UTC (22:10 Phnom Penh)", _SUMMARY_HOUR_UTC, _SUMMARY_MINUTE_UTC)

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

    # Recurring order reminders — 7am, 1pm, 6pm Phnom Penh (the day before fulfillment)
    for hour_utc, num in [
        (_REC_REMINDER_1_HOUR_UTC, 1),
        (_REC_REMINDER_2_HOUR_UTC, 2),
        (_REC_REMINDER_3_HOUR_UTC, 3),
    ]:
        job_fn = [_job_recurring_reminder_1, _job_recurring_reminder_2, _job_recurring_reminder_3][num - 1]
        app.job_queue.run_daily(
            job_fn,
            time=datetime.time(hour=hour_utc, minute=0, tzinfo=datetime.timezone.utc),
        )
        logger.info("Recurring reminder #%s scheduled at %02d:00 UTC", num, hour_utc)

    logger.info("B2B bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
