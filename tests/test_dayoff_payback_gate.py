"""dayoff_payback_allowed — owner rule (Jun 21): never offer a rest day for a debt under 2h."""
from gm_bot.payback import DAYOFF_MIN_PAYBACK_MIN, dayoff_payback_allowed


def test_threshold_is_two_hours():
    assert DAYOFF_MIN_PAYBACK_MIN == 120


def test_small_debt_no_dayoff():
    for bal in (0, 1, 7, 59, 119):
        assert dayoff_payback_allowed(bal) is False


def test_two_hours_or_more_allows_dayoff():
    for bal in (120, 121, 240, 540):
        assert dayoff_payback_allowed(bal) is True


def test_none_is_safe():
    assert dayoff_payback_allowed(None) is False
