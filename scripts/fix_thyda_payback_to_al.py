"""Owner instruction (2026-07-02): take Thyda's (id 34) ENTIRE current payback backlog from her AL
instead of making her work it back (part of setting her up as a payback_to_al staffer).

Her debt #158: owed 2250, paid 0 = **2250 min** still owed (reason 'paperless sick', accumulated from
2026-06-21). Verified authoritative (read-only): paid=0 is correct — every come-early payback slot
(06:00-12:00) credited 0 because she checked in at/after her noon shift start (06-27 384 late, 06-29
420 late, 06-30 569 late vs the 06:00 slot start); the 'done' bookings are came-normal 0-extension,
NOT a settle bug. No hidden credit missing.

Conversion (own-shift basis, the payback_to_al rule, owner-confirmed same as Vannary): 2250 min ÷
720-min shift (12:00-00:00) = **3.125 AL days**.

Three writes, ONE transaction (atomic; reversible S1):
  1. staff_registry.al_left 17.5 -> 17.5 - 3.125 = 14.375
  2. payback_debts #158: minutes_paid -> minutes_owed (2250), status='cleared'
  3. her still-'booked' 07-02 come-early slot: booking 'booked'->'cancelled' + redefine #322
     'approved'->'cancelled' (stop her working it back; with the debt cleared the auto-booker won't
     re-create come-early slots)

ABORTS unless the exact expected pre-state holds (debt owed=2250/paid=0/open, al_left=17.5, the
07-02 booking still 'booked'). Dry-run by default; --apply. Independent before/after read.

Reverse: al_left += 3.125 ; debt #158 minutes_paid=0,status='open' ; booking+redefine #322 back to
booked/approved.

Usage:  TWBSHOP_ENV=prod PYTHONPATH=. python scripts/fix_thyda_payback_to_al.py [--apply]
"""
import sys
sys.path.insert(0, r"C:\Users\Papa\twbshop")
from shared.database import _db

SID = 34
DEBT_ID = 158
REDEFINE_ID = 322
SLOT_DATE = "2026-07-02"
EXPECT_OWED, EXPECT_PAID = 2250, 0
EXPECT_AL = 17.5
AL_DAYS = 3.125          # 2250/720 = 3.125 exactly


def read(cur):
    cur.execute("SELECT minutes_owed, minutes_paid, status FROM payback_debts WHERE id=%s AND staff_id=%s",
                (DEBT_ID, SID))
    debt = cur.fetchone()
    cur.execute("SELECT COALESCE(al_left,0) AS al FROM staff_registry WHERE id=%s", (SID,))
    al = float(cur.fetchone()["al"])
    cur.execute("SELECT status FROM payback_bookings WHERE staff_id=%s AND slot_date=%s AND is_test=FALSE "
                "ORDER BY id", (SID, SLOT_DATE))
    bks = [r["status"] for r in cur.fetchall()]
    cur.execute("SELECT status FROM shift_changes WHERE id=%s", (REDEFINE_ID,))
    rd = cur.fetchone()
    return debt, al, bks, (rd["status"] if rd else None)


def main(apply: bool):
    with _db() as conn:
        with conn.cursor() as cur:
            debt, al, bks, rd = read(cur)
            print("BEFORE:")
            print("  debt#158:", dict(debt) if debt else None)
            print("  al_left:", al)
            print("  07-02 booking(s):", bks, "| redefine#322:", rd)

            if not debt or debt["minutes_owed"] != EXPECT_OWED or debt["minutes_paid"] != EXPECT_PAID \
                    or debt["status"] != "open":
                print("ABORT: debt #158 isn't owed=%d/paid=%d/open — re-investigate." % (EXPECT_OWED, EXPECT_PAID))
                return
            if abs(al - EXPECT_AL) > 1e-6:
                print("ABORT: al_left isn't %.3f (got %.3f) — re-investigate." % (EXPECT_AL, al))
                return
            if "booked" not in bks:
                print("ABORT: expected a still-'booked' 07-02 slot; got", bks, "— re-investigate.")
                return

            if not apply:
                print("\nDRY-RUN — would: al_left %.3f -> %.3f (-%.3f); clear debt #158 (paid->2250, cleared); "
                      "cancel 07-02 booking + redefine #322. Pass --apply." % (al, al - AL_DAYS, AL_DAYS))
                return

            cur.execute("UPDATE staff_registry SET al_left = al_left - %s, updated_at=NOW() "
                        "WHERE id=%s AND al_left=%s", (AL_DAYS, SID, EXPECT_AL))
            print("  al deducted rows:", cur.rowcount)
            cur.execute("UPDATE payback_debts SET minutes_paid=minutes_owed, status='cleared' "
                        "WHERE id=%s AND minutes_owed=%s AND minutes_paid=%s AND status='open'",
                        (DEBT_ID, EXPECT_OWED, EXPECT_PAID))
            print("  debt cleared rows:", cur.rowcount)
            cur.execute("UPDATE payback_bookings SET status='cancelled' "
                        "WHERE staff_id=%s AND slot_date=%s AND status='booked' AND is_test=FALSE",
                        (SID, SLOT_DATE))
            print("  booking cancelled rows:", cur.rowcount)
            cur.execute("UPDATE shift_changes SET status='cancelled' "
                        "WHERE id=%s AND status='approved'", (REDEFINE_ID,))
            print("  redefine cancelled rows:", cur.rowcount)

    with _db() as conn:                      # independent re-read
        with conn.cursor() as cur:
            debt, al, bks, rd = read(cur)
            print("\nAFTER (independent read):")
            print("  debt#158:", dict(debt))
            print("  al_left:", al)
            print("  07-02 booking(s):", bks, "| redefine#322:", rd)


if __name__ == "__main__":
    main("--apply" in sys.argv)
