"""Entry point: python run_import.py — one-time historical import, safe to re-run."""

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
        RotatingFileHandler("logs/importer.log", maxBytes=10 * 1024 * 1024, backupCount=2),
        logging.StreamHandler(),
    ],
)

from ops_intelligence.importer import run_import

if __name__ == "__main__":
    asyncio.run(run_import())
