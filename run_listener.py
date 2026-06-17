"""Entry point: python run_listener.py"""

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

if not os.path.exists("secrets.py"):
    sys.exit("secrets.py not found — say 'pull' to Claude Code")

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        RotatingFileHandler("logs/listener.log", maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(),
    ],
)

from ops_intelligence.listener import run

if __name__ == "__main__":
    from shared.runtime_guard import assert_polling_allowed
    assert_polling_allowed("listener")
    asyncio.run(run())
