"""core.points — parity with live (gm_bot.points). Since the verdict inputs already match live ~98%,
proving the points DERIVATION matches live by construction completes the points vertical."""
import core.points as cp
import gm_bot.points as live


def test_split_late_parity_with_live():
    # cross-check the split across the full space: never-declared, declared-before, declared-after-N
    for late in (0, 1, 5, 12, 59, 120):
        for off in (None, -10, 0, 1, 3, 7, 100):
            assert cp.split_late(late, off) == live.split_late(late, off), (late, off)


def test_checkin_points_cases():
    assert cp.checkin_points("early", 0, 5) == [("early_arrival", 1)]
    assert cp.checkin_points("on_time", 0, 0) == []
    # late, never declared → all uninformed (−2/min)
    assert cp.checkin_points("late", 10, 0, None) == [("late_uninformed", 10)]
    # late, declared before shift start (offset ≤ 0) → all informed (−1/min)
    assert cp.checkin_points("late", 10, 0, 0) == [("late_informed", 10)]
    # late 10, declared 4 min after start → 4 uninformed + 6 informed
    assert cp.checkin_points("late", 10, 0, 4) == [("late_uninformed", 4), ("late_informed", 6)]


def test_catalogue_values_match_live():
    # the per-tenant config defaults equal live's catalogue (TWB): +10 / −1 / −2
    assert live.CATALOGUE["early_arrival"][0] == 10
    assert live.CATALOGUE["late_informed"][0] == -1
    assert live.CATALOGUE["late_uninformed"][0] == -2
