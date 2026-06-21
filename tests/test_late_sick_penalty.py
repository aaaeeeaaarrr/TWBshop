"""v_late_sick_penalty — own-sick declared late must carry the −15 (catches the Long-class miss)."""
from datetime import date, datetime, timezone

from gm_bot.audit import v_late_sick_penalty

STAFF = {
    1: {"id": 1, "call_name": "Long", "work_start": "21:00"},
    2: {"id": 2, "call_name": "Fam", "work_start": "06:00"},
}
TODAY = date(2026, 6, 21)


def _utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_flags_late_own_sick_with_no_penalty():
    # 20:55 PP (13:55 UTC) vs 21:00 shift = 5 min before, no late_sick_inform event → FLAG
    sick = [{"staff_id": 1, "who": "me", "the_date": date(2026, 6, 19), "created_at": _utc(2026, 6, 19, 13, 55)}]
    out = v_late_sick_penalty(sick, [], STAFF, TODAY)
    assert len(out) == 1 and "LONG" in out[0] and "2026-06-19" in out[0]


def test_no_flag_when_penalty_present():
    sick = [{"staff_id": 1, "who": "me", "the_date": date(2026, 6, 18), "created_at": _utc(2026, 6, 18, 13, 55)}]
    pevents = [{"staff_id": 1, "cause": "late_sick_inform", "ref": "2026-06-18"}]
    assert v_late_sick_penalty(sick, pevents, STAFF, TODAY) == []


def test_no_flag_when_declared_early():
    # 17:00 PP (10:00 UTC) vs 21:00 shift = 240 min before → not late
    sick = [{"staff_id": 1, "who": "me", "the_date": date(2026, 6, 17), "created_at": _utc(2026, 6, 17, 10, 0)}]
    assert v_late_sick_penalty(sick, [], STAFF, TODAY) == []


def test_family_sick_excluded():
    sick = [{"staff_id": 2, "who": "child", "the_date": date(2026, 6, 19), "created_at": _utc(2026, 6, 18, 23, 55)}]
    assert v_late_sick_penalty(sick, [], STAFF, TODAY) == []


def test_old_sick_outside_window_ignored():
    sick = [{"staff_id": 1, "who": "me", "the_date": date(2026, 6, 1), "created_at": _utc(2026, 6, 1, 13, 55)}]
    assert v_late_sick_penalty(sick, [], STAFF, TODAY) == []
