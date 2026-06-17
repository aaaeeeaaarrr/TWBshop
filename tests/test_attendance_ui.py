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


# ── overnight-aware shift-date binding (the sick/late-declare fix) ──
def _patch_now(monkeypatch, today_str, now_min, day_map):
    import gm_bot.attendance_ui as ui
    from datetime import date as _d
    monkeypatch.setattr(ui, "_today", lambda: _d.fromisoformat(today_str))
    monkeypatch.setattr(ui, "_now_min", lambda: now_min)
    def _rd(p, iso, ctx=None):
        w, s, e = day_map.get(iso, (False, None, None))
        return {"working": w, "start_min": s, "end_min": e, "reason": "normal" if w else "day_off"}
    monkeypatch.setattr(ui, "resolve_day", _rd)


def test_shift_date_now_overnight_after_midnight(monkeypatch):
    import gm_bot.attendance_ui as ui
    # 21:00-06:00 worker acting at 02:00 Jun17 → belongs to Jun16's shift, NOT the calendar day
    _patch_now(monkeypatch, "2026-06-17", 120,
               {"2026-06-17": (True, 1260, 360), "2026-06-16": (True, 1260, 360)})
    assert ui._shift_date_now({"id": 1, "work_start": "21:00", "work_end": "06:00"}) == date(2026, 6, 16)


def test_shift_date_now_overnight_before_midnight(monkeypatch):
    import gm_bot.attendance_ui as ui
    _patch_now(monkeypatch, "2026-06-16", 1320,        # 22:00, shift just started → today
               {"2026-06-16": (True, 1260, 360), "2026-06-15": (True, 1260, 360)})
    assert ui._shift_date_now({"id": 1, "work_start": "21:00", "work_end": "06:00"}) == date(2026, 6, 16)


def test_shift_date_now_day_worker_is_today(monkeypatch):
    import gm_bot.attendance_ui as ui
    _patch_now(monkeypatch, "2026-06-17", 300,         # 05:00, 06:00-15:00 shift imminent → today
               {"2026-06-17": (True, 360, 900), "2026-06-16": (True, 360, 900)})
    assert ui._shift_date_now({"id": 1, "work_start": "06:00", "work_end": "15:00"}) == date(2026, 6, 17)


def test_sick_late_mins_overnight_after_midnight(monkeypatch):
    import gm_bot.attendance_ui as ui
    # 2am report, 300 min AFTER the 21:00 start → negative (late informing), measured against the
    # shift they're IN — the old code measured tonight's shift (19h away) and missed the penalty
    _patch_now(monkeypatch, "2026-06-17", 120,
               {"2026-06-17": (True, 1260, 360), "2026-06-16": (True, 1260, 360)})
    assert ui._sick_late_mins({"id": 1, "work_start": "21:00", "work_end": "06:00"}) == -300


def test_sick_late_mins_day_worker_before_shift(monkeypatch):
    import gm_bot.attendance_ui as ui
    _patch_now(monkeypatch, "2026-06-17", 300,         # 60 min before a 06:00 shift → +60 (in time)
               {"2026-06-17": (True, 360, 900), "2026-06-16": (True, 360, 900)})
    assert ui._sick_late_mins({"id": 1, "work_start": "06:00", "work_end": "15:00"}) == 60
