"""Seed acc_vendors from scripts/vendor_seed.py.

Idempotent — vendor_link() upserts on tg_group_id, so re-running only refreshes.
Dormant vendors are seeded with active=FALSE (kept for the price-broadcast feature but
out of the active payable run). Run with TWBSHOP_ENV=staging in dev; prod runs it at
accountant go-live.

    TWBSHOP_ENV=staging python scripts/seed_vendors.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # repo root
sys.path.insert(0, HERE)                    # scripts/

from accountant.db import init_accounting_db, vendor_link, list_vendors
from shared.database import _db
from vendor_seed import VENDORS


def main():
    env = os.environ.get("TWBSHOP_ENV", "(unset)")
    init_accounting_db()
    before = len(list_vendors(active_only=False))

    dormant = []
    for name, gid, cat, status in VENDORS:
        vendor_link(name, gid, cat)          # active=TRUE on upsert
        if status == "dormant":
            dormant.append(gid)

    if dormant:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE acc_vendors SET active=FALSE WHERE tg_group_id = ANY(%s)",
                    (dormant,),
                )

    after = len(list_vendors(active_only=False))
    active = len(list_vendors(active_only=True))
    print(f"env={env}  before={before}  after={after}  active={active}  dormant={after - active}")


if __name__ == "__main__":
    main()
