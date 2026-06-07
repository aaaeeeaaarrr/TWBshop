"""Day-off swap pure logic."""
from datetime import date

from gm_bot import swap
from gm_bot.attendance import to_min


def test_within_7_days():
    assert swap.within_7_days(date(2026, 6, 8), date(2026, 6, 15)) is True
    assert swap.within_7_days(date(2026, 6, 8), date(2026, 6, 16)) is False
    assert swap.within_7_days(date(2026, 6, 8), date(2026, 6, 8)) is True


def test_is_own_dayoff():
    assert swap.is_own_dayoff("Wed", date(2026, 6, 10)) is True   # Jun 10 2026 = Wed
    assert swap.is_own_dayoff("Wed", date(2026, 6, 11)) is False


def test_partner_eligible_similar_shift():
    req = {"id": 1, "org": "TWB", "work_start": "11:00", "work_end": "21:00"}
    near = {"id": 2, "org": "TWB", "canonical_name": "X", "work_start": "12:00", "work_end": "21:00"}
    far = {"id": 3, "org": "TWB", "canonical_name": "Y", "work_start": "21:00", "work_end": "06:00"}
    assert swap.partner_eligible(req, near, to_min) is True
    assert swap.partner_eligible(req, far, to_min) is False


def test_partner_eligible_excludes_self_tyty_delis():
    req = {"id": 1, "org": "TWB", "work_start": "06:00", "work_end": "15:00"}
    assert swap.partner_eligible(req, dict(req), to_min) is False           # self
    assert swap.partner_eligible(req, {"id": 2, "org": "DELIS", "work_start": "06:00",
                                       "work_end": "15:00"}, to_min) is False
    assert swap.partner_eligible(req, {"id": 3, "org": "TWB", "canonical_name": "Tyty",
                                       "work_start": "06:00", "work_end": "15:00"}, to_min) is False
