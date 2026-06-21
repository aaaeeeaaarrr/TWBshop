"""Entry point for the accountant bot. systemd: twbshop-accountant"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

sys.path.insert(0, '/root/TWBshop')

try:
    from secrets import ACCOUNTANT_BOT_TOKEN
except ImportError:
    ACCOUNTANT_BOT_TOKEN = ""

if not ACCOUNTANT_BOT_TOKEN:
    print("ERROR: ACCOUNTANT_BOT_TOKEN missing or empty — create the bot via @BotFather, add it "
          "to the secrets repo (python bootstrap.py --push-secrets), and re-pull.")
    sys.exit(1)

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("logs/accountant.log", maxBytes=5 * 1024 * 1024,
                            backupCount=3, encoding="utf-8"),
    ],
)
# keep the bot TOKEN out of logs — redaction filter + httpx/httpcore/telegram.request->WARNING (Jun 22)
from shared.log_redact import install_log_hygiene
install_log_hygiene()
logging.getLogger("hpack").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

from accountant.db import init_accounting_db
from accountant.bot import build_application

if __name__ == "__main__":
    from shared.runtime_guard import assert_polling_allowed
    assert_polling_allowed("accountant")
    init_accounting_db()  # idempotent — ensure the schema on whichever DB the env selects
    logger.info("Starting accountant bot…")
    app = build_application(ACCOUNTANT_BOT_TOKEN)
    app.run_polling(drop_pending_updates=True)
