"""Check-in core — pure logic (verdict + scheduling), no DB/Telegram.

The real check-in engine rides on this + flow_state + attendance_sessions. Everything here
is deterministic and unit-tested; the job/handler in bot.py wire it to Telegram, GATED behind
the `attendance_live` master switch (OFF until the owner goes live → zero staff contact).

Rules (locked spec, session 28):
- ≤5 min late = FREE; >5 min → ALL minutes count (from minute 1, not minus 5).
- arrive >5 min EARLY (in zone) = +10 points (pending).
- proof = live location inside the 100m zone; a static pin never counts.
"""
from __future__ import annotations

GRACE_MIN = 5          # ≤5 min late is free
EARLY_BONUS_MIN = 5    # >5 min early earns the +10


def relative_minutes(now_min: int, shift_start_min: int) -> tuple[int, int]:
    """(early, late) minutes vs shift start, on the 24h circle. Exactly one is non-zero
    (or both 0 at the exact start). >12h before is read as 'early', else 'late'."""
    rel = (now_min - shift_start_min) % 1440
    if rel == 0:
        return 0, 0
    if rel > 720:                 # before the shift
        return 1440 - rel, 0
    return 0, rel                 # at/after the shift


def verdict(now_min: int, shift_start_min: int, in_zone: bool) -> tuple[str, int]:
    """Classify a check-in attempt → (state, minutes).
    states: 'not_here' (outside zone) · 'early' (+points, minutes early) ·
            'ontime' (within grace either side) · 'late' (minutes late, counts as payback)."""
    if not in_zone:
        return "not_here", 0
    early, late = relative_minutes(now_min, shift_start_min)
    if early > EARLY_BONUS_MIN:
        return "early", early
    if late > GRACE_MIN:
        return "late", late
    return "ontime", 0


def is_due(event_min: int, now_min: int) -> bool:
    """A per-minute scheduler tick: fire an event when the clock reaches its minute.
    (The job runs ~every 60s; exact-minute match avoids double-fires.)"""
    return event_min == now_min
