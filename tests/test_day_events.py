"""Day-event schedule brain — pure logic."""
from gm_bot.attendance_ui import staff_day_events


def test_day_shift_events():
    p = {"work_start": "06:00", "work_end": "18:00"}
    ev = dict((label.split(" ")[0], m) for m, label in staff_day_events(p))
    assert ev["T−10"] == 350      # 5:50am
    assert ev["T0"] == 360        # 6:00am
    assert ev["T+5"] == 365
    assert ev["check-out"] == 1080  # 6:00pm
    assert ev["leave-early"] == 1090


def test_overnight_shift_events_wrap():
    p = {"work_start": "21:00", "work_end": "06:00"}
    ev = dict((label.split(" ")[0], m) for m, label in staff_day_events(p))
    assert ev["T−10"] == 1250     # 8:50pm
    assert ev["T0"] == 1260       # 9:00pm
    assert ev["check-out"] == 360  # 6:00am (wrapped)
    assert ev["leave-early"] == 370


def test_no_shift_no_events():
    assert staff_day_events({"work_start": None, "work_end": None}) == []
    assert staff_day_events({"work_start": "Never", "work_end": "Never"}) == []
