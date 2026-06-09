"""Give-OT / time-bank pure logic (session 28). No DB/Telegram.

Seniors GRANT OT → owner approves → hours bank (cap 14h, no money) → staff takes buyback rest at
the shop's SAFEST (most-surplus) times. NOW-OT = present staff (consent + location/senior proof);
FUTURE-OT = accept → scheduled work slot. Accepted = commitment.
"""
from __future__ import annotations

BANK_CAP_MIN = 14 * 60   # 14 hours


def cap_room(current_bank_min: int) -> int:
    """Minutes of OT still grantable before the 14h cap."""
    return max(0, BANK_CAP_MIN - current_bank_min)


def grant_fits(current_bank_min: int, grant_min: int) -> bool:
    return grant_min <= cap_room(current_bank_min)


def duration_options(current_bank_min: int) -> list[int]:
    """30min→6h in 30-min steps, capped to remaining bank room."""
    room = cap_room(current_bank_min)
    return [m for m in range(30, 361, 30) if m <= room]


# ======================================================================================
# Session 31: SHIFT-EXTENSION OT model (see docs/OT_DESIGN.md). Supersedes the Now/Later
# entry split. OT extends a working day's shift edge — earlier start and/or later end.
# Credit = in-zone time ∩ UNION of sanctioned OT windows (never summed across overlapping
# grants), capped, banked at the day's checkout. Points: +10 early to the OT start, −10
# "very late" (completed under HALF the committed OT — ghost OR 5-min cameo). Time worked
# is ALWAYS credited; early can never combine with a no-show.
# All times are minutes on a MONOTONIC axis (caller converts datetimes; overnight => may
# exceed 1440, fine as long as ordered).
# ======================================================================================

NO_SHOW_RATIO = 0.5      # completed below this fraction of committed OT = "very late" / no-show
EARLY_GRACE_MIN = 5      # must beat the OT start by MORE than this to earn the early bonus
PTS_EARLY = 10
PTS_NO_SHOW = -10
MAX_PRE_SHIFT_HOURS = 4  # picker: OT may start at most this many hours before the shift


def union_windows(shift_start, shift_end, grants):
    """grants: iterable of (ot_start, ot_end). Returns (pre_start, post_end) — the EXTENDED edges:
    earliest pre-shift start (< shift_start) and latest post-shift end (> shift_end), or None on a
    side with no grant. Overlapping/duplicate grants on a side collapse into one window (the union),
    so credit is never double-counted."""
    pre_starts = [s for (s, e) in grants if s < shift_start]
    post_ends = [e for (s, e) in grants if e > shift_end]
    return (min(pre_starts) if pre_starts else None,
            max(post_ends) if post_ends else None)


def committed_ot(shift_start, shift_end, grants):
    """Total sanctioned OT minutes for the day (pre head + post tail), counted ONCE via the union."""
    pre_start, post_end = union_windows(shift_start, shift_end, grants)
    pre = (shift_start - pre_start) if pre_start is not None else 0
    post = (post_end - shift_end) if post_end is not None else 0
    return pre + post


def worked_ot(shift_start, shift_end, grants, checkin, checkout):
    """OT minutes ACTUALLY worked = overlap of in-zone presence [checkin, checkout] with the union OT
    windows: pre head [pre_start, shift_start] + post tail [shift_end, post_end]. Never counts regular
    shift time; never double-counts overlapping grants; capped by the windows. 0 if checkout<=checkin."""
    if checkout <= checkin:
        return 0
    pre_start, post_end = union_windows(shift_start, shift_end, grants)
    worked = 0
    if pre_start is not None:
        worked += max(0, min(checkout, shift_start) - max(checkin, pre_start))
    if post_end is not None:
        worked += max(0, min(checkout, post_end) - max(checkin, shift_end))
    return worked


def ot_outcome(shift_start, shift_end, grants, checkin, checkout):
    """Return (worked_min, label, points). `worked_min` is ALWAYS credited/paid.
      - 'no_show'  −10 : worked < HALF the committed OT (ghost OR 5-min cameo). Wins over 'early'.
      - 'early'    +10 : arrived MORE than the grace before the OT start, and NOT a no-show.
                         (before-shift only — after-shift they were already at work.)
      - 'ok'         0 : did at least half; on-time / late-but-worked.
      - 'none'       0 : no OT grant for the day.
    """
    committed = committed_ot(shift_start, shift_end, grants)
    worked = worked_ot(shift_start, shift_end, grants, checkin, checkout)
    if committed <= 0:
        return (worked, "none", 0)
    if worked < NO_SHOW_RATIO * committed:
        return (worked, "no_show", PTS_NO_SHOW)   # early bonus NEVER applies to a no-show
    pre_start, _ = union_windows(shift_start, shift_end, grants)
    if pre_start is not None and (pre_start - checkin) > EARLY_GRACE_MIN:
        return (worked, "early", PTS_EARLY)
    return (worked, "ok", 0)


def pre_shift_start_options(shift_start, max_hours=MAX_PRE_SHIFT_HOURS, step_min=60):
    """Picker: before-shift OT start options, earliest first (e.g. 3,4,5,6am for a 7am shift, 4h cap).
    Each auto-confirms to [option, shift_start]."""
    return [shift_start - m for m in range(max_hours * 60, 0, -step_min)]


def post_shift_end_options(shift_end, max_hours=MAX_PRE_SHIFT_HOURS, step_min=60):
    """Picker: after-shift OT end options (start pinned at shift_end), nearest first."""
    return [shift_end + m for m in range(step_min, max_hours * 60 + 1, step_min)]
