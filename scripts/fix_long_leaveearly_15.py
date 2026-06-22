"""Vetted data-fix (owner Jun 22): remove Long's ERRONEOUS Jun-21 −15 late_sick_inform (points_events
id 138). Long CHECKED IN (came to work) then fell ill mid-shift = leave-early sick → the −15 (for
late-informing an ABSENCE) does not apply. His Jun-19 −15 (id 130) is a GENUINE absence → KEPT.

Dry-run by default; --apply to execute. Independent before/after read (separate connection). Aborts if
the target row isn't exactly the expected erroneous −15. Run AFTER the audit-exemption deploy so the
live watchdog never flags case #51 as 'missing −15'.

Usage:  TWBSHOP_ENV=prod PYTHONPATH=. python scripts/fix_long_leaveearly_15.py [--apply]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.database import _db

STAFF_ID = 1
EVENT_ID = 138   # late_sick_inform, ref 2026-06-21 (the leave-early one)


def _points(cur):
    cur.execute("SELECT cause, COUNT(*) n, SUM(quantity) q FROM points_events "
                "WHERE staff_id=%s AND is_test=false GROUP BY cause ORDER BY cause", (STAFF_ID,))
    return {r["cause"]: (r["n"], int(r["q"])) for r in cur.fetchall()}


def main(apply: bool):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, cause, quantity, ref FROM points_events WHERE id=%s AND staff_id=%s",
                        (EVENT_ID, STAFF_ID))
            row = cur.fetchone()
            print("target row:", dict(row) if row else "NOT FOUND")
            if not row or row["cause"] != "late_sick_inform" or str(row["ref"]) != "2026-06-21":
                print("ABORT: row doesn't match the expected erroneous −15 (id 138 / late_sick_inform / 2026-06-21)")
                return
            print("BEFORE:", _points(cur))
            if not apply:
                print("DRY-RUN — pass --apply to delete (removes 1 late_sick_inform = +15 to Long's net).")
                return
            cur.execute("DELETE FROM points_events WHERE id=%s AND staff_id=%s "
                        "AND cause='late_sick_inform' AND ref='2026-06-21' AND is_test=false",
                        (EVENT_ID, STAFF_ID))
            print("deleted rows:", cur.rowcount)
    with _db() as conn:                                  # independent re-read, separate connection
        with conn.cursor() as cur:
            print("AFTER (independent read):", _points(cur))


if __name__ == "__main__":
    main("--apply" in sys.argv)
