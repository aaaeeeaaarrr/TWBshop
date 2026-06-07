"""Late + payback pure logic."""
from datetime import date

from gm_bot import late, payback


# ── late ──
def test_late_offsets_day_shift():
    offs = late.late_offsets(360, 1080)  # 6am-6pm (12h=720), cap 600
    assert offs[:10] == [5, 10, 15, 20, 30, 45, 60, 75, 90, 120]
    assert offs[-1] == 600 and all(o <= 600 for o in offs)


def test_late_offsets_short_shift_caps():
    offs = late.late_offsets(540, 840)  # 9am-2pm (5h=300), cap 180
    assert offs[-1] == 180 and 210 not in offs


def test_declared_minutes_late_overnight():
    # 9pm shift, declared 9:30pm
    assert late.declared_minutes_late(1290, 1260) == 30


# ── payback ──
def test_working_days_skips_dayoff_and_leave():
    days = payback.working_days_ahead("Wed", {"2026-06-09"}, date(2026, 6, 8), 10, 3)
    isos = [d.isoformat() for d in days]
    # 8 Mon ok · 9 Tue leave(skip) · 10 Wed dayoff(skip) · 11 Thu ok · 12 Fri ok
    assert isos == ["2026-06-08", "2026-06-11", "2026-06-12"]


def test_slot_windows_before_after():
    w = dict((lbl, (s, e)) for lbl, s, e in payback.slot_windows(540, 1020, 90))  # 9am-5pm, 90min
    assert w["before"] == (450, 540)     # 7:30-9:00
    assert w["after"] == (1020, 1110)    # 5:00-6:30


def test_slot_windows_overnight_wrap():
    w = dict((lbl, (s, e)) for lbl, s, e in payback.slot_windows(1260, 360, 60))  # 9pm-6am, 60min
    assert w["before"] == (1200, 1260)   # 8-9pm
    assert w["after"] == (360, 420)      # 6-7am


def test_apply_payback_partial_and_cap():
    assert payback.apply_payback(90, 60) == (60, 30)
    assert payback.apply_payback(30, 50) == (30, 0)   # over-work caps at balance


def test_ignore_stage():
    assert payback.ignore_stage(0) == "daily"
    assert payback.ignore_stage(2) == "daily"
    assert payback.ignore_stage(3) == "warn"
    assert payback.ignore_stage(4) == "autobook"
    assert payback.ignore_stage(9) == "autobook"
