"""Demo runner — the Telegram DISCOVER-CONFIRM onboarding on a TEST tenant bot.

Try it: create a throwaway bot in @BotFather, set its privacy OFF (/setprivacy → Disable), add it to a test
group, then:

  TWBSHOP_ENV=staging ONBOARD_BOT_TOKEN=<botfather token> ONBOARD_STAFF_CHAT_ID=<-100…> \
  ONBOARD_ORG=demo python run_onboard_demo.py

Have a couple of people post in the group, then send /onboard there and confirm each one. It writes ONLY to
the platform tables (core_staff / core_onboarding_candidates) for ONBOARD_ORG — it NEVER touches TWB's live
data. SECURITY: staging only; the token is passed at runtime, not stored.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

if os.environ.get("TWBSHOP_ENV") != "staging":
    print("Set TWBSHOP_ENV=staging — the demo writes to the platform tables, never TWB live.")
    sys.exit(1)
token = os.environ.get("ONBOARD_BOT_TOKEN")
chat = os.environ.get("ONBOARD_STAFF_CHAT_ID")
org = os.environ.get("ONBOARD_ORG", "demo")
if not token or not chat:
    print("Set ONBOARD_BOT_TOKEN (from BotFather) and ONBOARD_STAFF_CHAT_ID (your test group's chat id).")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from telegram.ext import Application
from core.db import init_core_db, ensure_org
from adapters.telegram_onboarding import register

init_core_db()
ensure_org(org, org)
app = Application.builder().token(token).build()
register(app, org, int(chat))
logging.getLogger("onboard").info("discover-confirm demo: org=%s staff_chat=%s — add the bot to the group, "
                                  "have people post, then /onboard. Ctrl-C to stop.", org, chat)
app.run_polling()
