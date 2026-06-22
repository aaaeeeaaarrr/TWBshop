"""Vetted data-fix (owner Jun 22): correct Long's #154 payback over-charge from the leave-early-sick bug.

His Jun-21 own-sick booked the FULL shift (540) as payback when he'd CHECKED IN and only left ~302 min
early — it should book the REMAINING tail (302), not the whole shift. So #154 is over by 238.
  Verified composition of owed 1094 = 540 (Jun-19 ABSENT sick, correct) + 14 (Jun-21 late check-in,
  correct) + 540 (Jun-21 sick, WRONG → should be 302).  Correct total = 540 + 14 + 302 = 856.

Sets #154 minutes_owed 1094 → 856. Booking #69 (540, Jun-23) stays ≤ 856 (no over-book). Dry-run by
default; --apply. Independent before/after read. ABORTS unless #154 is exactly owed=1094 / paid=0 and
its open bookings sum ≤ 856 (so a changed state forces a re-check, never a blind write).

Usage:  TWBSHOP_ENV=prod PYTHONPATH=. python scripts/fix_long_payback.py [--apply]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.database import _db

DEBT_ID = 154
STAFF_ID = 1
EXPECT_OWED = 1094
CORRECT_OWED = 856   # 540 (Jun-19) + 14 (Jun-21 late) + 302 (Jun-21 sick remaining)


def _read(cur):
    cur.execute("SELECT minutes_owed, minutes_paid, status FROM payback_debts WHERE id=%s AND staff_id=%s",
                (DEBT_ID, STAFF_ID))
    debt = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(minutes),0) b FROM payback_bookings "
                "WHERE debt_id=%s AND status='booked'", (DEBT_ID,))
    booked = cur.fetchone()["b"]
    return debt, int(booked)


def main(apply: bool):
    with _db() as conn:
        with conn.cursor() as cur:
            debt, booked = _read(cur)
            print("BEFORE: debt", dict(debt) if debt else None, "| open bookings sum:", booked)
            if not debt or debt["minutes_owed"] != EXPECT_OWED or debt["minutes_paid"] != 0:
                print("ABORT: #154 isn't the expected owed=%d/paid=0 — re-investigate before writing." % EXPECT_OWED)
                return
            if booked > CORRECT_OWED:
                print("ABORT: open bookings (%d) exceed the corrected owed (%d) — would over-book." % (booked, CORRECT_OWED))
                return
            if not apply:
                print("DRY-RUN — pass --apply to set owed %d → %d (removes the 238 over-charge)." % (EXPECT_OWED, CORRECT_OWED))
                return
            cur.execute("UPDATE payback_debts SET minutes_owed=%s WHERE id=%s AND staff_id=%s AND minutes_owed=%s",
                        (CORRECT_OWED, DEBT_ID, STAFF_ID, EXPECT_OWED))
            print("updated rows:", cur.rowcount)
    with _db() as conn:                                  # independent re-read
        with conn.cursor() as cur:
            debt, booked = _read(cur)
            print("AFTER (independent read): debt", dict(debt), "| open bookings sum:", booked)


if __name__ == "__main__":
    main("--apply" in sys.argv)
