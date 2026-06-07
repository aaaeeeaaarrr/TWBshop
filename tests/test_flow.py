"""Flow-state pure helpers (H1) — TTL, expiry, merge."""
from datetime import datetime, timedelta, timezone

from gm_bot import flow


def _t(s):
    return datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc) + timedelta(seconds=s)


def test_new_expiry_and_not_expired():
    now = _t(0)
    exp = flow.new_expiry(30, now=now)
    assert flow.is_expired(exp, now=now) is False
    assert flow.is_expired(exp, now=now + timedelta(minutes=29)) is False


def test_expired_after_ttl():
    now = _t(0)
    exp = flow.new_expiry(30, now=now)
    assert flow.is_expired(exp, now=now + timedelta(minutes=31)) is True


def test_missing_or_bad_expiry_is_expired():
    assert flow.is_expired(None) is True
    assert flow.is_expired("not-a-date") is True


def test_naive_iso_treated_as_utc():
    # a stored naive timestamp shouldn't crash the compare
    assert flow.is_expired("2020-01-01T00:00:00") is True


def test_merge_overwrites_and_removes():
    base = {"days": ["a"], "reason": "x"}
    assert flow.merge_data(base, {"reason": "y"}) == {"days": ["a"], "reason": "y"}
    assert flow.merge_data(base, {"reason": None}) == {"days": ["a"]}
    assert flow.merge_data(None, {"k": 1}) == {"k": 1}
    assert flow.merge_data(base, None) == base


def test_ttl_for():
    assert flow.ttl_for(step_is_text_wait=True) == flow.TEXT_WAIT_TTL_MIN
    assert flow.ttl_for(step_is_text_wait=False) == flow.DEFAULT_TTL_MIN
