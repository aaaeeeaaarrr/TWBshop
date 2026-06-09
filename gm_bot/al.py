"""Annual-leave pure logic (session 28). No DB/Telegram.

AL costs AL-days (never salary). ≥7 days ahead = free; 0–6 days = short-notice, priced in
points. ≥2 senior approvals (a senior can't approve their own). Hours-AL deducts fractionally.
This module: short-notice detection, points cost, fractional deduction, quorum, availability set.
Gated behind attendance_live like everything else.
"""
from __future__ import annotations

from datetime import date, timedelta

SHORT_NOTICE_DAYS = 7          # <7 days ahead = short notice (points cost)
SHORT_NOTICE_PT_PER_MIN = 0.1  # pending activation
APPROVALS_NEEDED = 2


def is_short_notice(al_day: date, today: date) -> bool:
    return (al_day - today).days < SHORT_NOTICE_DAYS


def short_notice_days(al_days: list[str], today: date) -> list[str]:
    return [d for d in al_days if is_short_notice(date.fromisoformat(d), today)]


def points_cost(short_days: int, shift_minutes: int) -> int:
    """Rough full-day short-notice points hit (pending activation)."""
    return round(SHORT_NOTICE_PT_PER_MIN * shift_minutes * short_days)


def fractional_al(hours_start_min: int, hours_end_min: int, shift_minutes: int) -> float:
    """Hours-AL as a fraction of an AL day: window / shift length, rounded to 2dp."""
    window = (hours_end_min - hours_start_min) % 1440
    if shift_minutes <= 0:
        return 0.0
    return round(window / shift_minutes, 2)


_DOW = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def al_charged_days(al_days: list[str], day_off: str | None = None) -> list[str]:
    """The selected dates that actually COST AL — the staff's weekly day-off is never charged
    (a day off is already free, whether they tapped it or it falls inside the leave span)."""
    off = _DOW.get((day_off or "")[:3].title()) if day_off else None
    return [d for d in sorted(al_days)
            if off is None or date.fromisoformat(d).weekday() != off]


def al_day_count(al_days: list[str], kind: str, frac_per_day: float = 1.0,
                 day_off: str | None = None) -> float:
    """Total AL deducted: full days = #charged days; hours = frac × #charged days. The staff's
    weekly day-off dates are excluded (never charged)."""
    n = len(al_charged_days(al_days, day_off))
    return round(n * (frac_per_day if kind == "hours" else 1.0), 2)


def al_span_label(al_days: list[str], day_off: str | None = None) -> str:
    """Format the leave as 'from → to' segments, BRIDGING the staff's day-off days: a day off
    sitting between two AL days means one continuous absence (out from the first to the last).
    A genuine WORKING-day gap splits into separate segments (so we never imply days off he works)."""
    days = sorted({date.fromisoformat(d) for d in al_days})
    if not days:
        return ""
    off = _DOW.get((day_off or "")[:3].title()) if day_off else None
    segs, s, e = [], days[0], days[0]
    for d in days[1:]:
        between = [e + timedelta(days=i) for i in range(1, (d - e).days)]
        if (d - e).days == 1 or (between and all(g.weekday() == off for g in between)):
            e = d                       # consecutive, or only day-off(s) in the gap → bridge
        else:
            segs.append((s, e)); s = e = d
    segs.append((s, e))
    fmt = lambda x: x.strftime("%a %d/%m")   # noqa: E731
    return ", ".join(fmt(a) if a == b else "%s → %s" % (fmt(a), fmt(b)) for a, b in segs)


def quorum_reached(approvals: list[str]) -> bool:
    return len([a for a in approvals if a == "approve"]) >= APPROVALS_NEEDED


def quorum_rejected(approvals: list[str]) -> bool:
    return len([a for a in approvals if a == "not_approve"]) >= APPROVALS_NEEDED


def senior_timers(now, al_start):
    """Dynamic nudge/escalate offsets — scale to time-until-the-AL-starts so the decision
    always lands before it begins. Returns (nudge_after_sec, escalate_after_sec)."""
    secs = max((al_start - now).total_seconds(), 0)
    nudge = min(12 * 3600, secs * 0.25)
    escalate = min(24 * 3600, secs * 0.5)
    return nudge, escalate
