"""Entry point for the hiring bot. systemd: twbshop-hire"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

sys.path.insert(0, '/root/TWBshop')

try:
    from secrets import HIRE_BOT_TOKEN
except ImportError:
    print("ERROR: HIRE_BOT_TOKEN not found in secrets.py — add it to the secrets repo and re-pull.")
    sys.exit(1)

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("logs/hire_bot.log", maxBytes=5 * 1024 * 1024,
                            backupCount=3, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from hire_bot.bot import build_application

if __name__ == "__main__":
    logger.info("Starting hire bot…")
    app = build_application(HIRE_BOT_TOKEN)
    app.run_polling(drop_pending_updates=True)
