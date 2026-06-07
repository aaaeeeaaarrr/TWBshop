"""Points pure logic — derive from rules, count only active."""
from gm_bot import points


def _rules(**active_vals):
    # build a rules map; pass cause=value for active ones
    r = {c: {"value": v, "active": False} for c, (v, _) in points.CATALOGUE.items()}
    for c, v in active_vals.items():
        r[c] = {"value": v, "active": True}
    return r


def test_inactive_rules_score_zero():
    rules = _rules()  # all inactive
    evs = [{"cause": "early_arrival", "quantity": 1}, {"cause": "late_uninformed", "quantity": 20}]
    assert points.total_points(evs, rules) == 0.0


def test_active_rules_score():
    rules = _rules(early_arrival=10, late_uninformed=-2)
    evs = [{"cause": "early_arrival", "quantity": 1}, {"cause": "late_uninformed", "quantity": 20}]
    assert points.total_points(evs, rules) == 10 + (-2 * 20)


def test_quantity_multiplier():
    rules = _rules(late_informed=-1)
    assert points.event_points("late_informed", 35, rules) == -35


def test_unknown_cause_zero():
    assert points.event_points("nonexistent", 5, _rules(early_arrival=10)) == 0.0


def test_catalogue_has_core_causes():
    for c in ("early_arrival", "late_informed", "late_uninformed", "no_show"):
        assert c in points.CATALOGUE
