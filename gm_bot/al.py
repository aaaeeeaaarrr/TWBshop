"""Annual-leave pure logic (session 28). No DB/Telegram.

AL costs AL-days (never salary). ≥7 days ahead = free; 0–6 days = short-notice, priced in
points. ≥2 senior approvals (a senior can't approve their own). Hours-AL deducts fractionally.
This module: short-notice detection, points cost, fractional deduction, quorum, availability set.
Gated behind attendance_live like everything else.
"""
from __future__ import annotations

from datetime import date, timedelta

SHORT_NOTICE_DAYS = 7          # <7 days ahead = short notice (points cost)
SHORT_NOTICE_PT_PER_MIN = 0.1  # ACTIVE (owner, Jun 11) — mirrors points_rules short_notice_al
APPROVALS_NEEDED = 2


_DOW_BACK = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def back_at_work_date(days: list[str], day_off: str | None, non_working: set | None = None) -> date:
    """The first WORKING day after an AL span — skips the leave days themselves, the staffer's
    weekly day-off, and any other absence (other AL/special/swap) bridged by the span. Feeds the
    'Back at work:' line of the Supervisors notice (locked format, owner session 28)."""
    occupied = set(days) | set(non_working or ())
    off = _DOW_BACK.get((day_off or "")[:3].lower())
    d = max(date.fromisoformat(x) for x in days) + timedelta(days=1)
    for _ in range(60):
        if d.isoformat() not in occupied and d.weekday() != off:
            return d
        d += timedelta(days=1)
    return d


def is_short_notice(al_day: date, today: date) -> bool:
    return (al_day - today).days < SHORT_NOTICE_DAYS


def short_notice_days(al_days: list[str], today: date) -> list[str]:
    return [d for d in al_days if is_short_notice(date.fromisoformat(d), today)]


def points_cost(short_days: int, shift_minutes: int) -> int:
    """Rough full-day short-notice points hit."""
    return round(SHORT_NOTICE_PT_PER_MIN * shift_minutes * short_days)


def fractional_al(hours_start_min: int, hours_end_min: int, shift_minutes: int) -> float:
    """Hours-AL as a fraction of an AL day: window / shift length, rounded to 2dp."""
    window = (hours_end_min - hours_start_min) % 1440
    if shift_minutes <= 0:
        return 0.0
    return round(window / shift_minutes, 2)


_DOW = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def _al_off(d: date, off_wd: int | None, non_working: set) -> bool:
    """Is this date a NON-WORKING day for the staff — their weekly day-off, or any other absence
    passed in `non_working` (another approved AL, a public holiday, a swap day-off, etc.)?"""
    return (off_wd is not None and d.weekday() == off_wd) or (d.isoformat() in non_working)


def al_charged_days(al_days: list[str], day_off: str | None = None,
                    non_working: set | None = None) -> list[str]:
    """The selected dates that actually COST AL — never the staff's day-off, nor any other day
    they're already away (in `non_working`: other approved AL, PH, swap-off…)."""
    off = _DOW.get((day_off or "")[:3].title()) if day_off else None
    nw = non_working or set()
    if off is None and not nw:
        return sorted(al_days)   # nothing to exclude → no date parsing (accepts non-ISO placeholders)
    return [d for d in sorted(al_days) if not _al_off(date.fromisoformat(d), off, nw)]


def al_day_count(al_days: list[str], kind: str, frac_per_day: float = 1.0,
                 day_off: str | None = None, non_working: set | None = None) -> float:
    """Total AL deducted: full days = #charged days; hours = frac × #charged days. Day-off and any
    other already-absent day (`non_working`) are excluded (never charged)."""
    n = len(al_charged_days(al_days, day_off, non_working))
    return round(n * (frac_per_day if kind == "hours" else 1.0), 2)


def al_deduction_map(al_days: list[str], kind: str, frac_per_day: float = 1.0,
                     day_off: str | None = None, non_working: set | None = None,
                     no_deduct: bool = False) -> tuple[dict, float]:
    """The FROZEN per-day AL charge: {date: amount} for EVERY selected day — the charge on a working
    day, 0 on a day-off / already-absent day / PH-comp request — plus the total. By construction
    keys == al_days (so refund + audit read the row, never recompute) and sum == al_day_count. This
    is the single place the deduction is computed, so the value frozen at approval is exact (S1)."""
    per_day = 0.0 if no_deduct else (frac_per_day if kind == "hours" else 1.0)
    charged = set(al_charged_days(al_days, day_off, non_working))
    dmap = {d: (per_day if d in charged else 0) for d in al_days}
    return dmap, round(sum(dmap.values()), 2)


def al_span_label(al_days: list[str], day_off: str | None = None,
                  non_working: set | None = None) -> str:
    """Format the leave as 'from → to' segments, BRIDGING any day the staff is NOT in for any
    reason — their day-off, another approved AL, a public holiday, a swap day-off (all passed via
    `non_working`/`day_off`). A genuine WORKING-day gap splits into separate segments (so we never
    imply days off he actually works)."""
    days = sorted({date.fromisoformat(d) for d in al_days})
    if not days:
        return ""
    off = _DOW.get((day_off or "")[:3].title()) if day_off else None
    nw = non_working or set()
    segs, s, e = [], days[0], days[0]
    for d in days[1:]:
        between = [e + timedelta(days=i) for i in range(1, (d - e).days)]
        if (d - e).days == 1 or (between and all(_al_off(g, off, nw) for g in between)):
            e = d                       # consecutive, or only non-working day(s) in the gap → bridge
        else:
            segs.append((s, e)); s = e = d
    segs.append((s, e))
    fmt = lambda x: x.strftime("%a %d/%m")   # noqa: E731
    return ", ".join(fmt(a) if a == b else "%s → %s" % (fmt(a), fmt(b)) for a, b in segs)


APPROVALS_NEEDED_SENIOR = 1   # a senior's OWN AL/swap needs just 1 other senior's approval


def approvals_needed(is_senior: bool) -> int:
    """How many senior approvals a request needs: a senior's own AL/swap → 1 other senior;
    regular staff → 2 seniors."""
    return APPROVALS_NEEDED_SENIOR if is_senior else APPROVALS_NEEDED


def quorum_reached(approvals: list[str], needed: int = APPROVALS_NEEDED) -> bool:
    return len([a for a in approvals if a == "approve"]) >= needed


def quorum_rejected(approvals: list[str], needed: int = APPROVALS_NEEDED) -> bool:
    return len([a for a in approvals if a == "not_approve"]) >= needed


def senior_timers(now, al_start):
    """Dynamic nudge/escalate offsets — scale to time-until-the-AL-starts so the decision
    always lands before it begins. Returns (nudge_after_sec, escalate_after_sec)."""
    secs = max((al_start - now).total_seconds(), 0)
    nudge = min(12 * 3600, secs * 0.25)
    escalate = min(24 * 3600, secs * 0.5)
    return nudge, escalate
