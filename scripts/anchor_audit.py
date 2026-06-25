"""Anchor every org's audit-chain HEAD to the external anchor file (core.audit_anchor). Run on a schedule
(e.g. nightly cron) and copy the anchor file OFFSITE — that's what makes a DB-admin re-chain detectable.

Usage:  TWBSHOP_ENV=prod python scripts/anchor_audit.py
Set ANCHOR_DIR (where the file lives, off the DB host) and ANCHOR_HMAC_KEY (in secrets) for production.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root on path (run from scripts/)

from core import audit_anchor
from shared.database import _db


def _orgs():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT DISTINCT org_id FROM core_audit ORDER BY org_id")
            return [r["org_id"] for r in cur.fetchall()]


def main():
    signed = False
    n = 0
    for o in _orgs():
        rec = audit_anchor.anchor_head(o)
        signed = rec.get("sig") is not None
        n += 1
        print("%-24s head=%s…  count=%d" % (o, str(rec["head_hash"])[:12], rec["count"]))
    print("--- anchored %d org(s) %s" % (n, "(HMAC-signed)" if signed else "(PLAINTEXT — set ANCHOR_HMAC_KEY)"))


if __name__ == "__main__":
    main()
