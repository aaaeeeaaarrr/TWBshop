"""LOCAL TEST launcher for the accountant bot — staging DB + dev poller + the Python-3.14
event-loop workaround. NOT production (the server uses run_accountant.py with TWBSHOP_POLL_OK).

    python scripts/run_accountant_local.py

ONE poller per token: do NOT run this on two machines at once (Telegram would drop updates).
"""
import asyncio
import os
import sys

# Python 3.14: run_polling() calls asyncio.get_event_loop(), which now needs a current loop.
asyncio.set_event_loop(asyncio.new_event_loop())
os.environ.setdefault("TWBSHOP_ENV", "staging")       # test data, never prod
os.environ.setdefault("ALLOW_LOCAL_POLLING", "1")     # deliberate local opt-in (runtime_guard)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from secrets import ACCOUNTANT_BOT_TOKEN
except ImportError:
    ACCOUNTANT_BOT_TOKEN = ""
if not ACCOUNTANT_BOT_TOKEN:
    sys.exit("ACCOUNTANT_BOT_TOKEN missing — add it to secrets.py + `python bootstrap.py --push-secrets`.")

from accountant.db import init_accounting_db
from accountant.bot import build_application

init_accounting_db()
print("accountant bot: LOCAL staging test poller started", flush=True)
build_application(ACCOUNTANT_BOT_TOKEN).run_polling(drop_pending_updates=True)
