"""core.points — check-in points (channel-agnostic, per-tenant config). Parity with gm_bot.points.

A check-in generates point EVENTS derived from the verdict: early → early_arrival(+10, qty 1); late →
split into late_uninformed (−2/min, the minutes elapsed BEFORE they declared) + late_informed (−1/min,
the minutes after they declared); on_time → none. The split is the only non-trivial bit. Values are
per-tenant config (TWB: +10 / −1 / −2); quantity is the unit count live records.
"""


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
