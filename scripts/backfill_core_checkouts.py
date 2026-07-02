"""Backfill the platform core's MISSING checked_out events from the LIVE attendance_sessions truth
(one-off; observability flow tier, 2026-07-03). flowcheck's first prod catch: the live→core shadow
feed was check-in-only, so every platform session sat incomplete. The forward feed is now hooked into
`att_check_out`; this completes the HISTORICAL sessions using the real checkout instants the live
system already recorded — truthful data, no invention. A core check-in whose LIVE session has no
checkout (genuinely never closed) is left alone and reported.

Idempotent (checked_out is UNIQUE per shift; a re-run writes nothing new). Shadow-side tables only —
touches NOTHING the live system owns. DRY-RUN by default; --apply writes.

Usage:  TWBSHOP_ENV=prod python scripts/backfill_core_checkouts.py [--apply]
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import _db

ORG = "twb"


def missing_checkouts() -> list:
    """Core checked_in events with NO checked_out on their shift, joined to their shift labels."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.shift_id, e.staff_id, s.business_day
                FROM attendance_events e JOIN shifts s ON s.shift_id = e.shift_id
                WHERE e.org_id=%s AND e.type='checked_in'
                  AND NOT EXISTS (SELECT 1 FROM attendance_events o
                                  WHERE o.shift_id=e.shift_id AND o.type='checked_out')
                ORDER BY s.business_day, e.staff_id
            """, (ORG,))
            return [dict(r) for r in cur.fetchall()]


def live_checkout_for(staff_id: int, day_iso: str):
    """The live system's recorded checkout instant for that staff-day (non-test), or None."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT checked_out_at FROM attendance_sessions
                           WHERE staff_id=%s AND shift_date=%s AND is_test=FALSE
                             AND checked_out_at IS NOT NULL""", (staff_id, day_iso))
            r = cur.fetchone()
            return r["checked_out_at"] if r else None


def main() -> int:
    apply = "--apply" in sys.argv
    from core.attendance import check_out
    from shared.database import staff_all
    hours = {s["id"]: (s.get("work_start"), s.get("work_end")) for s in staff_all("active")}
    todo = missing_checkouts()
    done = skipped_no_live = skipped_no_staff = unbound = 0
    print("%d core session(s) missing a checkout%s" % (len(todo), "" if apply else " [DRY-RUN]"))
    for m in todo:
        day = str(m["business_day"])
        live_at = live_checkout_for(m["staff_id"], day)
        if live_at is None:
            skipped_no_live += 1
            print("  · shift %s staff %s %s — live has NO checkout either (left incomplete, flowcheck "
                  "will flag it)" % (m["shift_id"], m["staff_id"], day))
            continue
        ws, we = hours.get(m["staff_id"], (None, None))
        if not ws:
            skipped_no_staff += 1
            print("  · shift %s staff %s — not in the active registry (skipped)" % (m["shift_id"], m["staff_id"]))
            continue
        when = live_at if isinstance(live_at, datetime) else datetime.fromisoformat(str(live_at))
        if apply:
            res = check_out(ORG, m["staff_id"], when, ws, we)
            if res.get("bound"):
                done += 1
                print("  ✓ shift %s staff %s %s → checked_out fed (worked %s min)"
                      % (m["shift_id"], m["staff_id"], day, res.get("worked_min")))
            else:
                unbound += 1
                print("  ✗ shift %s staff %s %s — did not bind (%s)"
                      % (m["shift_id"], m["staff_id"], day, res.get("reason")))
        else:
            done += 1
            print("  → shift %s staff %s %s would feed checkout %s" % (m["shift_id"], m["staff_id"], day, when))
    print("summary: %s=%d · no-live-checkout=%d · not-active=%d · unbound=%d"
          % ("fed" if apply else "would-feed", done, skipped_no_live, skipped_no_staff, unbound))
    if apply:   # independent re-read: how many are STILL missing after the writes settled?
        print("re-read: %d still missing" % len(missing_checkouts()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
