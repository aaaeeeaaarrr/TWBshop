"""Coverage engine pure logic."""
from gm_bot import coverage as cov
from gm_bot.attendance import to_min


def test_stations_for():
    assert cov.stations_for(["cashier"]) == {"front"}
    assert cov.stations_for(["bar"]) == {"front", "bar"}
    assert cov.stations_for(["kitchen", "service"]) == {"front", "kitchen"}
    assert cov.stations_for(["bakery"]) == {"bakery"}


def test_window_targets():
    assert cov.window_target("lunch", "Mon", "kitchen") == 4
    assert cov.window_target("morning", "Mon", "kitchen") == 3
    assert cov.window_target("night", "Fri", "bakery") == 4
    assert cov.window_target("night", "Tue", "bakery") == 3
    assert cov.window_target("dinner", "Mon", "bakery") == 0
    assert cov.window_target("lunch", "Mon", "bar") == 1
    assert cov.window_target("lunch", "Mon", "prep") == 2


def test_on_duty_counts_only_qualified_present():
    staff = [
        {"call_name": "A", "expertise": ["kitchen"], "work_start": "06:00", "work_end": "18:00", "day_off": "Sun"},
        {"call_name": "B", "expertise": ["cashier"], "work_start": "06:00", "work_end": "15:00", "day_off": "Mon"},
        {"call_name": "C", "expertise": ["kitchen"], "work_start": "21:00", "work_end": "06:00", "day_off": "Tue"},
    ]
    # lunch (11-14) Monday: A works (kitchen), B is off Mon, C is night -> kitchen on-duty = 1
    assert cov.on_duty("kitchen", 660, 840, "Mon", staff, set(), to_min) == 1
    # front lunch Mon: B off -> 0
    assert cov.on_duty("front", 660, 840, "Mon", staff, set(), to_min) == 0


def test_shortfall_and_leave():
    staff = [{"call_name": "A", "expertise": ["kitchen"], "work_start": "06:00",
              "work_end": "18:00", "day_off": "Sun"}]
    # lunch Tue kitchen target 4, on-duty 1 -> shortfall 3
    assert cov.shortfall("kitchen", "lunch", 660, 840, "Tue", staff, set(), to_min) == 3
    # A on leave -> on-duty 0 -> shortfall 4
    assert cov.shortfall("kitchen", "lunch", 660, 840, "Tue", staff, {"a"}, to_min) == 4


def test_slot_score_picks_biggest_shortfall():
    staff = [{"call_name": "A", "expertise": ["kitchen"], "work_start": "06:00",
              "work_end": "18:00", "day_off": "Sun"}]
    # a kitchen+front person; slot 11-14 Tue overlaps lunch; kitchen shortfall 3, front 4 -> 4
    score = cov.slot_score(["kitchen", "cashier"], 660, 840, "Tue", staff, set(), to_min)
    assert score == 4
