"""Entry point: python run_extract_prices.py"""
import sys
import os
if not os.path.exists("secrets.py"):
    sys.exit("Secrets missing — say 'pull' to Claude Code")

import asyncio
import logging
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)
handler = RotatingFileHandler("logs/price_extract.log", maxBytes=10 * 1024 * 1024, backupCount=2)
logging.basicConfig(
    handlers=[handler, logging.StreamHandler()],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

from ops_intelligence.price_extractor import run
asyncio.run(run())
