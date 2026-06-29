"""gm_bot.checkin_net — the C2 cut-over BRIDGE: the live check-in verdict routed through core.flip's
instant-revert net (the self-healing program, docs/SELF_HEALING_AND_SHADOW_PROGRAM.md).

Kept OUT of the pure gm_bot/checkin.py (which is intentionally DB-free + unit-tested as pure) because
this one helper does a DB round-trip — reading the per-(org, path) authority flag and logging divergence
— via core.flip.

Behaviour, by construction:
  • FLAG OFF (the default for every org/path) → returns (live_state, live_mins, False) BYTE-IDENTICAL to
    today. core is never consulted for the result; a botched core verdict cannot affect live.
  • FLAG ON  → core.attendance.verdict (parity-locked to gm_bot.checkin.verdict) becomes authoritative;
    the old engine shadows it; the net AUTO-REVERTS to live the instant recent divergence breaches the
    safety threshold (returns auto_reverted=True so the caller can alarm).
Fail-safe: ANY error computing core's verdict → compare live-vs-live → returns live unchanged.

Parity note (verified line-by-line for TWB's 5/5 grace/early config): core.attendance.verdict and
gm_bot.checkin.verdict share the same 24h-circle math + the same grace/early thresholds, and this bridge
feeds core the SAME resolved start (`ws`) live used, then routes the RAW verdict (grace / points / payback
stay live, applied to the chosen result). So flipping 'checkin' for TWB is expected to be a true no-op;
the net + the Sentinel `detect_flip_divergence` detector are the safety belt for any unenumerated edge.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_TZ = "Asia/Phnom_Penh"


def verdict_via_net(now_dt, shift_date, ws: int, grace_min: int, early_bonus_min: int,
                    live_state: str, live_mins: int, org_id: str = "twb"):
    """Route the live check-in verdict (live_state, live_mins) through core.flip.decide for
    (org_id, 'checkin'). Returns (state, mins, auto_reverted). See the module docstring for the safety
    guarantees.

    now_dt: the tz-aware check-in instant (live's now_pp). shift_date: 'YYYY-MM-DD' business day.
    ws: the RESOLVED (redefine-aware) shift start as minute-of-day — the SAME value live passed to
    gm_bot.checkin.verdict, so core judges against the identical start.
    """
    try:
        from core import flip
        from core.attendance import verdict as core_verdict
        tz = ZoneInfo(_TZ)
        start_dt = datetime.fromisoformat(str(shift_date)).replace(tzinfo=tz) + timedelta(minutes=int(ws))
        cs, c_late, c_early = core_verdict(now_dt, start_dt, _TZ, grace_min, early_bonus_min)
        cstate = "ontime" if cs == "on_time" else cs                 # core vocab → live vocab
        cmins = c_late if cstate == "late" else (c_early if cstate == "early" else 0)
        (state, mins), reverted = flip.decide(org_id, "checkin", (cstate, cmins), (live_state, live_mins))
        return state, mins, reverted
    except Exception:
        return live_state, live_mins, False


def points_via_net(state, late_min, early_min, declare_offset_min, live_events, org_id: str = "twb"):
    """D2 (points cut-over): route the check-in POINTS events through core.flip.decide for (org_id,
    'points'). Returns (events, auto_reverted). FLAG OFF (the default) → (live_events, False) byte-identical
    to today. FLAG ON → core.points.checkin_points (parity-locked to gm_bot.points) is authoritative, with
    auto-revert on divergence. Fail-safe: ANY error → live_events. `live_events` / the result are a list of
    (cause, quantity) for points_record. core's vocab matches live ('early'/'late'/'ontime' → [] for ontime)."""
    try:
        from core import flip
        from core.points import checkin_points
        core_events = checkin_points(state, int(late_min or 0), int(early_min or 0), declare_offset_min)
        chosen, reverted = flip.decide(org_id, "points", core_events, live_events)
        return chosen, reverted
    except Exception:
        return live_events, False


def settle_via_net(core_vals, live_vals, org_id: str = "twb"):
    """D2 (settle cut-over): route the checkout settle decision (pb_cleared, ot_banked) through
    core.flip.decide for (org_id, 'settle'). Returns (vals, auto_reverted). FLAG OFF (the default) →
    (live_vals, False) byte-identical to today. FLAG ON → core's values (parity: core.settle.settle_shift
    for a normal day + settle_payback_slot for a payback slot), auto-reverting on divergence. Fail-safe:
    ANY error → live_vals. The caller computes both (pb_cleared, ot_banked) tuples (core's PURELY, no side
    effects) and applies the CHOSEN one, so OFF is byte-identical by construction."""
    try:
        from core import flip
        chosen, reverted = flip.decide(org_id, "settle", core_vals, live_vals)
        return chosen, reverted
    except Exception:
        return live_vals, False
