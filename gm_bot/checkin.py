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
AUTO_CHECKOUT_GRACE_MIN = 3    # a live share seen in-zone within this many min of shift end = present


def is_share_stop(is_edited: bool, live_period) -> bool:
    """A live-location share that has been STOPPED (the live message turns static) arrives as an
    EDITED message whose `live_period` is gone. That is not a presence proof — the scheduler must
    not auto-check-out on it, and we record it as 'no longer present'. A one-shot static PIN arrives
    as a NEW message (never an edit), so it never matches here; an active live update keeps
    live_period set, so it doesn't match either. Pure — no Telegram objects."""
    return bool(is_edited) and not live_period


def can_auto_checkout(ping, now, grace_min: int = AUTO_CHECKOUT_GRACE_MIN) -> bool:
    """Spec §3.7: at shift end, if the staffer's live location has stayed ON and IN-ZONE we already
    know they were here to the last minute — close silently, no "did you leave early?" chase. True
    only when the freshest ping is in-zone AND recent enough to mean the share is still live (a
    stationary Telegram live-share heartbeats every few minutes; `grace_min` absorbs the gaps).
    A stale ping (share turned off) or an out-of-zone ping (they walked off, OR a stop was recorded
    as not-in-zone) → False → ask the normal way. `ping` = {in_zone, ts(tz-aware)} or None;
    `now` = tz-aware now. Pure — no DB/Telegram."""
    if not ping or not ping.get("in_zone") or not ping.get("ts"):
        return False
    return 0 <= (now - ping["ts"]).total_seconds() <= grace_min * 60


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
