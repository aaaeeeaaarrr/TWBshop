"""Telegram bot entry point — handler registration and startup."""

import logging
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

import config
import database
from orders import handle_order_text, handle_callback, handle_menu_command

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context) -> None:
    await update.message.reply_text(
        "Welcome! Just send your order as a message and I'll confirm it with you.\n"
        "Type /menu to see what's available."
    )


async def unknown_command(update: Update, context) -> None:
    await update.message.reply_text("Sorry, I don't know that command.")


def main() -> None:
    database.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", handle_menu_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_text))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
