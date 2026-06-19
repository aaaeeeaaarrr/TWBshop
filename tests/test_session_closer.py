"""Fallback end-of-shift session closer (gm_bot.bot) — go-live hardening.

Auto-checkout only fires if the live-share is still ON + IN-ZONE at shift end; staff routinely stop
sharing early, so a checked-in session otherwise dangles OPEN forever (the audit flags it 'stale' after
2 days, and it recurs daily). The closer closes such a session at the RESOLVED shift end and settles
exactly like auto-checkout (a no-op for a normal shift).

Pure overnight end-time math is proven directly; the find→close round-trip is proven against the
isolated staging DB on a throwaway staff row (same pattern as test_al_atomic), torn down in finally.
"""
from datetime import date, timedelta

import shared.database as db
from gm_bot.bot import _shift_end_from_mins, _shift_end_dt


# ── pure shift-end math (overnight-aware) ──────────────────────────────────

def test_end_from_mins_normal_day():
    assert _shift_end_from_mins("2026-06-16", 7 * 60, 17 * 60).isoformat().startswith("2026-06-16T17:00")


def test_end_from_mins_overnight_lands_next_day():
    # 21:00 → 06:00 ends the NEXT calendar day
    assert _shift_end_from_mins("2026-06-16", 21 * 60, 6 * 60).isoformat().startswith("2026-06-17T06:00")


def test_end_from_mins_empty_or_missing_is_none():
    assert _shift_end_from_mins("2026-06-16", 9 * 60, 9 * 60) is None     # zero-length window
    assert _shift_end_from_mins("2026-06-16", None, 17 * 60) is None      # missing time


# ── resolve-driven end: a fresh id has no AL/sick ⇒ normal schedule ────────
# (read-only: resolve_day queries by staff_id and finds nothing, so it uses the passed work hours.)

def _not_off(day_iso):
    wd = date.fromisoformat(day_iso).strftime("%a")
    return "Sun" if wd != "Sun" else "Mon"


def test_end_dt_normal_working_day():
    d = "2026-06-16"
    staff = {"id": 990901, "work_start": "07:00", "work_end": "17:00", "day_off": _not_off(d)}
    assert _shift_end_dt(staff, d).isoformat().startswith(d + "T17:00")


def test_end_dt_overnight_working_day():
    d = "2026-06-16"
    staff = {"id": 990902, "work_start": "21:00", "work_end": "06:00", "day_off": _not_off(d)}
    assert _shift_end_dt(staff, d).isoformat().startswith("2026-06-17T06:00")


def test_end_dt_day_off_still_closes_at_normal_hours():
    # a session EXISTS on a resolver-day-off (they picked up the shift, e.g. go-live day) ⇒ a check-in
    # means they worked, so close at their normal end — NOT skip (which would dangle it forever).
    d = "2026-06-16"
    off = date.fromisoformat(d).strftime("%a")          # their day off = this weekday
    staff = {"id": 990903, "work_start": "07:00", "work_end": "17:00", "day_off": off}
    assert _shift_end_dt(staff, d).isoformat().startswith(d + "T17:00")


def test_end_dt_none_only_when_no_work_hours():
    d = "2026-06-16"
    staff = {"id": 990904, "work_start": None, "work_end": None, "day_off": "Sun"}
    assert _shift_end_dt(staff, d) is None              # genuine data gap ⇒ skip rather than guess


# ── find → close round-trip on the isolated staging DB ─────────────────────

def _seed_staff(name, work_start="07:00", work_end="17:00", day_off="Sun"):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM staff_registry WHERE canonical_name=%s", (name,))
            cur.execute("INSERT INTO staff_registry (canonical_name, status, work_start, work_end, day_off) "
                        "VALUES (%s,'active',%s,%s,%s) RETURNING id", (name, work_start, work_end, day_off))
            return cur.fetchone()["id"]


def _teardown(sid):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM attendance_sessions WHERE staff_id=%s", (sid,))
            cur.execute("DELETE FROM staff_registry WHERE id=%s", (sid,))


def test_open_past_session_found_then_closed_and_excluded():
    sid = _seed_staff("ZZ_CLOSER_FOUND")
    sd = (date.today() - timedelta(days=3)).isoformat()
    today = date.today().isoformat()
    try:
        db.att_check_in(sid, sd, "2026-06-16T07:01:00+07:00", True)        # checked in, never out
        assert sid in [r["staff_id"] for r in db.att_open_past_sessions(today, is_test=False)]
        # the closer's action: close at the resolved shift end
        db.att_check_out(sid, sd, "2026-06-16T17:00:00+07:00")
        s = db.att_get_session(sid, sd)
        assert s["status"] == "closed" and s["checked_out_at"] is not None
        assert sid not in [r["staff_id"] for r in db.att_open_past_sessions(today, is_test=False)]
    finally:
        _teardown(sid)


def test_todays_open_session_is_not_closeable():
    sid = _seed_staff("ZZ_CLOSER_TODAY")
    sd = date.today().isoformat()                                          # TODAY ⇒ shift not ended
    try:
        db.att_check_in(sid, sd, "2026-06-16T07:01:00+07:00", True)
        assert sid not in [r["staff_id"] for r in db.att_open_past_sessions(date.today().isoformat(),
                                                                            is_test=False)]
    finally:
        _teardown(sid)


def test_already_checked_out_session_is_not_returned():
    sid = _seed_staff("ZZ_CLOSER_DONE")
    sd = (date.today() - timedelta(days=3)).isoformat()
    try:
        db.att_check_in(sid, sd, "2026-06-16T07:01:00+07:00", True)
        db.att_check_out(sid, sd, "2026-06-16T17:00:00+07:00")
        # a closed session never appears (and a second close is a harmless no-op on an excluded row)
        assert sid not in [r["staff_id"] for r in db.att_open_past_sessions(date.today().isoformat(),
                                                                            is_test=False)]
    finally:
        _teardown(sid)
