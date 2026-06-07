"""Planned-AL deduction timing — pure logic."""
from gm_bot.attendance import days_due


def test_past_days_due():
    assert days_due(["2026-06-08", "2026-06-09"], [], "2026-06-09", "imported planned AL") \
        == ["2026-06-08"]


def test_already_deducted_skipped():
    assert days_due(["2026-06-08"], ["2026-06-08"], "2026-06-10", "imported planned AL") == []


def test_future_days_not_due():
    assert days_due(["2026-06-12"], [], "2026-06-09", "x") == []


def test_ph_never_deducted():
    assert days_due(["2026-06-12", "2026-06-13"], [], "2026-06-20",
                    "PH compensation (April) — DO NOT DEDUCT") == []


def test_all_passed_all_due_sorted():
    assert days_due(["2026-06-10", "2026-06-09"], [], "2026-06-11", None) \
        == ["2026-06-09", "2026-06-10"]
