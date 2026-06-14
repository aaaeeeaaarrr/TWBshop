"""Payback pure logic (session 28). No DB/Telegram.

Late minutes become a payback BALANCE worked off in slots glued to the staff's own shift
(before/after) on working days, plus one day-off option, at the shop's neediest times.
This module: slot-window geometry, the ignore-ladder stage machine, partial math.
(Need-ranking by coverage is a later refinement; windows here are correct + schedule-based.)
"""
from __future__ import annotations

from datetime import date, timedelta

_DOW = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}

PB_DEADLINE_DAYS = 14   # a debt must be worked off within 14 days (owner spec, session 28)

MAX_DAY_TOTAL_MIN = 15 * 60   # owner rule (Jun 11): one day's TOTAL work time never exceeds 15h


def day_ext_cap(normal_len_min: int) -> int:
    """Max extension minutes bookable onto a working day — normal shift + extension caps at 15h
    total. The remainder of a bigger debt books onto other days instead."""
    return max(0, MAX_DAY_TOTAL_MIN - max(0, normal_len_min or 0))


def unbooked(balance_min: int, pending_ext_min: int) -> int:
    """Remaining-to-book = open debt MINUS the extension already covered by approved upcoming
    redefines (booked payback slots AND senior-given extensions — the same hour is never owed
    twice). Every payback surface (picker, My-Schedule button, the ladder, the book tap itself)
    must size itself with THIS number, never the raw balance: sizing with the raw balance let
    staff book the same debt over and over and mint OT from the surplus (owner find, Jun 11)."""
    return max(0, max(0, balance_min or 0) - max(0, pending_ext_min or 0))


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


def dayoff_dates_ahead(day_off: str | None, leave_iso: set[str], start: date,
                       n_days: int) -> list[date]:
    """The DAY-OFF-weekday dates within the next `n_days` from `start` (inclusive), skipping leave.
    Inverse of working_days_ahead — for day-off payback / day-off OT options."""
    off = _DOW.get((day_off or "")[:3].title())
    if off is None:
        return []
    out, d, scanned = [], start, 0
    while scanned < n_days:
        if d.weekday() == off and d.isoformat() not in leave_iso:
            out.append(d)
        d += timedelta(days=1)
        scanned += 1
    return out


def swap_pairings(req_dates: list, partner_dates: list,
                  max_gap: int = 6, cap: int = 6) -> list[tuple]:
    """Valid day-off SWAP pairings between a requester and a partner (WF5). Each input is that
    person's REAL upcoming day-off occurrences. A pairing (req_dayoff_date, partner_dayoff_date) is
    valid when the two dates are within `max_gap` days of each other — a true trade where each ends
    up working the OTHER's day off, so headcount is unchanged on both dates (coverage-neutral by
    construction; no arbitrary day, no same-week constraint). Sorted soonest-first, de-duplicated,
    capped at `cap`. Empty when the two have the same day off (nothing to trade) or no pair is close
    enough."""
    pairs, seen = [], set()
    for r in req_dates:
        for p in partner_dates:
            if r == p:
                continue                              # same calendar date → not a trade
            if abs((p - r).days) <= max_gap and (r, p) not in seen:
                seen.add((r, p))
                pairs.append((r, p))
    pairs.sort(key=lambda t: (min(t), max(t)))
    return pairs[:cap]


def dayoff_windows(ws_min: int, we_min: int, minutes: int, step_min: int = 30,
                   margin_min: int = 0) -> list[tuple[int, int]]:
    """Candidate day-off windows (for payback OR OT) = a `minutes`-long block placed WITHIN the
    staff's regular shift hours [ws,we] — a 9pm–6am person gets night windows on their day off, never
    a 5am call (owner spec). Overnight-safe (we<ws wraps). `margin_min` widens the allowed band by that
    many minutes on each side of the regular hours (0 = strictly within-hours; 120 = ±2h). If the
    amount fills the whole band, the only window is the band itself. Returns [(start,end)] in clock
    minutes (mod 1440) for the caller to need-rank; the caller picks the neediest one."""
    span = ((we_min - ws_min) % 1440) or 1440
    band_start = ws_min - margin_min
    band_span = span + 2 * margin_min
    win = min(minutes, band_span)
    out, s, last = [], band_start, band_start + band_span - win
    while s <= last:
        out.append((s % 1440, (s + win) % 1440))
        s += step_min
    if not out:
        out = [(band_start % 1440, (band_start + win) % 1440)]
    return out


def slot_windows(ws_min: int, we_min: int, minutes: int) -> list[tuple[str, int, int]]:
    """For a working day: the before-shift and after-shift windows sized to `minutes`.
    Returns [(label, start_min, end_min)] — 'before' ends at shift start, 'after' begins
    at shift end. (Negative/over-1440 are wrapped by the caller into clock times.)"""
    return [
        ("before", (ws_min - minutes) % 1440, ws_min),
        ("after", we_min % 1440, (we_min + minutes) % 1440),
    ]


def takeback_windows(ws_min: int, we_min: int, minutes: int) -> list[tuple[str, int, int]]:
    """For TAKING BACK earned OT as rest (not payback): the rest sits at the EDGES of the shift,
    eating into it — come in later (rest the START) or leave earlier (rest the END). Returns
    [(label, start_min, end_min)] where the window is the rest period INSIDE the shift."""
    return [
        ("start late", ws_min % 1440, (ws_min + minutes) % 1440),   # come in `minutes` later
        ("leave early", (we_min - minutes) % 1440, we_min % 1440),  # leave `minutes` earlier
    ]


def redefine_window(ws_min: int | None, we_min: int | None, is_dayoff: bool,
                    s_min: int, e_min: int) -> tuple[int, int, int] | None:
    """The shift-REDEFINE a booked payback slot creates (owner unification, Jun 11 — a slot is
    not a separate 'mini-shift', it EXTENDS the shift and the settle engine credits the debt):
    - working day, slot glued BEFORE the shift → [slot_start, slot_start + slot + normal_len]
    - working day, slot glued AFTER the shift  → [shift_start, shift_start + normal_len + slot]
    - day off → the window itself with normal_len=0 (every worked minute is extension → credits)
    Returns (start_min, end_min_absolute, normal_len) — end may exceed 1440 (overnight-safe,
    same convention as the senior redefine ladder) — or None when the slot doesn't touch a
    shift edge (shouldn't happen with slot_windows-generated slots)."""
    slot = (e_min - s_min) % 1440 or 1440
    if is_dayoff:
        return s_min % 1440, (s_min % 1440) + slot, 0
    if ws_min is None or we_min is None:
        return None
    normal_len = (we_min - ws_min) % 1440 or 1440
    if e_min % 1440 == ws_min % 1440:      # before-shift slot: start earlier, same end
        st = s_min % 1440
        return st, st + slot + normal_len, normal_len
    if s_min % 1440 == we_min % 1440:      # after-shift slot: same start, end later
        st = ws_min % 1440
        return st, st + normal_len + slot, normal_len
    return None


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
