"""Owner one-off (2026-07-01): take Vannary's (id 17) remaining PAYBACK from her AL instead of
making her work it back.

Her debt #163: owed 644, paid 60, balance = 584 min still owed (verified: the 60 paid = the 06-28
stay-late slot she actually worked; the 06-30 come-early slot credited 0 because she came at her
normal 06:00, not 02:00 — no settle bug, 584 is authoritative).

Conversion (owner rule = the payback_to_al basis: owed-min ÷ their OWN shift, full shift = 1.0 AL):
    584 min ÷ 840-min shift (06:00-20:00, her real ~14h shift) = 0.695 → 0.70 AL days.

Three writes, ONE transaction (atomic; reversible S1):
  1. staff_registry.al_left 17.0 -> 17.0 - AL_DAYS         (deduct the AL)
  2. payback_debts #163: minutes_paid -> minutes_owed, status='cleared'  (clear the debt)
  3. her still-open 07-01 come-early slot: booking 'booked'->'cancelled' + redefine #320
     'approved'->'cancelled'  (stop her working it back AND stop a false 241-late tonight; with
     the debt cleared the daily auto-booker won't re-create come-early slots)

ABORTS unless the exact expected pre-state holds (debt owed=644/paid=60/open, al_left=17.0, the
07-01 booking still 'booked') so any drift forces a re-check, never a blind write. Dry-run by
default; pass --apply. Independent before/after read from a fresh connection.

Reverse (if ever needed): al_left += AL_DAYS ; debt #163 minutes_paid=60,status='open' ;
booking+redefine #320 back to booked/approved.

Usage:  TWBSHOP_ENV=prod PYTHONPATH=. python scripts/fix_vannary_payback_to_al.py [--apply]
"""
import sys
sys.path.insert(0, r"C:\Users\Papa\twbshop")
from shared.database import _db

SID = 17
DEBT_ID = 163
REDEFINE_ID = 320
SLOT_DATE = "2026-07-01"
EXPECT_OWED, EXPECT_PAID = 644, 60
EXPECT_AL = 17.0
AL_DAYS = 0.70          # 584/840 = 0.695 -> 0.70


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
            print("  debt#163:", dict(debt) if debt else None)
            print("  al_left:", al)
            print("  07-01 booking(s):", bks, "| redefine#320:", rd)

            if not debt or debt["minutes_owed"] != EXPECT_OWED or debt["minutes_paid"] != EXPECT_PAID \
                    or debt["status"] != "open":
                print("ABORT: debt #163 isn't owed=%d/paid=%d/open — re-investigate." % (EXPECT_OWED, EXPECT_PAID))
                return
            if abs(al - EXPECT_AL) > 1e-6:
                print("ABORT: al_left isn't %.2f (got %.2f) — re-investigate." % (EXPECT_AL, al))
                return
            if "booked" not in bks:
                print("ABORT: expected a still-'booked' 07-01 slot; got", bks, "— re-investigate.")
                return

            if not apply:
                print("\nDRY-RUN — would: al_left %.2f -> %.2f (-%.2f); clear debt #163 (paid->644, cleared); "
                      "cancel 07-01 booking + redefine #320. Pass --apply." % (al, al - AL_DAYS, AL_DAYS))
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
            print("  debt#163:", dict(debt))
            print("  al_left:", al)
            print("  07-01 booking(s):", bks, "| redefine#320:", rd)


if __name__ == "__main__":
    main("--apply" in sys.argv)
