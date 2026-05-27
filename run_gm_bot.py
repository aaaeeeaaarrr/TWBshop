"""Entry point: GM Manager TWB bot."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(__file__))

import config

if not config.GM_BOT_TOKEN:
    print("GM_BOT_TOKEN is not set. Add it to secrets.py and re-run bootstrap.")
    sys.exit(1)

os.makedirs("logs", exist_ok=True)

handler = RotatingFileHandler("logs/gm_bot.log", maxBytes=5_000_000, backupCount=3)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[handler, logging.StreamHandler()],
)

from shared.database import init_gm_db, init_receipt_clarifications_db
from gm_bot.bot import build_app

init_gm_db()
init_receipt_clarifications_db()

app = build_app()
logging.info("GM Manager bot starting...")
app.run_polling(drop_pending_updates=True)
