"""Tests for gm_bot/sales.py — sales-anomaly framework (pure, no DB/AI)."""

from datetime import date

from gm_bot import sales


# ── day classification ────────────────────────────────────────────────────────

def test_month_phase():
    assert sales.month_phase(date(2026, 6, 3)) == "early"
    assert sales.month_phase(date(2026, 6, 15)) == "mid"
    assert sales.month_phase(date(2026, 6, 28)) == "late"


def test_holiday_and_festival():
    assert sales.holiday_name(date(2026, 1, 1)) == "International New Year"
    assert sales.holiday_name(date(2026, 6, 3)) is None
    assert sales.festival_name(date(2026, 4, 15)) == "Khmer New Year"      # inside window
    assert sales.festival_name(date(2026, 4, 20)) is None


def test_holiday_class_pre_and_post():
    # Independence Day 2026-11-09: the 8th is pre, the 10th is post.
    assert sales.holiday_class(date(2026, 11, 9)) == "holiday"
    assert sales.holiday_class(date(2026, 11, 8)) == "pre_holiday"
    assert sales.holiday_class(date(2026, 11, 10)) == "post_holiday"
    assert sales.holiday_class(date(2026, 6, 3)) == "normal"


def test_day_type_key_festival_is_its_own_class():
    assert sales.day_type_key(date(2026, 4, 15)) == "festival:Khmer New Year"
    # normal day -> weekday|phase|class
    k = sales.day_type_key(date(2026, 6, 2))   # a Tuesday, early, normal
    assert k == "Tue|early|normal"


# ── band + anomaly ────────────────────────────────────────────────────────────

def test_expected_band_needs_min_samples():
    assert sales.expected_band([100, 100, 100]) is None        # < MIN_SAMPLES
    band = sales.expected_band([100, 110, 90, 105, 95])
    assert band is not None and band["n"] == 5
    assert band["low"] < band["median"] < band["high"]


def _hist(day_sales):
    return [{"business_day": d, "total_sales": s} for d, s in day_sales]


def _same_type_dates(target, n):
    """Find n past dates with the SAME day-type key as target (same weekday + month-
    phase + holiday class) — so the band is built from a real same-type cohort."""
    from datetime import timedelta
    td = sales._parse_day(target)
    key = sales.day_type_key(td)
    out, d = [], td - timedelta(days=1)
    while len(out) < n and d > td - timedelta(days=600):
        if sales.day_type_key(d) == key:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out


def test_anomaly_silent_without_enough_same_type():
    # Only the target day's type has < MIN_SAMPLES of history -> None (stay silent).
    hist = _hist([("2026-06-02", 100), ("2026-06-09", 105)])  # 2 Tuesdays
    assert sales.anomaly_check("2026-06-16", 50, hist) is None


def test_anomaly_flags_low_payday_like_day():
    # Same-type cohort around $100; the target at $40 is well below the band.
    target = "2026-07-07"
    vals = [100, 98, 102, 99, 101]
    hist = [{"business_day": d, "total_sales": v}
            for d, v in zip(_same_type_dates(target, 5), vals)]
    res = sales.anomaly_check(target, 40, hist)
    assert res is not None
    assert res["is_low"] is True
    assert res["drop_pct"] > 50
    assert res["day_type"] == sales.day_type_key(sales._parse_day(target))


def test_anomaly_does_not_flag_normal_day():
    target = "2026-07-07"
    vals = [100, 98, 102, 99, 101]
    hist = [{"business_day": d, "total_sales": v}
            for d, v in zip(_same_type_dates(target, 5), vals)]
    res = sales.anomaly_check(target, 99, hist)
    assert res is not None and res["is_low"] is False


def test_anomaly_excludes_other_day_types():
    # Mondays in history must not be used as the baseline for a Tuesday.
    hist = _hist([("2026-06-01", 200), ("2026-06-08", 205), ("2026-06-15", 195),
                  ("2026-06-22", 202)])  # all Mondays
    assert sales.anomaly_check("2026-06-02", 90, hist) is None  # no Tuesday history


# ── trend + reasons ───────────────────────────────────────────────────────────

def test_declining_trend():
    assert sales.declining_trend([120, 110, 100]) is True
    assert sales.declining_trend([100, 110, 105]) is False
    assert sales.declining_trend([110, 100]) is False          # < days


def test_likely_reasons():
    r = sales.likely_reasons(date(2026, 4, 15), leave_count=2, lateness_count=1)
    joined = " ".join(r)
    assert "Khmer New Year" in joined
    assert "2 staff on leave" in joined
    assert "1 lateness" in joined
    assert sales.likely_reasons(date(2026, 6, 3)) == []        # ordinary day, no context


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
