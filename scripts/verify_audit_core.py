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
    do_anchors = "--anchors" in sys.argv[1:]                  # also verify the external anchor file
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    orgs = [pos[0]] if pos else _all_orgs()
    bad = 0
    for o in orgs:
        v = audit.verify_chain(o)
        print("%-24s chain  %s  (%d entries)" % (o, v["result"], v["checked"]))
        for f in v["failures"]:
            print("    - " + f)
        bad += 0 if v["result"] == "PASS" else 1
        if do_anchors:
            from core import audit_anchor
            a = audit_anchor.verify_anchors(o)
            print("%-24s anchor %s  (%d anchored)" % (o, a["result"], a["checked"]))
            for f in a["failures"]:
                print("    - " + f)
            bad += 0 if a["result"] == "PASS" else 1
    print("---", "ALL PASS" if not bad else "%d FAILED" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
