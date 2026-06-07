"""AL pure logic."""
from datetime import date, datetime, timedelta, timezone

from gm_bot import al


def test_short_notice_boundary():
    today = date(2026, 6, 8)
    assert al.is_short_notice(date(2026, 6, 8), today) is True     # today
    assert al.is_short_notice(date(2026, 6, 14), today) is True    # 6 days
    assert al.is_short_notice(date(2026, 6, 15), today) is False   # 7 days = free


def test_short_notice_days_filter():
    today = date(2026, 6, 8)
    days = ["2026-06-10", "2026-06-20"]
    assert al.short_notice_days(days, today) == ["2026-06-10"]


def test_points_cost():
    assert al.points_cost(2, 540) == 108     # 0.1 * 540 * 2


def test_fractional_al():
    assert al.fractional_al(1260, 1440, 540) == round(180 / 540, 2)   # 3h of 9h ≈ 0.33
    assert al.fractional_al(0, 0, 540) == 0.0


def test_al_day_count():
    assert al.al_day_count(["a", "b", "c"], "days") == 3.0
    assert al.al_day_count(["a", "b", "c"], "hours", 0.33) == round(3 * 0.33, 2)


def test_quorum():
    assert al.quorum_reached(["approve", "approve"]) is True
    assert al.quorum_reached(["approve", "not_approve"]) is False
    assert al.quorum_rejected(["not_approve", "not_approve"]) is True


def test_senior_timers_scale_to_start():
    now = datetime(2026, 6, 8, 12, tzinfo=timezone.utc)
    # AL starts in 2 hours -> nudge 30min (25%), escalate 1h (50%)
    nudge, esc = al.senior_timers(now, now + timedelta(hours=2))
    assert abs(nudge - 1800) < 1 and abs(esc - 3600) < 1
    # far future -> capped at 12h / 24h
    nudge2, esc2 = al.senior_timers(now, now + timedelta(days=10))
    assert nudge2 == 12 * 3600 and esc2 == 24 * 3600
