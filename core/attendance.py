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


def verdict(when_dt, start_dt, tz: str = "Asia/Phnom_Penh",
            grace_min: int = 5, early_bonus_min: int = 5) -> tuple:
    """(state, minutes_late, minutes_early) for a check-in instant vs the shift start. PARITY with live
    (gm_bot/checkin.verdict): minute-of-day truncation (drop seconds), a GRACE for small lateness, and an
    EARLY threshold — within grace either side = 'on_time' with 0/0. grace_min/early_bonus_min are
    per-tenant config (TWB = 5/5); pure (no DB). Circle math handles overnight by construction."""
    z = ZoneInfo(tz)
    wl, sl = when_dt.astimezone(z), start_dt.astimezone(z)
    rel = ((wl.hour * 60 + wl.minute) - (sl.hour * 60 + sl.minute)) % 1440
    if rel == 0:
        early = late = 0
    elif rel > 720:                       # before the start = early
        early, late = 1440 - rel, 0
    else:
        early, late = 0, rel
    if early >= early_bonus_min:
        return "early", 0, early
    if late > grace_min:
        return "late", late, 0
    return "on_time", 0, 0


def check_in(org_id, staff_id, when_dt, work_start, work_end,
             tz: str = "Asia/Phnom_Penh", location=None,
             grace_min: int = 5, early_bonus_min: int = 5) -> dict:
    """Bind the check-in to its shift + return the verdict (state + minutes), emitting one checked_in
    event. Verdict matches live (grace/early thresholds, minute-of-day). `when_dt` must be tz-aware."""
    shift = _bind_shift(org_id, staff_id, when_dt, work_start, work_end, tz)
    if not shift:
        return {"bound": False, "reason": "no shift near this instant"}
    state, late, early = verdict(when_dt, shift["start_dt"], tz, grace_min, early_bonus_min)
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
