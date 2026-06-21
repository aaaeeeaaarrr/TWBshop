"""core.attendance — channel-agnostic CHECK-IN / CHECK-OUT commands.

Pure domain: takes (org, staff, when, the staff's schedule) and returns a verdict + emits an event. NO
Telegram/web/app types in here — a channel adapter calls these and renders the result. The verdict is
pure INTERVAL math against the shift's start_dt (never a calendar-date comparison). Events are idempotent
(one check-in / one check-out per shift — the UNIQUE index is the claim).
"""
import json
from datetime import timedelta
from zoneinfo import ZoneInfo

from shared.database import _db
from core.shifts import ensure_shift, shift_for_instant


def _emit_event(org_id, shift_id, staff_id, etype, at, detail) -> bool:
    """Append an event; idempotent for checked_in/checked_out via the UNIQUE(shift_id,type) index.
    Returns True if this call inserted it, False if it was already there (a duplicate / redelivery)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO attendance_events (org_id, shift_id, staff_id, type, at, detail)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT DO NOTHING RETURNING event_id""",
                        (org_id, shift_id, staff_id, etype, at, json.dumps(detail, default=str)))
            return cur.fetchone() is not None


def _bind_shift(org_id, staff_id, when_dt, work_start, work_end, tz):
    """Materialize the candidate shifts (the local day + the day before, in tz) then bind `when_dt` to one
    by interval — overnight-correct: a 2am check-in binds to yesterday's still-running shift."""
    local_day = when_dt.astimezone(ZoneInfo(tz)).date()
    for d in (local_day, local_day - timedelta(days=1)):
        ensure_shift(org_id, staff_id, d, work_start, work_end, tz)
    return shift_for_instant(org_id, staff_id, when_dt)


def check_in(org_id, staff_id, when_dt, work_start, work_end,
             tz: str = "Asia/Phnom_Penh", location=None) -> dict:
    """Bind the check-in to its shift + return the verdict (state + minutes), emitting one checked_in
    event. Verdict is pure: minutes vs the shift's real start_dt. `when_dt` must be tz-aware (UTC)."""
    shift = _bind_shift(org_id, staff_id, when_dt, work_start, work_end, tz)
    if not shift:
        return {"bound": False, "reason": "no shift near this instant"}
    diff_min = round((when_dt - shift["start_dt"]).total_seconds() / 60.0)
    late = max(0, diff_min)
    early = max(0, -diff_min)
    state = "late" if late > 0 else ("early" if early > 0 else "on_time")
    inserted = _emit_event(org_id, shift["shift_id"], staff_id, "checked_in", when_dt,
                           {"minutes_late": late, "minutes_early": early, "state": state,
                            "location": location})
    return {"bound": True, "shift_id": shift["shift_id"], "business_day": str(shift["business_day"]),
            "state": state, "minutes_late": late, "minutes_early": early, "duplicate": not inserted}


def check_out(org_id, staff_id, when_dt, work_start, work_end, tz: str = "Asia/Phnom_Penh") -> dict:
    """Bind the check-out to its shift + emit one checked_out event with worked minutes (capped at the
    shift end — lingering past end banks nothing, mirroring live). Pure interval math."""
    shift = _bind_shift(org_id, staff_id, when_dt, work_start, work_end, tz)
    if not shift:
        return {"bound": False, "reason": "no shift near this instant"}
    end_for_calc = min(when_dt, shift["end_dt"])
    # worked = from the check-in (if recorded) else the shift start, to the (capped) checkout
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT at FROM attendance_events WHERE shift_id=%s AND type='checked_in'""",
                        (shift["shift_id"],))
            r = cur.fetchone()
    ci = r["at"] if r else shift["start_dt"]
    worked = max(0, round((end_for_calc - max(ci, shift["start_dt"])).total_seconds() / 60.0))
    inserted = _emit_event(org_id, shift["shift_id"], staff_id, "checked_out", when_dt,
                           {"worked_min": worked})
    return {"bound": True, "shift_id": shift["shift_id"], "worked_min": worked,
            "duplicate": not inserted}
