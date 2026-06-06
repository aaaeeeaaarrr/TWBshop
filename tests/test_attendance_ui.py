"""Attendance shell pure helpers — no DB/Telegram."""
from datetime import date

from gm_bot.attendance_ui import day_label, fmt12, grid, late_offsets, shift_len_min


def test_fmt12():
    assert fmt12(540) == "9am"
    assert fmt12(545) == "9:05am"
    assert fmt12(1260) == "9pm"
    assert fmt12(0) == "12am"
    assert fmt12(720) == "12pm"
    assert fmt12(1500) == "1am"  # wraps past midnight (overnight ladder)


def test_day_label():
    assert day_label(date(2026, 6, 29)) == "Mo 29/06"
    assert day_label(date(2026, 6, 7)) == "Su 07/06"


def test_shift_len_overnight():
    assert shift_len_min("21:00", "06:00") == 540   # 9pm -> 6am
    assert shift_len_min("06:00", "18:00") == 720


def test_late_offsets_9h_shift():
    offs = late_offsets(540)  # cap = 420 (2h before end)
    assert offs[:10] == [5, 10, 15, 20, 30, 45, 60, 75, 90, 120]
    assert offs[-1] == 420
    assert all(o <= 420 for o in offs)


def test_late_offsets_short_shift():
    offs = late_offsets(300)  # 5h shift, cap 180
    assert offs[-1] == 180
    assert 210 not in offs


def test_grid_rows():
    btns = list(range(7))
    rows = grid(btns, 3)
    assert [len(r) for r in rows] == [3, 3, 1]
