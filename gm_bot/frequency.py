"""Frequency / pattern detection for autonomous call-outs (session 28). No DB/Telegram/AI.

Reads a staff member's recent lateness (or paperless-sick) event DATES and flags patterns.
A confirmed pattern → the call-out job sends a Sonnet private DM + Opus group wink (CC owners).
Nice until bam: the GM never confronts on a pattern that hasn't crossed a threshold.
"""
from __future__ import annotations

from collections import Counter
from datetime import date


def _within(dates: list[date], today: date, days: int) -> list[date]:
    return [d for d in dates if 0 <= (today - d).days < days]


def detect(dates: list[str], today: date) -> dict | None:
    """Strongest pattern among recent events, or None. Returns {flag, count, detail}."""
    ds = sorted({date.fromisoformat(d) for d in dates})
    if not ds:
        return None
    last7 = _within(ds, today, 7)
    last30 = _within(ds, today, 30)
    last4 = ds[-4:]

    # same-weekday: 3 of the last 4 on one weekday ("every Monday")
    if len(last4) >= 4:
        wd, n = Counter(d.weekday() for d in last4).most_common(1)[0]
        if n >= 3:
            name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][wd]
            return {"flag": "same_weekday", "count": n, "detail": "%d of the last 4 on %s" % (n, name)}
    # burst: 2+ within 7 days
    if len(last7) >= 2:
        return {"flag": "burst", "count": len(last7), "detail": "%d in the last 7 days" % len(last7)}
    # drip: 3+ within 30 days (even if spread)
    if len(last30) >= 3:
        return {"flag": "drip", "count": len(last30), "detail": "%d in the last 30 days" % len(last30)}
    return None
