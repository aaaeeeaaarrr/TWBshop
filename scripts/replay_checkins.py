"""REPLAY accelerator (owner Jun 22 — "days instead of weeks").

Reads recent LIVE check-ins (attendance_sessions) and runs each through the NEW core, comparing to the
verdict live already recorded — so weeks of real data are compared in one run, instead of waiting for
check-ins to trickle in. READ-ONLY on live (only reads sessions + staff); writes ONLY to the isolated
shadow tables (source='replay'). Re-runnable: clears prior replay rows first.

CAVEAT: it uses each staff's CURRENT schedule, so a check-in from before a schedule change is compared
against today's hours (approximate for old rows). Default window = 30 days, where schedules are stable.
Expected mismatches: days with a redefine (payback/OT slot moved the start) or live grace/sick-waiver —
the core slice doesn't model those yet, so the digest groups them as "known, not-yet-ported."

Usage:  TWBSHOP_ENV=prod PYTHONPATH=. python scripts/replay_checkins.py [days]
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import _db
from core.db import init_core_db, ensure_org
from core.attendance import check_in
from core.shadow import compare_checkin

ORG = "twb"
TZ = "Asia/Phnom_Penh"


def _live_state(minutes_late, minutes_early):
    if (minutes_late or 0) > 0:
        return "late"
    if (minutes_early or 0) > 0:
        return "early"
    return "on_time"


def main(days: int = 30):
    init_core_db()
    ensure_org(ORG, "TWBshop", TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, work_start, work_end FROM staff_registry")
            sched = {r["id"]: (r["work_start"], r["work_end"]) for r in cur.fetchall()}
            # fresh replay: drop prior replay comparisons (keep the live-hook ones)
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s AND source='replay'", (ORG,))
            cur.execute("""SELECT staff_id, checked_in_at, minutes_late, minutes_early
                           FROM attendance_sessions
                           WHERE checked_in_at IS NOT NULL AND is_test=FALSE
                             AND shift_date >= CURRENT_DATE - %s
                           ORDER BY checked_in_at""", (days,))
            rows = [dict(r) for r in cur.fetchall()]

    done = skipped = agree = 0
    for r in rows:
        ws_we = sched.get(r["staff_id"])
        if not ws_we or not ws_we[0] or not ws_we[1]:
            skipped += 1
            continue
        res = check_in(ORG, r["staff_id"], r["checked_in_at"], ws_we[0], ws_we[1], TZ)
        ok = compare_checkin(ORG, r["staff_id"], _live_state(r["minutes_late"], r["minutes_early"]),
                             r["minutes_late"], r["minutes_early"], res, source="replay")
        done += 1
        agree += 1 if ok else 0
    print("replayed %d check-ins (last %d days) · %d agreed · %d mismatched · %d skipped (no schedule)"
          % (done, days, agree, done - agree, skipped))
    from core.shadow import build_digest
    print("\n" + build_digest(ORG)["text"])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
