"""VETTED DATA-FIX — Heng (staff 37) payback over-book + uncredited 7-min tail (owner Jun 21).

Run AFTER the session-51 GM deploy, in a quiet window. HIGH-RISK (payroll-adjacent): dry-run by
default; pass --apply to write. Prints BEFORE + AFTER from an INDEPENDENT re-read (separate connection).

What it does (debt #148, owed 96 / paid 89 / open 7):
  1. CANCEL the phantom Jun-21 89-min slot — booking #62 + shift_change #268 (the over-book; he never
     owed it — it was minted in the work->credit gap).
  2. CREDIT the worked 7-min Jun-20 tail (06:00-06:07, he checked out 06:07) that never posted.
  -> debt #148 becomes paid 96 == owed -> CLEARED. No phantom slot. Audit overbook clears.

Usage:
  TWBSHOP_ENV=prod python scripts/fix_heng_overbook.py            # dry-run (shows plan + BEFORE)
  TWBSHOP_ENV=prod python scripts/fix_heng_overbook.py --apply    # write + AFTER proof
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root on path

DEBT_ID = 148
BOOKING_ID = 62
SHIFT_CHANGE_ID = 268
CREDIT_MIN = 7


def _snap(cur):
    cur.execute("SELECT id, minutes_owed, minutes_paid, status FROM payback_debts WHERE id=%s", (DEBT_ID,))
    debt = cur.fetchone()
    cur.execute("SELECT id, slot_date, minutes, status FROM payback_bookings WHERE id=%s", (BOOKING_ID,))
    bk = cur.fetchone()
    cur.execute("SELECT id, when_date, status FROM shift_changes WHERE id=%s", (SHIFT_CHANGE_ID,))
    sc = cur.fetchone()
    return debt, bk, sc


def _show(tag, cur):
    debt, bk, sc = _snap(cur)
    print("\n--- %s ---" % tag)
    print("  debt #%s:" % DEBT_ID, dict(debt) if debt else None)
    print("  booking #%s:" % BOOKING_ID, dict(bk) if bk else None)
    print("  shift_change #%s:" % SHIFT_CHANGE_ID, dict(sc) if sc else None)


def main(apply: bool):
    from shared.database import _db
    # BEFORE (independent read)
    with _db() as conn:
        with conn.cursor() as cur:
            _show("BEFORE", cur)
            debt, _, _ = _snap(cur)
    if not debt or debt["status"] != "open":
        print("\n[ABORT] debt #%s is not open (already fixed?) — nothing to do." % DEBT_ID)
        return
    if not apply:
        print("\n[DRY-RUN] would: cancel booking #%s + shift_change #%s, credit %d min -> debt cleared."
              "\n          re-run with --apply to write." % (BOOKING_ID, SHIFT_CHANGE_ID, CREDIT_MIN))
        return
    # APPLY (one transaction)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE payback_bookings SET status='cancelled' WHERE id=%s AND status='booked'",
                        (BOOKING_ID,))
            cur.execute("UPDATE shift_changes SET status='cancelled' WHERE id=%s AND status='approved'",
                        (SHIFT_CHANGE_ID,))
            cur.execute("UPDATE payback_debts SET minutes_paid = minutes_paid + %s WHERE id=%s",
                        (CREDIT_MIN, DEBT_ID))
            cur.execute("SELECT minutes_owed, minutes_paid FROM payback_debts WHERE id=%s", (DEBT_ID,))
            r = cur.fetchone()
            if r["minutes_paid"] >= r["minutes_owed"]:
                cur.execute("UPDATE payback_debts SET status='cleared' WHERE id=%s", (DEBT_ID,))
        conn.commit()
    # AFTER (independent re-read, fresh connection)
    with _db() as conn:
        with conn.cursor() as cur:
            _show("AFTER (independent re-read)", cur)
    print("\n[DONE] Heng over-book fixed. Verify debt #%s = cleared, booking/sc = cancelled above." % DEBT_ID)


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
