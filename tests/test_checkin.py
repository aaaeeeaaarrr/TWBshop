"""Check-in verdict + scheduling — pure logic."""
from gm_bot import checkin as ci


def test_in_zone_exactly_on_time():
    assert ci.verdict(540, 540, True) == ("ontime", 0)


def test_early_beyond_grace():
    # 9:00 shift, arrive 8:48 (12 min early) -> early +bonus
    assert ci.verdict(528, 540, True) == ("early", 12)


def test_early_within_grace_is_ontime():
    # 3 min early -> no bonus, no penalty
    assert ci.verdict(537, 540, True) == ("ontime", 0)


def test_late_within_grace_free():
    # 5 min late exactly -> free (ontime)
    assert ci.verdict(545, 540, True) == ("ontime", 0)


def test_late_beyond_grace_counts_all():
    # 25 min late -> all 25 count
    assert ci.verdict(565, 540, True) == ("late", 25)


def test_outside_zone_never_checks_in():
    assert ci.verdict(540, 540, False) == ("not_here", 0)


def test_overnight_early():
    # 9pm shift (1260), arrive 8:50pm (1250) = 10 min early
    assert ci.verdict(1250, 1260, True) == ("early", 10)


def test_overnight_after_midnight_late():
    # 9pm shift (1260), arrive 12:30am (30) -> 210 min late
    assert ci.verdict(30, 1260, True) == ("late", 210)


def test_is_due():
    assert ci.is_due(350, 350) is True
    assert ci.is_due(350, 351) is False
