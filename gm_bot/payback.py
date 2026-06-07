"""Payback pure logic (session 28). No DB/Telegram.

Late minutes become a payback BALANCE worked off in slots glued to the staff's own shift
(before/after) on working days, plus one day-off option, at the shop's neediest times.
This module: slot-window geometry, the ignore-ladder stage machine, partial math.
(Need-ranking by coverage is a later refinement; windows here are correct + schedule-based.)
"""
from __future__ import annotations

from datetime import date, timedelta

_DOW = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def working_days_ahead(day_off: str | None, leave_iso: set[str], start: date,
                       n_days: int, count: int) -> list[date]:
    """The next `count` WORKING days from `start` (inclusive) within `n_days` —
    skipping the staff's day-off weekday and any leave dates."""
    off = _DOW.get((day_off or "")[:3].title())
    out, d, scanned = [], start, 0
    while len(out) < count and scanned < n_days:
        if d.weekday() != off and d.isoformat() not in leave_iso:
            out.append(d)
        d += timedelta(days=1)
        scanned += 1
    return out


def slot_windows(ws_min: int, we_min: int, minutes: int) -> list[tuple[str, int, int]]:
    """For a working day: the before-shift and after-shift windows sized to `minutes`.
    Returns [(label, start_min, end_min)] — 'before' ends at shift start, 'after' begins
    at shift end. (Negative/over-1440 are wrapped by the caller into clock times.)"""
    return [
        ("before", (ws_min - minutes) % 1440, ws_min),
        ("after", we_min % 1440, (we_min + minutes) % 1440),
    ]


def apply_payback(balance_min: int, worked_min: int) -> tuple[int, int]:
    """Credit worked minutes against the balance. Returns (credited, new_balance).
    Over-work doesn't go negative — caps at the balance (extra is just early/OT elsewhere)."""
    credited = min(max(worked_min, 0), balance_min)
    return credited, balance_min - credited


def ignore_stage(days_since_created: int) -> str:
    """The ignore-ladder stage by whole days since the debt was born (legitimate-leave days
    are excluded by the caller before counting):
      0–2 → 'daily'  (one calm line at check-in)
      3   → 'warn'   ("pick before tomorrow, or I'll pick for you")
      >=4 → 'autobook' (GM books the neediest slot)."""
    if days_since_created >= 4:
        return "autobook"
    if days_since_created == 3:
        return "warn"
    return "daily"
