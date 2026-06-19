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
EARLY_BONUS_MIN = 5    # ≥5 min early earns the +10 (owner Jun 18: arriving exactly 5 min early counts)
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
    if early >= EARLY_BONUS_MIN:
        return "early", early
    if late > GRACE_MIN:
        return "late", late
    return "ontime", 0


def is_due(event_min: int, now_min: int) -> bool:
    """A per-minute scheduler tick: fire an event when the clock reaches its minute.
    (The job runs ~every 60s; exact-minute match avoids double-fires.)"""
    return event_min == now_min


CHECKIN_PRE_MIN = 60      # accept a check-in up to 60 min before the shift start (early birds + T-10)
CHECKIN_POST_MIN = 120    # accept an end-of-shift checkout / late check-in up to 2 h past the end


def shift_for_now(now_min: int, candidates: list[tuple[int, bool, int | None, int | None]],
                  pre: int = CHECKIN_PRE_MIN, post: int = CHECKIN_POST_MIN) -> tuple[int | None, int | None]:
    """Which scheduled shift a live-location ping at `now_min` (minute-of-day) belongs to — the fix for
    the overnight-binding bug. A baker's 06:00 end-ping is on the NEXT calendar day, so binding to
    `now.date()` filed it under the wrong shift (phantom next-day session + false no-show). Instead we
    test each candidate shift and bind to the one whose window covers `now`.

    `candidates`: (day_offset, working, ws, we) per candidate day, TODAY-FIRST (0=today, -1=yesterday).
      ws/we = start/end minute-of-day as resolve_day returns them (we may be < ws for an overnight shift).
    Returns (day_offset, ws_norm) of the matching shift (ws_norm in 0..1439), or (None, None) if none is
    plausible. Today is preferred (listed first); yesterday only claims a ping if its shift ran PAST
    midnight (overnight) and `now` still falls inside [start-pre, end+post). Pure — no DB/Telegram."""
    for off, working, ws, we in candidates:
        if not working or ws is None or we is None:
            continue
        we2 = we + 1440 if we <= ws else we          # overnight end rolls past midnight (21:00→06:00)
        if off < 0 and we2 <= 1440:
            continue                                  # a past day that didn't run past its own midnight
        now_abs = (-off) * 1440 + now_min             # minutes from that day's midnight to now
        if ws - pre <= now_abs < we2 + post:
            return off, ws % 1440
    return None, None


def offshift_reason(now_min: int, today_dec: dict,
                    pre: int = CHECKIN_PRE_MIN, post: int = CHECKIN_POST_MIN) -> str:
    """Why a live-location ping did NOT bind to a shift (i.e. shift_for_now returned None) — so the bot
    can give a short, kind reply instead of SILENCE. Silence reads to staff as "the bot is broken" and,
    worse, would hide a genuinely wrong schedule (it looks identical to a real day-off bug). `today_dec`
    = resolve_day() for today. Returns:
      'off'       — not scheduled to work today (day off / approved leave / no shift times set);
      'too_early' — scheduled today but the check-in window hasn't opened yet (>pre min before start);
      'over'      — scheduled today but the window has already closed (shift done / missed).
    This is only ever reached on the no-bind path, so 'working today AND now inside the window' cannot
    occur here (shift_for_now would have bound it). Pure — no DB/Telegram."""
    if not today_dec or not today_dec.get("working"):
        return "off"
    ws = today_dec.get("start_min")
    we = today_dec.get("end_min")
    if ws is None or we is None:
        return "off"
    we2 = we + 1440 if we <= ws else we          # overnight end rolls past midnight
    if now_min < ws - pre:
        return "too_early"
    if now_min >= we2 + post:
        return "over"
    return "over"          # within-window is unreachable here; safe catch-all
