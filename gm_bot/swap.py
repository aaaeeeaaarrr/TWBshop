"""Day-off swap pure logic (session 28). No DB/Telegram.

A swaps their day-off to a chosen DATE within 7 days, exchanging with a PARTNER (OVERLAPPING shift,
coverage-safe). Partner approves FIRST (cheapest veto), then 2 seniors. Both schedules get a
dated override for that week. This module: same-week rule, partner eligibility.
"""
from __future__ import annotations

from datetime import date

_DOW = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def within_7_days(d1: date, d2: date) -> bool:
    return abs((d2 - d1).days) <= 7


def is_own_dayoff(weekday_name: str | None, d: date) -> bool:
    wd = _DOW.get((weekday_name or "")[:3].title())
    return wd is not None and d.weekday() == wd


def _shift_len(start_min: int, end_min: int) -> int:
    """Shift length in minutes (overnight-aware: end <= start wraps past midnight)."""
    return (end_min - start_min) % 1440 or 1440


def shift_overlap_min(s1: int, e1: int, s2: int, e2: int) -> int:
    """Minutes two shifts SHARE on the 24h circle. Each shift is the half-open interval [start, start+len);
    we slide the 2nd by ±24h so an overnight shift (e.g. 21:00→06:00) overlaps a day shift correctly."""
    l1, l2 = _shift_len(s1, e1), _shift_len(s2, e2)
    a0, a1 = s1, s1 + l1
    best = 0
    for off in (-1440, 0, 1440):
        b0, b1 = s2 + off, s2 + off + l2
        best = max(best, max(0, min(a1, b1) - max(a0, b0)))
    return best


def shifts_compatible(requester: dict, cand: dict, to_min, *, rule: str = "overlap",
                      overlap_frac: float = 0.5, start_window_min: int = 180) -> bool:
    """Are two shifts swap-compatible? Three selectable rules (config-driven via the dashboard —
    categories.attendance.schedule.swap_partner_rule):
      • overlap      — they OVERLAP by ≥ overlap_frac of the SHORTER shift (default; they mostly work the same
                       hours, so trading days barely shifts coverage — the most correct rule).
      • start_or_end — their start OR end times are within start_window_min of each other.
      • start_window — their START times are within start_window_min (the original 'similar start' rule)."""
    rs, re_ = to_min(requester.get("work_start")), to_min(requester.get("work_end"))
    cs, ce = to_min(cand.get("work_start")), to_min(cand.get("work_end"))
    if None in (rs, re_, cs, ce):
        return False
    if rule == "start_window":
        return min((rs - cs) % 1440, (cs - rs) % 1440) <= start_window_min
    if rule == "start_or_end":
        ds = min((rs - cs) % 1440, (cs - rs) % 1440)
        de = min((re_ - ce) % 1440, (ce - re_) % 1440)
        return ds <= start_window_min or de <= start_window_min
    overlap = shift_overlap_min(rs, re_, cs, ce)                    # default: overlap
    return overlap >= overlap_frac * min(_shift_len(rs, re_), _shift_len(cs, ce))


def partner_eligible(requester: dict, cand: dict, to_min, *, rule: str = "overlap",
                     overlap_frac: float = 0.5, start_window_min: int = 180) -> bool:
    """Candidate is a plausible swap partner: active TWB, not the requester, not Tyty, with a shift compatible
    with the requester's per the configured `rule` (default: overlaps by ≥ half the shorter shift)."""
    if cand["id"] == requester["id"]:
        return False
    if cand.get("org") != "TWB" or cand.get("canonical_name") == "Tyty":
        return False
    return shifts_compatible(requester, cand, to_min, rule=rule, overlap_frac=overlap_frac,
                             start_window_min=start_window_min)
