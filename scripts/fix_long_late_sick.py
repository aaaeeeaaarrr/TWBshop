"""VETTED DATA-FIX — Long (staff 1) retroactive -15 late-sick-informing (owner Jun 21).

Long filed own-sick Jun 19 at 20:55 (5 min before his 21:00 shift) but the -15 never fired (the
self-cancellation bug, fixed in d09e00c). Owner decision: apply -15 to LONG + going-forward (no other
retro). Run AFTER the session-51 GM deploy. HIGH-RISK: dry-run by default; --apply to write.

What it does:
  1. RECORD the missed -15: points_event late_sick_inform for Long, dated 2026-06-19 (idempotent — skips
     if one already exists for that date).
  2. Set the idempotency + deferred-notice flags so the bot TEACHES Long the -15 at his NEXT check-in
     (the built late-informing message), and his existing 540-min paperless-sick payback (debt #154) is
     offered by the normal check-in/ladder flow. (No separate send needed — both ride the built paths.)
  Prints BEFORE + AFTER from an independent re-read.

Usage:
  TWBSHOP_ENV=prod python scripts/fix_long_late_sick.py            # dry-run
  TWBSHOP_ENV=prod python scripts/fix_long_late_sick.py --apply    # write + proof
"""
import sys

STAFF_ID = 1
UID = 5961683250
THE_DATE = "2026-06-19"


def _events(cur):
    cur.execute("SELECT id, cause, quantity, ref FROM points_events "
                "WHERE staff_id=%s AND cause='late_sick_inform' ORDER BY id", (STAFF_ID,))
    return [dict(r) for r in cur.fetchall()]


def main(apply: bool):
    from shared.database import _db
    with _db() as conn:
        with conn.cursor() as cur:
            existing = _events(cur)
    print("BEFORE — Long late_sick_inform events:", existing)
    if any(e.get("ref") == THE_DATE for e in existing):
        print("[ABORT] a -15 for %s already exists — nothing to do (idempotent)." % THE_DATE)
        return
    if not apply:
        print("\n[DRY-RUN] would record -15 late_sick_inform for Long dated %s + set the deferred-notice"
              "\n          flag (taught at next check-in). Re-run with --apply." % THE_DATE)
        return
    from shared.database import points_record, gm_set_state
    points_record(STAFF_ID, "late_sick_inform", 1, THE_DATE)
    gm_set_state("late_inform_done:%d:%s" % (STAFF_ID, THE_DATE), "true")
    import datetime
    gm_set_state("late_inform_notice:%d" % UID, datetime.date.today().isoformat())
    # AFTER (independent re-read)
    with _db() as conn:
        with conn.cursor() as cur:
            print("\nAFTER (independent re-read) — Long late_sick_inform events:", _events(cur))
    print("[DONE] -15 recorded. The bot will TEACH Long at his next check-in + offer his 540 payback.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
