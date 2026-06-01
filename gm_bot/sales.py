"""
Sales-anomaly framework (TWB REPORT finance brain) — pure logic, no DB/AI.

Compares a day's sales only against OTHER days of the SAME TYPE, where a day-type =
weekday + month-phase (payday cycle) + holiday class. It learns the normal *band* for
each type from history and flags a day only when it falls below that band — so a quiet
late-month Tuesday is not an alarm, but a quiet payday Friday is.

Embodies the owner's 7 ideas:
  1. expectation BAND, not a single threshold
  2. month-phase buckets tied to payday (the real shape is learned from data)
  3. Cambodia holiday calendar (+ night-before / day-after as their own types)
  4. big festivals as a separate class (Khmer NY, Pchum Ben, Water Festival)
  5. trend vs blip (multi-day decline detection)
  6. flag-with-a-likely-reason (context hook)
  7. same-day last-month / last-year (reserved for when history lands)

NOTE: holiday/festival dates below are lunar-shifting — VERIFY & UPDATE annually.
With little history the engine stays silent (returns None) until a day-type has enough
samples; it activates once the years of Messenger reports are imported.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

# Minimum same-type samples before we trust a band enough to flag.
MIN_SAMPLES = 4
# How far below the band counts as "low" (robust spread multiplier + min % drop).
MAD_K = 2.0
MIN_DROP_FRAC = 0.20  # must also be >=20% below the type median to flag

# ── Cambodia public holidays (fixed-date) — verify/update yearly ────────────────
_FIXED_HOLIDAYS = {
    (1, 1):   "International New Year",
    (3, 8):   "International Women's Day",
    (5, 1):   "International Labour Day",
    (5, 14):  "King Sihamoni Birthday",
    (6, 18):  "Queen Mother Birthday",
    (10, 15): "King Father Commemoration",
    (10, 29): "King's Coronation",
    (11, 9):  "Independence Day",
}

# ── Multi-day festivals (lunar — approximate, VERIFY yearly) ────────────────────
# (start_date, end_date, name). 2025 + 2026 windows.
_FESTIVALS = [
    (date(2025, 4, 14), date(2025, 4, 16), "Khmer New Year"),
    (date(2026, 4, 14), date(2026, 4, 16), "Khmer New Year"),
    (date(2025, 9, 21), date(2025, 9, 23), "Pchum Ben"),
    (date(2026, 10, 10), date(2026, 10, 12), "Pchum Ben"),
    (date(2025, 11, 4), date(2025, 11, 6), "Water Festival"),
    (date(2026, 11, 24), date(2026, 11, 26), "Water Festival"),
]


def holiday_name(d: date) -> str | None:
    """Public-holiday name for a date, or None."""
    return _FIXED_HOLIDAYS.get((d.month, d.day))


def festival_name(d: date) -> str | None:
    """Festival name if the date falls in a festival window, else None."""
    for start, end, name in _FESTIVALS:
        if start <= d <= end:
            return name
    return None


def _is_holiday(d: date) -> bool:
    return holiday_name(d) is not None or festival_name(d) is not None


def month_phase(d: date) -> str:
    """Payday-cycle bucket: early (1-10, post-payday), mid (11-20), late (21-end)."""
    if d.day <= 10:
        return "early"
    if d.day <= 20:
        return "mid"
    return "late"


def holiday_class(d: date) -> str:
    """'festival:<name>' | 'holiday' | 'pre_holiday' | 'post_holiday' | 'normal'."""
    fest = festival_name(d)
    if fest:
        return "festival:" + fest
    if holiday_name(d):
        return "holiday"
    if _is_holiday(d + timedelta(days=1)):
        return "pre_holiday"
    if _is_holiday(d - timedelta(days=1)):
        return "post_holiday"
    return "normal"


def day_type_key(d: date) -> str:
    """The bucket a day belongs to. Festivals are their own class (weekday/phase
    don't matter inside a festival); otherwise weekday + month-phase + holiday class."""
    hc = holiday_class(d)
    if hc.startswith("festival:"):
        return hc
    return "%s|%s|%s" % (d.strftime("%a"), month_phase(d), hc)


def _parse_day(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def expected_band(values: list[float]) -> dict | None:
    """Robust normal band from same-type history. None if too few samples.
    Returns {median, low, high, n} using median +/- MAD_K * MAD."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < MIN_SAMPLES:
        return None
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals]) or (statistics.pstdev(vals) or 0.0)
    return {"median": med, "low": med - MAD_K * mad, "high": med + MAD_K * mad, "n": len(vals)}


def anomaly_check(target_day, target_sales: float, history: list[dict]) -> dict | None:
    """Compare target_sales to the band of same-type days in history.

    history: [{"business_day": <date/str>, "total_sales": <float>}], target day excluded.
    Returns None when there isn't enough same-type history yet (stays silent).
    Otherwise {day_type, is_low, drop_pct, median, low, high, n}.
    """
    if target_sales is None:
        return None
    td = _parse_day(target_day)
    key = day_type_key(td)
    same = [h["total_sales"] for h in history
            if h.get("total_sales") is not None
            and _parse_day(h["business_day"]) != td
            and day_type_key(_parse_day(h["business_day"])) == key]
    band = expected_band(same)
    if band is None:
        return None
    drop_pct = round((band["median"] - target_sales) / band["median"] * 100, 1) if band["median"] else 0.0
    is_low = target_sales < band["low"] and drop_pct >= MIN_DROP_FRAC * 100
    return {
        "day_type": key, "is_low": is_low, "drop_pct": drop_pct,
        "median": round(band["median"], 2), "low": round(band["low"], 2),
        "high": round(band["high"], 2), "n": band["n"],
    }


def declining_trend(recent_sales: list[float], days: int = 3) -> bool:
    """Idea 5 — multi-day decline: True if the last `days` values strictly decrease.
    `recent_sales` is oldest→newest."""
    tail = [s for s in recent_sales[-days:] if s is not None]
    if len(tail) < days:
        return False
    return all(tail[i] > tail[i + 1] for i in range(len(tail) - 1))


def likely_reasons(target_day, leave_count: int = 0, lateness_count: int = 0) -> list[str]:
    """Idea 6 — candidate causes to attach to a low-sales flag. Extend as the
    knowledge base grows (delivery-app outages, weather, etc.)."""
    td = _parse_day(target_day)
    reasons = []
    fest = festival_name(td)
    if fest:
        reasons.append("%s (people often travel to provinces)" % fest)
    elif holiday_name(td):
        reasons.append("public holiday: %s" % holiday_name(td))
    elif holiday_class(td) == "post_holiday":
        reasons.append("day after a holiday")
    if leave_count:
        reasons.append("%d staff on leave that day" % leave_count)
    if lateness_count:
        reasons.append("%d lateness/absence report(s) that day" % lateness_count)
    return reasons
