"""Day-off swap pure logic (session 28). No DB/Telegram.

A swaps their day-off to a chosen DATE within 7 days, exchanging with a PARTNER (similar shift,
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


def partner_eligible(requester: dict, cand: dict, to_min,
                     start_within_min: int = 180) -> bool:
    """Candidate is a plausible swap partner: active TWB, not the requester, not Tyty,
    with a shift starting within `start_within_min` of the requester's (similar hours)."""
    if cand["id"] == requester["id"]:
        return False
    if cand.get("org") != "TWB" or cand.get("canonical_name") == "Tyty":
        return False
    rs, cs = to_min(requester.get("work_start")), to_min(cand.get("work_start"))
    if rs is None or cs is None:
        return False
    diff = min((rs - cs) % 1440, (cs - rs) % 1440)
    return diff <= start_within_min
