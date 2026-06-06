"""Day-event schedule brain — pure logic (day_offset, minute, label)."""
from gm_bot.attendance_ui import staff_day_events


def _by_prefix(p):
    return {label.split(" ")[0]: (off, m) for off, m, label in staff_day_events(p)}


def test_day_shift_events_all_same_day():
    ev = _by_prefix({"work_start": "06:00", "work_end": "18:00"})
    assert ev["T−10"] == (0, 350)        # 5:50am
    assert ev["T0"] == (0, 360)
    assert ev["T+5"] == (0, 365)
    assert ev["check-out"] == (0, 1080)  # 6:00pm
    assert ev["leave-early"] == (0, 1090)


def test_overnight_shift_end_events_carry_next_day_offset():
    ev = _by_prefix({"work_start": "21:00", "work_end": "06:00"})
    assert ev["T−10"] == (0, 1250)       # 8:50pm same day
    assert ev["T0"] == (0, 1260)
    assert ev["check-out"] == (1, 360)   # 6:00am NEXT day
    assert ev["leave-early"] == (1, 370)


def test_just_after_midnight_start_pre_reminder_previous_day():
    ev = _by_prefix({"work_start": "00:05", "work_end": "09:00"})
    assert ev["T−10"] == (-1, 1435)      # 11:55pm the day BEFORE
    assert ev["T0"] == (0, 5)


def test_no_shift_no_events():
    assert staff_day_events({"work_start": None, "work_end": None}) == []
    assert staff_day_events({"work_start": "Never", "work_end": "Never"}) == []
