"""Day-off payback / OT window primitive — anchored to regular shift hours, overnight-safe."""
from datetime import date
from gm_bot import payback as pb


def test_dayoff_dates_ahead_picks_the_weekday():
    # Mon 2026-06-08 start; day_off = Wed → next Wed is 2026-06-10, then 06-17 within 14 days
    got = pb.dayoff_dates_ahead("Wed", set(), date(2026, 6, 8), 14)
    assert got == [date(2026, 6, 10), date(2026, 6, 17)]

def test_dayoff_dates_skips_leave():
    got = pb.dayoff_dates_ahead("Wed", {"2026-06-10"}, date(2026, 6, 8), 14)
    assert got == [date(2026, 6, 17)]

def test_dayoff_dates_none_day_off():
    assert pb.dayoff_dates_ahead(None, set(), date(2026, 6, 8), 7) == []


def test_dayoff_windows_within_day_shift():
    # 7am-4pm (420-960), pay back 120 → windows slide inside regular hours, 30-min step
    w = pb.dayoff_windows(420, 960, 120)
    assert w[0] == (420, 540)            # 7:00-9:00 (start of regular hours)
    assert w[-1] == (840, 960)           # 2:00-4:00 (end of regular hours)
    assert all(0 <= s < 1440 and 0 <= e < 1440 for s, e in w)

def test_dayoff_windows_night_shift_gives_night_windows():
    # 9pm-6am (1260 -> 360, overnight). A 120-min window must land at NIGHT, never a morning call.
    w = pb.dayoff_windows(1260, 360, 120)
    assert w[0] == (1260, 1380)          # 9:00pm-11:00pm
    assert w[-1] == (240, 360)           # 4:00am-6:00am (end of the night shift)
    # never a daytime (e.g. 8am-4pm) window
    assert all(not (480 <= s <= 960) for s, e in w)

def test_dayoff_windows_full_amount_fills_band():
    # amount >= shift span → one window = the whole regular-hours block
    w = pb.dayoff_windows(420, 960, 999)
    assert w == [(420, 960)]

def test_dayoff_windows_margin_widens_band():
    # margin 120 (±2h) extends a 7am-4pm band to 5am-6pm
    w = pb.dayoff_windows(420, 960, 120, margin_min=120)
    assert w[0] == (300, 420)            # 5:00am-7:00am (2h before regular start)
    assert w[-1] == (960, 1080)          # 4:00pm-6:00pm (2h after regular end)
