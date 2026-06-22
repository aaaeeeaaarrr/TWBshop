"""core.points — check-in points (channel-agnostic, per-tenant config). Parity with gm_bot.points.

Design (live's, kept): RECORD raw events (cause + quantity); DERIVE points later = Σ value×quantity over
a catalogue, so changing a value re-scores history fairly. A check-in emits early_arrival(+10) OR the
late split (−1/−2); an absence emits no_show(−2/shift-min); late-sick emits late_sick_inform(−15).
The catalogue is per-tenant config (these = TWB's); drift-guarded == gm_bot.points.CATALOGUE.
"""

# cause → points value (TWB). Drift-guarded against gm_bot.points.CATALOGUE by tests/test_core_points.py.
CATALOGUE = {
    "early_arrival": 10, "late_informed": -1, "late_uninformed": -2, "no_show": -2,
    "return_after_doctor": 15, "ot_no_show": -30, "short_notice_al": -0.1,
    "late_sick_inform": -15, "owner_adjustment": 1,
}


def split_late(late_min, declare_offset_min):
    """(uninformed_min, informed_min). declare_offset_min = minutes AFTER shift start when they declared
    (≤0 = declared before start → all informed; None = never declared → all uninformed). Parity with
    gm_bot.points.split_late."""
    late_min = max(0, int(late_min))
    if declare_offset_min is None:
        return late_min, 0
    un = max(0, min(late_min, int(declare_offset_min)))
    return un, late_min - un


def checkin_points(state, late_min, early_min, declare_offset_min=None):
    """The point events a check-in generates, as [(cause, quantity)] — comparable to live's points_events
    for that staff+date. Empty for on_time."""
    if state == "early":
        return [("early_arrival", 1)]
    if state == "late":
        un, inf = split_late(late_min, declare_offset_min)
        out = []
        if un:
            out.append(("late_uninformed", un))
        if inf:
            out.append(("late_informed", inf))
        return out
    return []


def no_show_points(shift_minutes) -> list:
    """Never arrived on a working day → no_show, quantity = the shift's minutes (−2/min)."""
    return [("no_show", int(shift_minutes))]


def late_sick_points() -> list:
    """Told us sick within 30 min of start / after it (own-sick) → the −15 Late-Informing event."""
    return [("late_sick_inform", 1)]


def points_for(events) -> float:
    """DERIVE points from raw events [(cause, quantity)] via the catalogue: Σ value × quantity. Unknown
    causes score 0 (forward-compatible). This is the platform's points total (per-tenant catalogue)."""
    return round(sum(CATALOGUE.get(c, 0) * q for c, q in events), 2)
