"""core.sick — the own-sick outcome rule (check-in is the pivot). Mirrors the live gate/exemption."""
from core import sick
from core.points import points_for


def test_leave_early_no_penalty_remaining_payback():
    # checked in (came to work) then sick → NO −15, payback = remaining only (not the 540 shift)
    r = sick.sick_outcome(checked_in=True, late_inform_mins=-238, shift_min=540, remaining_min=302)
    assert r["points"] == [] and r["payback_min"] == 302
    assert points_for(r["points"]) == 0                       # zero points docked


def test_absent_sick_late_gets_minus15_full_payback():
    # not checked in, reported after start (−238 < 30) → −15 + full-shift payback
    r = sick.sick_outcome(checked_in=False, late_inform_mins=-238, shift_min=540, remaining_min=0)
    assert r["points"] == [("late_sick_inform", 1)] and r["payback_min"] == 540
    assert points_for(r["points"]) == -15


def test_absent_sick_early_notice_no_penalty():
    # not checked in, told us well before start (mins ≥ 30) → no −15, full payback
    r = sick.sick_outcome(checked_in=False, late_inform_mins=120, shift_min=540, remaining_min=0)
    assert r["points"] == [] and r["payback_min"] == 540
    # no shift at all (None) → no penalty either
    assert sick.sick_outcome(False, None, 540, 0)["points"] == []
