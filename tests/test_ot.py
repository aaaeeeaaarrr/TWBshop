"""Give-OT pure logic + coverage surplus."""
from gm_bot import ot
from gm_bot import coverage as cov
from gm_bot.attendance import to_min


def test_cap_room():
    assert ot.cap_room(0) == 840
    assert ot.cap_room(13 * 60) == 60
    assert ot.cap_room(14 * 60) == 0
    assert ot.cap_room(15 * 60) == 0


def test_grant_fits():
    assert ot.grant_fits(13 * 60, 60) is True
    assert ot.grant_fits(13 * 60, 90) is False


def test_duration_options_capped():
    assert ot.duration_options(0)[0] == 30 and ot.duration_options(0)[-1] == 360
    # bank at 13.5h -> only 30min fits
    assert ot.duration_options(13 * 60 + 30) == [30]
    assert ot.duration_options(14 * 60) == []


def test_surplus_positive_when_overstaffed():
    # 3 kitchen present, lunch target 4 -> surplus -1; 5 present -> +1
    staff3 = [{"call_name": str(i), "expertise": ["kitchen"], "work_start": "06:00",
               "work_end": "18:00", "day_off": "Sun"} for i in range(5)]
    sp = cov.surplus("kitchen", "lunch", 660, 840, "Mon", staff3, set(), to_min)
    assert sp == 1   # 5 present - target 4


def test_slot_surplus_min_across_windows():
    staff = [{"call_name": "A", "expertise": ["kitchen"], "work_start": "06:00",
              "work_end": "18:00", "day_off": "Sun"}]
    # 1 kitchen, lunch target 4 -> surplus -3 (taking them out makes it worse) => negative
    sp = cov.slot_surplus(["kitchen"], 660, 840, "Mon", staff, set(), to_min)
    assert sp == -3
