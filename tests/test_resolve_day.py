"""Phase 1a of the unified schedule-event model (docs/SCHEDULE_RESOLUTION_MODEL.md): resolve_day()
precedence, proven on staging. Additive — nothing is repointed yet, so this changes no behavior.
"""
import json
from datetime import date

import psycopg2.extras
import pytest

import shared.database as db
from gm_bot import attendance_ui as ui

WORKDAY = "2099-08-03"          # a normal working day (day_off is set to OFFDAY's weekday)
OFFDAY = "2099-08-04"           # the staffer's weekly day-off
OFF_WD = date.fromisoformat(OFFDAY).strftime("%a")   # e.g. "Tue"


@pytest.fixture
def staff():
    with db._db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM staff_registry WHERE canonical_name='ZZ_RESOLVE'")
        cur.execute("INSERT INTO staff_registry (canonical_name, status, work_start, work_end, day_off) "
                    "VALUES ('ZZ_RESOLVE','active','08:00','17:00',%s) RETURNING id", (OFF_WD,))
        sid = cur.fetchone()["id"]
    p = {"id": sid, "work_start": "08:00", "work_end": "17:00", "day_off": OFF_WD}
    yield p
    with db._db() as c, c.cursor() as cur:
        for t in ("al_requests", "sick_cases", "special_leaves", "shift_changes", "dayoff_overrides"):
            cur.execute(f"DELETE FROM {t} WHERE staff_id=%s", (sid,))
        cur.execute("DELETE FROM staff_registry WHERE id=%s", (sid,))


def _al(sid, days):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, is_test) "
                    "VALUES (%s,'days',%s,'approved',FALSE)", (sid, json.dumps(days)))


def _redefine(sid, day, start=600, end=900):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO shift_changes (senior_id, staff_id, when_date, start_min, end_min, "
                    "normal_len, status, is_test) VALUES (%s,%s,%s,%s,%s,540,'approved',FALSE)",
                    (sid, sid, day, start, end))


def _sick(sid, day):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO sick_cases (staff_id, who, the_date, status, is_test) "
                    "VALUES (%s,'me',%s,'open',FALSE)", (sid, day))


def _override(sid, day, kind):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO dayoff_overrides (staff_id, the_date, kind, is_test) "
                    "VALUES (%s,%s,%s,FALSE)", (sid, day, kind))


def test_normal_working_day(staff):
    d = ui.resolve_day(staff, WORKDAY)
    assert d["working"] and d["reason"] == "normal" and d["start_min"] == 480 and d["end_min"] == 1020


def test_weekly_day_off(staff):
    d = ui.resolve_day(staff, OFFDAY)
    assert not d["working"] and d["reason"] == "day_off"


def test_approved_al_is_away(staff):
    _al(staff["id"], [WORKDAY])
    d = ui.resolve_day(staff, WORKDAY)
    assert not d["working"] and d["reason"] == "al"


def test_al_BEATS_a_coexisting_redefine(staff):
    # BUG 1 FIX: a redefine must NOT silently override approved AL — leave is protected.
    _al(staff["id"], [WORKDAY])
    _redefine(staff["id"], WORKDAY)
    d = ui.resolve_day(staff, WORKDAY)
    assert not d["working"] and d["reason"] == "al"


def test_sick_is_away(staff):
    # BUG 2 FIX: sick now touches the resolver.
    _sick(staff["id"], WORKDAY)
    d = ui.resolve_day(staff, WORKDAY)
    assert not d["working"] and d["reason"] == "sick"


def test_redefine_beats_day_off_change_day(staff):
    _redefine(staff["id"], OFFDAY, start=600, end=900)
    d = ui.resolve_day(staff, OFFDAY)
    assert d["working"] and d["reason"] == "redefine" and d["start_min"] == 600 and d["end_min"] == 900


def test_swap_off_is_away_and_swap_work_is_working(staff):
    _override(staff["id"], WORKDAY, "off")
    assert ui.resolve_day(staff, WORKDAY)["reason"] == "swap_off"
    _override(staff["id"], OFFDAY, "work")
    d = ui.resolve_day(staff, OFFDAY)
    assert d["working"] and d["reason"] == "swap_work" and d["start_min"] == 480


def test_compute_day_events_bugs_vanish_integration():
    """The two bugs vanish in the LIVE scheduler path: a redefine no longer overrides AL, and sick now
    excludes. Seeds a real TWB staffer (compute_day_events reads the roster) and checks presence."""
    with db._db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM staff_registry WHERE canonical_name='ZZ_RESOLVE_CDE'")
        cur.execute("INSERT INTO staff_registry (canonical_name, status, org, work_start, work_end, "
                    "day_off) VALUES ('ZZ_RESOLVE_CDE','active','TWB','08:00','17:00',%s) RETURNING id",
                    (OFF_WD,))
        sid = cur.fetchone()["id"]
    d = date.fromisoformat(WORKDAY)
    try:
        present = lambda: "ZZ_RESOLVE_CDE" in {n for _m, n, _l, _t, _sd in ui.compute_day_events(d)}
        assert present()                                  # baseline: a normal working day → scheduled
        _al(sid, [WORKDAY]); _redefine(sid, WORKDAY)
        assert not present()                              # BUG 1 gone: AL wins over the redefine → away
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM al_requests WHERE staff_id=%s", (sid,))
            cur.execute("DELETE FROM shift_changes WHERE staff_id=%s", (sid,))
        _sick(sid, WORKDAY)
        assert not present()                              # BUG 2 gone: sick excludes from the schedule
    finally:
        with db._db() as c, c.cursor() as cur:
            for t in ("al_requests", "sick_cases", "shift_changes"):
                cur.execute(f"DELETE FROM {t} WHERE staff_id=%s", (sid,))
            cur.execute("DELETE FROM staff_registry WHERE id=%s", (sid,))


def test_special_leave_span_is_away(staff):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO special_leaves (staff_id, kind, who, start_date, days, deducted_amount, "
                    "is_test) VALUES (%s,'death','parent',%s,3,3,FALSE)", (staff["id"], WORKDAY))
    d = ui.resolve_day(staff, WORKDAY)
    assert not d["working"] and d["reason"] == "special"
