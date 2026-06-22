"""core.leave — annual-leave deduction math (channel-agnostic, per-tenant config). The balance core:
which days actually COST AL (never a day-off / already-absent day), the FROZEN per-day deduction map
(S1 — computed ONCE at approval so refund + audit read the row, never recompute), short-notice points,
and fractional hours-AL. Parity with live (gm_bot.al), drift-guarded by tests/test_core_leave.py.

PURE math only. The HIGH-RISK live orchestration that goes with it at cut-over — the atomic
deduct-at-approval + the symmetric refund-on-cancel (S1), the ≥2-senior quorum — stays a deliberate
live build. The shadow proves this math equals live first.
"""
from datetime import date, timedelta

SHORT_NOTICE_DAYS = 7           # <7 days ahead = short notice (points cost, not salary)
SHORT_NOTICE_PT_PER_MIN = 0.1   # per-tenant config (TWB), mirrors live

_DOW = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def is_short_notice(al_day: date, today: date) -> bool:
    return (al_day - today).days < SHORT_NOTICE_DAYS


def short_notice_days(al_days, today: date):
    return [d for d in al_days if is_short_notice(date.fromisoformat(d), today)]


def points_cost(short_days: int, shift_minutes: int) -> int:
    """Full-day short-notice points hit."""
    return round(SHORT_NOTICE_PT_PER_MIN * shift_minutes * short_days)


def fractional_al(hours_start_min: int, hours_end_min: int, shift_minutes: int) -> float:
    """Hours-AL as a fraction of an AL day: window / shift length (2dp)."""
    window = (hours_end_min - hours_start_min) % 1440
    if shift_minutes <= 0:
        return 0.0
    return round(window / shift_minutes, 2)


def _al_off(d: date, off_wd, non_working: set) -> bool:
    """Non-working for this staff — their weekly day-off, or any other absence in `non_working`."""
    return (off_wd is not None and d.weekday() == off_wd) or (d.isoformat() in non_working)


def al_charged_days(al_days, day_off=None, non_working=None):
    """The selected dates that actually COST AL — never the staff's day-off, nor any day already away."""
    off = _DOW.get((day_off or "")[:3].title()) if day_off else None
    nw = non_working or set()
    if off is None and not nw:
        return sorted(al_days)
    return [d for d in sorted(al_days) if not _al_off(date.fromisoformat(d), off, nw)]


def al_day_count(al_days, kind: str, frac_per_day: float = 1.0, day_off=None, non_working=None) -> float:
    """Total AL deducted: full days = #charged; hours = frac × #charged. Day-off / already-absent free."""
    n = len(al_charged_days(al_days, day_off, non_working))
    return round(n * (frac_per_day if kind == "hours" else 1.0), 2)


def al_deduction_map(al_days, kind: str, frac_per_day: float = 1.0, day_off=None,
                     non_working=None, no_deduct: bool = False):
    """The FROZEN per-day AL charge: {date: amount} for EVERY selected day (the charge on a working day,
    0 on a day-off / already-absent / PH-comp day) + the total. By construction keys == al_days and
    sum == al_day_count, so refund + audit read the row and never recompute (S1)."""
    per_day = 0.0 if no_deduct else (frac_per_day if kind == "hours" else 1.0)
    charged = set(al_charged_days(al_days, day_off, non_working))
    dmap = {d: (per_day if d in charged else 0) for d in al_days}
    return dmap, round(sum(dmap.values()), 2)
