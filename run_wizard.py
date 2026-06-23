"""Entry point: the Wizard config viewer (Stage 1, READ-ONLY).

SECURITY (CLAUDE.md ▶▶ PRODUCT SECURITY & IP): binds to localhost ONLY (never 0.0.0.0) — reach it through
an SSH tunnel:  ssh -L 8090:localhost:8090 twbshop  then open http://localhost:8090 . The brain/rules stay
server-side; this serves rendered views only; nothing public until real logins + HTTPS exist.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: F401 — presence check; missing secrets.py → the standard "say pull" path

if not os.environ.get("TWBSHOP_ENV"):
    print("TWBSHOP_ENV not set (prod|staging). e.g.  TWBSHOP_ENV=prod python run_wizard.py")
    sys.exit(1)

os.makedirs("logs", exist_ok=True)
handler = RotatingFileHandler("logs/wizard.log", maxBytes=5_000_000, backupCount=3)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[handler, logging.StreamHandler()])

from wizard.app import app

if __name__ == "__main__":
    host = "127.0.0.1"                                    # localhost ONLY (security law)
    port = int(os.environ.get("WIZARD_PORT", "8090"))
    logging.getLogger("wizard").info("Wizard viewer (read-only) on http://%s:%d  — tunnel in to reach it",
                                     host, port)
    app.run(host=host, port=port, threaded=False)        # single-thread: the shared DB pool isn't thread-safe
