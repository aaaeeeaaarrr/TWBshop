"""Entry point for the stock worker — headless (AppSheet <-> Postgres sync + reorder cron).
systemd/cron: twbshop-stock. NOT YET DEPLOYED — inert on prod; staging only.

NOT a chat bot: staff use the GM bot's gateway button -> AppSheet (design, session 43). This worker
keeps Postgres (the source of truth) and AppSheet in sync and computes the reorder list. It is run
once per invocation by cron (like scripts/fetch_report_receipts.py), so it does one pass and exits.

No Telegram token is needed (no bot). The only external dependency is the database, selected by the
fail-closed TWBSHOP_ENV switch (shared/database.py refuses an unset/unknown env) — so a misconfigured
run dies loudly instead of touching the wrong DB.

Usage:
  TWBSHOP_ENV=staging python run_stock.py --seed   seed/refresh the acc_items catalog (idempotent)
  TWBSHOP_ENV=staging python run_stock.py          one worker tick (reorder list + sync if wired)
"""
import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

sys.path.insert(0, '/root/TWBshop')

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("logs/stock.log", maxBytes=5 * 1024 * 1024,
                            backupCount=3, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from shared import stock_shared as ss
from stock import catalog, sync


def seed() -> None:
    n = catalog.seed_catalog()
    logger.info("Catalog seeded/refreshed: %d items in acc_items.", n)


def tick() -> None:
    """One worker pass: ensure schema, sync (if the AppSheet client is wired), log the reorder list."""
    ss.init_stock_shared_db()

    client = sync.AppSheetClient()  # unconfigured until C2 connectivity is confirmed (owner)
    result = sync.run_sync(client)
    if result.get("synced"):
        logger.info("AppSheet sync: %d counts applied (%d changed).",
                    result["counts_applied"], result["changed"])
    else:
        logger.info("AppSheet sync skipped: %s.", result.get("reason"))

    rows = catalog.reorder_list()
    msg = catalog.order_brain.format_order_message(rows)
    if msg:
        logger.info("Reorder check:\n%s", msg)
    else:
        logger.info("Reorder check: nothing below minimum.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stock worker (headless).")
    ap.add_argument("--seed", action="store_true", help="seed/refresh the acc_items catalog and exit")
    args = ap.parse_args()
    if args.seed:
        seed()
    else:
        tick()


if __name__ == "__main__":
    main()
