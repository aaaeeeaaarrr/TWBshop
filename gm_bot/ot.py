"""OT pure logic. No DB/Telegram.

Time bank: granted OT banks (cap 14h, no money) → staff takes it back as REST via buyback at the
shop's safest times. Bank-cap helpers below are session-28.

Session 31 (see docs/OT_DESIGN.md) UNIFIED the entry: OT is no longer a separate Now/Later grant —
a senior REDEFINES a working day's shift (retime/move/extend) and the staff approves; OT is emergent
= hours worked beyond the normal shift length, and it nets against payback (one currency). The
unified helpers are in the session-31 block below.
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
# Session 31: UNIFIED "redefine-a-shift" model (see docs/OT_DESIGN.md). A senior retimes /
# moves / extends a working day's shift; the staff approves; OT is EMERGENT = hours worked
# BEYOND the person's normal shift length. No window logic, no OT-specific +10/−10 — normal
# late / leave-early / no-show rules apply to the approved [start,end] (the early +10 is the
# existing early-arrival bonus). PB and OT are ONE currency (time): an extension / earned OT
# clears outstanding PAYBACK first, the rest is OT. All times are minutes (caller converts
# datetimes; overnight => may exceed 1440, fine if kept ordered). Pure logic, no DB.
# ======================================================================================

OT_STEP_MIN = 30        # start-picker granularity (flip to 15 for finer)
MAX_EXTRA_HOURS = 4     # most OT (hours beyond normal length) the end-ladder offers


def ot_earned(worked_min: int, normal_len_min: int) -> int:
    """OT = hours worked BEYOND a normal shift length. Late/short already reduce worked_min, so a
    normal-length day (however shifted) earns 0 — that's the whole unified model."""
    return max(0, worked_min - normal_len_min)


def split_ot_pb(minutes: int, pb_balance_min: int) -> tuple[int, int]:
    """Split `minutes` of OT (or a planned extension) against an outstanding PAYBACK balance: it
    clears the debt FIRST, the remainder is OT. Returns (pb_cleared, ot). One currency (time)."""
    pb = max(0, pb_balance_min)
    pb_cleared = min(max(0, minutes), pb)
    return pb_cleared, max(0, minutes) - pb_cleared


def apply_ot_to_pb(ot_earned_min: int, pb_balance_min: int) -> tuple[int, int, int]:
    """After a shift is worked: OT earned pays down PB first, the rest banks. Returns
    (pb_cleared, ot_banked, new_pb_balance). My Schedule shows the net. Points are NOT touched here
    (reputation never nets — that stays on its own track)."""
    pb_cleared, ot_banked = split_ot_pb(ot_earned_min, pb_balance_min)
    return pb_cleared, ot_banked, max(0, pb_balance_min) - pb_cleared


def settle_shift(worked_min: int, normal_len_min: int, pb_balance_min: int) -> tuple[int, int, int]:
    """At checkout: OT = worked beyond normal length; it clears payback FIRST, the rest banks.
    Returns (ot_banked, pb_cleared, new_pb_balance). The whole money path in one call."""
    earned = ot_earned(worked_min, normal_len_min)
    pb_cleared, ot_banked = split_ot_pb(earned, pb_balance_min)
    return ot_banked, pb_cleared, max(0, pb_balance_min) - pb_cleared


def rest_redefine(ws_min: int, we_min: int, s_min: int, e_min: int) -> tuple[int, int, int] | None:
    """The shift-REDEFINE a booked OT-rest (buyback) creates — the rest eats INTO the shift at an
    edge, so the day's real shift is the remainder and attendance stays fair (no false 'late' for
    using earned rest): rest-at-start → [rest_end .. original_end]; rest-at-end → [start ..
    rest_start]. normal_len stays the FULL normal length (worked < normal → no OT, by design).
    Returns (start_min, end_min_absolute, normal_len), or None if the window isn't at an edge."""
    normal_len = (we_min - ws_min) % 1440 or 1440
    rest = (e_min - s_min) % 1440 or 1440
    if rest >= normal_len:
        return None
    if s_min % 1440 == ws_min % 1440:        # rest first → come in later
        st = e_min % 1440
        return st, st + (normal_len - rest), normal_len
    if e_min % 1440 == we_min % 1440:        # rest last → leave earlier
        st = ws_min % 1440
        return st, st + (normal_len - rest), normal_len
    return None


def _fmt_dur(mins: int) -> str:
    """Compact h/m for a button tag: 75→'1h15', 60→'1h', 45→'45m' (owner, Jun 15: minutes, not decimals
    like 1.25h)."""
    h, m = divmod(int(mins), 60)
    if h and m:
        return "%dh%02d" % (h, m)
    return ("%dh" % h) if h else ("%dm" % m)


def _ext_tag(pb_cleared: int, ot: int) -> str:
    """Button tag for an extension. Shows BOTH parts when it spans both (owner, Jun 15): an extension
    clearing 1h15 of UNBOOKED payback then earning 45m OT reads '+1h15 PB +45m OT' — not just one half,
    and in minutes not decimals. The caller MUST pass UNBOOKED payback (balance minus already-booked
    extensions), never the raw debt, or the +PB part is overstated and double-credits."""
    parts = []
    if pb_cleared > 0:
        parts.append("+%s PB" % _fmt_dur(pb_cleared))
    if ot > 0:
        parts.append("+%s OT" % _fmt_dur(ot))
    return " ".join(parts)


def end_option_tags(start_min: int, normal_len_min: int, pb_balance_min: int = 0,
                    max_extra_hours: int = MAX_EXTRA_HOURS, step_min: int = 60) -> list[tuple[int, str]]:
    """Change-time END buttons from a chosen start. First = the normal end (no tag); each step beyond
    carries '+NPB' (clearing debt) then '+MOT'. step default hourly (wider, 2/row in the UI). Returns
    [(end_min mod 1440, tag)]."""
    normal_end = start_min + normal_len_min
    out = [(normal_end % 1440, "")]
    extra = step_min
    while extra <= max_extra_hours * 60:
        pb_cleared, ot = split_ot_pb(extra, pb_balance_min)
        out.append(((normal_end + extra) % 1440, _ext_tag(pb_cleared, ot)))
        extra += step_min
    return out


def start_options(step_min: int = OT_STEP_MIN, earliest_min: int = 0) -> list[int]:
    """Change-time START buttons (12am..11:30pm at `step_min`). For TODAY pass earliest_min = the
    current minute-of-day to drop past times; future days pass 0."""
    return [m for m in range(0, 1440, step_min) if m >= earliest_min]
