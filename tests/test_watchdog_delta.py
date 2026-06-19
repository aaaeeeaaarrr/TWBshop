"""Pure-diff helper shared by the test-mode + LIVE audit watchdogs (gm_bot.bot._watchdog_delta).

The watchdogs DM the owner the instant a NEW audit problem appears and a ✅ when one clears, de-duped
against the previous cycle. That de-dup is the whole correctness surface — proven here with no I/O.
"""
import json

from gm_bot.bot import _watchdog_delta


def test_first_cycle_everything_is_new():
    new, cleared, cur = _watchdog_delta(None, ["B problem", "A problem"])
    assert new == ["A problem", "B problem"]          # sorted, both new
    assert cleared == []
    assert json.loads(cur) == ["A problem", "B problem"]


def test_stable_cycle_pings_nothing():
    prev = json.dumps(["A", "B"])
    new, cleared, cur = _watchdog_delta(prev, ["A", "B"])
    assert new == [] and cleared == []
    assert json.loads(cur) == ["A", "B"]


def test_only_the_newly_appeared_problem_is_new():
    prev = json.dumps(["A", "B"])
    new, cleared, cur = _watchdog_delta(prev, ["A", "B", "C"])
    assert new == ["C"]
    assert cleared == []
    assert json.loads(cur) == ["A", "B", "C"]


def test_only_the_cleared_problem_is_cleared():
    prev = json.dumps(["A", "B", "C"])
    new, cleared, cur = _watchdog_delta(prev, ["A", "C"])
    assert new == []
    assert cleared == ["B"]
    assert json.loads(cur) == ["A", "C"]


def test_simultaneous_new_and_cleared():
    prev = json.dumps(["A", "B"])
    new, cleared, cur = _watchdog_delta(prev, ["A", "C"])
    assert new == ["C"]
    assert cleared == ["B"]
    assert json.loads(cur) == ["A", "C"]


def test_corrupt_prev_treated_as_empty():
    new, cleared, cur = _watchdog_delta("}{ not json", ["A"])
    assert new == ["A"]          # corrupt history ⇒ "nothing seen yet" ⇒ pings (fail-loud, never silent)
    assert cleared == []
    assert json.loads(cur) == ["A"]


def test_empty_problems_clears_all_and_stores_empty():
    prev = json.dumps(["A", "B"])
    new, cleared, cur = _watchdog_delta(prev, [])
    assert new == []
    assert cleared == ["A", "B"]
    assert json.loads(cur) == []


def test_duplicate_problems_deduped_in_store():
    new, cleared, cur = _watchdog_delta(json.dumps([]), ["A", "A", "B"])
    assert new == ["A", "B"]                 # set-deduped + sorted
    assert json.loads(cur) == ["A", "B"]
