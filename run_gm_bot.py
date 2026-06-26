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

from shared.runtime_guard import assert_polling_allowed
assert_polling_allowed("GM")  # refuse to poll the live token off the production server

os.makedirs("logs", exist_ok=True)

handler = RotatingFileHandler("logs/gm_bot.log", maxBytes=5_000_000, backupCount=3)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[handler, logging.StreamHandler()],
)

from shared.log_redact import install_log_hygiene
install_log_hygiene()   # keep the bot TOKEN out of logs/*.log + drop the routine getUpdates spam

from shared.database import (
    init_gm_db, init_receipt_clarifications_db, init_gm_finance_db,
    init_gm_clarifications_db, init_gm_lateness_db, init_gm_finance_aliases_db,
    init_gm_leave_db, init_stock_db, init_staff_registry_db, init_attendance_db,
)
from gm_bot.bot import build_app

init_gm_db()
init_receipt_clarifications_db()
init_gm_finance_db()
init_gm_clarifications_db()
init_gm_lateness_db()
init_gm_finance_aliases_db()
init_gm_leave_db()
init_stock_db()
init_staff_registry_db()
init_attendance_db()      # adds the gender column (among others)
from gm_bot.events import init_events_db
init_events_db()          # append-only gm_events audit log (forensics: pushes/clicks/sick/points/FYI)
from core.db import init_core_db, ensure_org
try:
    init_core_db()        # NEW platform tables (shadow-run, additive, inert until gm_state shadow_run=on)
    ensure_org("twb", "TWBshop", "Asia/Phnom_Penh")   # TWBshop = tenant #1
except Exception:
    # The platform layer is INERT/shadow — a schema/init error here must NEVER block the LIVE gm boot.
    logging.getLogger(__name__).exception("init_core_db/ensure_org failed — continuing without the platform layer")
from shared.database import seed_staff_genders
seed_staff_genders()      # fill the gender column from the owner roster (idempotent; logs unmatched)
from shared.database import points_seed_catalogue, set_att_test, gm_get_state
points_seed_catalogue()
# sync the process-global TEST flag with the persisted switch (survives restarts)
set_att_test(gm_get_state("attendance_test_mode") == "true")

app = build_app()
logging.info("GM Manager bot starting...")
app.run_polling(drop_pending_updates=True)
