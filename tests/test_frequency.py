"""Frequency / call-out pattern detection."""
from datetime import date

from gm_bot import frequency as fq


def test_none_when_few():
    assert fq.detect([], date(2026, 6, 8)) is None
    assert fq.detect(["2026-06-01"], date(2026, 6, 8)) is None


def test_burst_2_in_7_days():
    p = fq.detect(["2026-06-06", "2026-06-08"], date(2026, 6, 8))
    assert p and p["flag"] == "burst" and p["count"] == 2


def test_drip_3_in_30_days():
    p = fq.detect(["2026-05-20", "2026-06-01", "2026-06-07"], date(2026, 6, 8))
    assert p and p["flag"] in ("drip", "burst")  # 1st+7th within 7? no -> drip


def test_same_weekday():
    # four Mondays-ish: pick dates that are same weekday
    mondays = ["2026-05-18", "2026-05-25", "2026-06-01", "2026-06-08"]  # all Mondays
    p = fq.detect(mondays, date(2026, 6, 8))
    assert p and p["flag"] == "same_weekday" and "Monday" in p["detail"]


def test_old_events_ignored():
    assert fq.detect(["2026-01-01", "2026-02-01"], date(2026, 6, 8)) is None
