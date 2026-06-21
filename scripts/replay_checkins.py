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

from shared.database import _db, staff_all
from core.db import init_core_db, ensure_org
from core.attendance import check_in
from core.shadow import compare_checkin

ORG = "twb"
TZ = "Asia/Phnom_Penh"


def _resolved_schedule(staff_dict, shift_date, base):
    """REDEFINE-AWARE schedule for a day: live's resolve_day knows the moved start (payback/OT slot).
    Returns (work_start, work_end) as HH:MM — the resolved start if the day was redefined, else the base.
    This is the shadow glue feeding the resolved schedule; the standalone core stays clean."""
    try:
        from gm_bot.attendance_ui import resolve_day
        dec = resolve_day(staff_dict, str(shift_date))
        if dec.get("working") and dec.get("start_min") is not None and dec.get("end_min") is not None:
            sm, em = int(dec["start_min"]) % 1440, int(dec["end_min"]) % 1440
            return "%02d:%02d" % (sm // 60, sm % 60), "%02d:%02d" % (em // 60, em % 60)
    except Exception:
        pass
    return base


def _live_state(minutes_late, minutes_early):
    if (minutes_late or 0) > 0:
        return "late"
    if (minutes_early or 0) > 0:
        return "early"
    return "on_time"


def main(days: int = 30):
    init_core_db()
    ensure_org(ORG, "TWBshop", TZ)
    staff_by_id = {s["id"]: s for s in staff_all(None)}   # full dicts for resolve_day (redefine-aware)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, work_start, work_end FROM staff_registry")
            sched = {r["id"]: (r["work_start"], r["work_end"]) for r in cur.fetchall()}
            # which (staff, date) had a REDEFINE (payback/OT slot moved the start) — to split the result
            cur.execute("SELECT DISTINCT staff_id, when_date FROM shift_changes "
                        "WHERE status IN ('approved','done')")
            redefine_days = {(r["staff_id"], str(r["when_date"])) for r in cur.fetchall()}
            # fresh replay: drop prior replay comparisons (keep the live-hook ones)
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s AND source='replay'", (ORG,))
            cur.execute("""SELECT staff_id, shift_date, checked_in_at, minutes_late, minutes_early
                           FROM attendance_sessions
                           WHERE checked_in_at IS NOT NULL AND is_test=FALSE
                             AND shift_date >= CURRENT_DATE - %s
                           ORDER BY checked_in_at""", (days,))
            rows = [dict(r) for r in cur.fetchall()]

    done = skipped = agree = 0
    norm_n = norm_ok = redef_n = redef_ok = 0   # split: normal-day vs redefine-day
    _norm_miss = []   # normal-day mismatch examples to characterize the remaining gap
    for r in rows:
        ws_we = sched.get(r["staff_id"])
        if not ws_we or not ws_we[0] or not ws_we[1]:
            skipped += 1
            continue
        # feed the REDEFINE-AWARE resolved schedule (the redefine port, measured with no core change/deploy)
        ws, we = _resolved_schedule(staff_by_id.get(r["staff_id"], {"id": r["staff_id"],
                                    "work_start": ws_we[0], "work_end": ws_we[1]}), r["shift_date"], ws_we)
        res = check_in(ORG, r["staff_id"], r["checked_in_at"], ws, we, TZ)
        ok = compare_checkin(ORG, r["staff_id"], _live_state(r["minutes_late"], r["minutes_early"]),
                             r["minutes_late"], r["minutes_early"], res, source="replay")
        done += 1
        agree += 1 if ok else 0
        if (r["staff_id"], str(r["shift_date"])) in redefine_days:
            redef_n += 1; redef_ok += 1 if ok else 0
        else:
            norm_n += 1; norm_ok += 1 if ok else 0
            if not ok:
                _norm_miss.append((str(r["shift_date"]), r["staff_id"],
                                   _live_state(r["minutes_late"], r["minutes_early"]),
                                   r["minutes_late"], r["minutes_early"], res.get("state"),
                                   res.get("minutes_late"), res.get("minutes_early")))
    print("replayed %d check-ins (last %d days) · %d agreed · %d mismatched · %d skipped (no schedule)"
          % (done, days, agree, done - agree, skipped))
    print("  SPLIT — normal days: %d/%d agree (%.0f%%) · redefine days: %d/%d agree (%.0f%%)"
          % (norm_ok, norm_n, (100.0 * norm_ok / norm_n if norm_n else 0),
             redef_ok, redef_n, (100.0 * redef_ok / redef_n if redef_n else 0)))
    if _norm_miss:
        print("  NORMAL-DAY mismatches (date · staff · live[state,L,E] -> new[state,L,E]):")
        for m in _norm_miss[:12]:
            print("    %s s%s live[%s,%s,%s] -> new[%s,%s,%s]" % m)
    from core.shadow import build_digest
    print("\n" + build_digest(ORG)["text"])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
