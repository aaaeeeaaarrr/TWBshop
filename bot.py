"""Telegram bot entry point — handler registration and startup."""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import config
from orders import handle_order_text, handle_callback

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context) -> None:
    await update.message.reply_text(
        "Welcome! Send your order and I'll help you place it."
    )


async def unknown_command(update: Update, context) -> None:
    await update.message.reply_text("Sorry, I don't know that command.")


def main() -> None:
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_text))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
