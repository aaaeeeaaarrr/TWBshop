"""Tests for gm_bot/clarify.py — escalation ladder decision logic. Pure, no DB."""

from datetime import datetime, timedelta, timezone

from gm_bot import clarify


def _t(minutes_ago):
    return datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc) - timedelta(minutes=minutes_ago)


NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_checking_phrase_detection():
    assert clarify.is_checking_phrase("give us time, we are checking")
    assert clarify.is_checking_phrase("one moment please")
    assert clarify.is_checking_phrase("let me check")
    assert not clarify.is_checking_phrase("the gas was 5000 riel")
    assert not clarify.is_checking_phrase("")
    assert not clarify.is_checking_phrase(None)


def test_open_waits_before_first_nudge():
    # created 5 min ago, next action in 5 min -> not due
    action, _ = clarify.decide_ladder_action(
        "open", created_at=_t(5), now=NOW, next_action_at=NOW + timedelta(minutes=5))
    assert action == "wait"


def test_open_nudges_when_due():
    action, new_next = clarify.decide_ladder_action(
        "open", created_at=_t(10), now=NOW, next_action_at=_t(0))
    assert action == "nudge"
    assert new_next == NOW + clarify.NUDGE_INTERVAL_OPEN  # 10 min


def test_checking_uses_30min_cadence():
    action, new_next = clarify.decide_ladder_action(
        "checking", created_at=_t(40), now=NOW, next_action_at=_t(0))
    assert action == "nudge"
    assert new_next == NOW + clarify.NUDGE_INTERVAL_CHECKING  # 30 min


def test_escalates_after_two_hours():
    action, _ = clarify.decide_ladder_action(
        "open", created_at=_t(121), now=NOW, next_action_at=_t(1))
    assert action == "escalate"


def test_checking_also_escalates_after_two_hours():
    action, _ = clarify.decide_ladder_action(
        "checking", created_at=_t(125), now=NOW, next_action_at=NOW + timedelta(minutes=5))
    assert action == "escalate"


def test_resolved_is_ignored():
    for status in ("answered", "escalated", "closed"):
        action, _ = clarify.decide_ladder_action(status, _t(200), NOW, _t(1))
        assert action == "none"


def test_nudge_text_hardens_after_three():
    soft = clarify.nudge_text("report_math", nudge_count=0)
    hard = clarify.nudge_text("report_math", nudge_count=3)
    assert "owner" in hard.lower()
    assert "owner" not in soft.lower()


def test_escalation_text_variants():
    no_answer = clarify.escalation_text("report_math", "TWB REPORT", "Sok", "fix the total", None)
    assert "No clarification after 2h" in no_answer
    with_answer = clarify.escalation_text("report_math", "TWB REPORT", "Sok", "fix the total", "i miscounted")
    assert "may not add up" in with_answer
    assert "i miscounted" in with_answer
