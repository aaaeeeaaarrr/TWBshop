"""Verify the tamper-evident audit hash-chain (core.audit) for one org or all orgs.

Recomputes every entry_hash and checks each previous_hash links to a real prior row → detects content edits and
row deletions. Exit 0 = all PASS, 1 = any FAIL. Run in a quiet window; read-only.

Usage:  TWBSHOP_ENV=prod python scripts/verify_audit_core.py [org_id]
"""
import sys

from core import audit
from shared.database import _db


def _all_orgs():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT DISTINCT org_id FROM core_audit ORDER BY org_id")
            return [r["org_id"] for r in cur.fetchall()]


def main():
    orgs = [sys.argv[1]] if len(sys.argv) > 1 else _all_orgs()
    bad = 0
    for o in orgs:
        v = audit.verify_chain(o)
        print("%-24s %s  (%d entries)" % (o, v["result"], v["checked"]))
        for f in v["failures"]:
            print("    - " + f)
        bad += 0 if v["result"] == "PASS" else 1
    print("---", "ALL PASS" if not bad else "%d org(s) FAILED" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
