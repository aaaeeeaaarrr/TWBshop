"""core.sick — own-sick outcome rule (channel-agnostic). The distinguishing fact is CHECK-IN:

  • checked in  → "leave-early sick" (fell ill on the job): NO −15 late-inform penalty, and payback only
                  the REMAINING unworked time ("pay-back from now"), not the whole shift.
  • not checked in → "absent sick": the −15 applies if reported late (within the threshold of start, or
                  after it), and payback = the full shift.

Doctor's papers cancel the payback either way. Mirrors the live rule (gm_bot `_sickme_book` gate +
`v_late_sick_penalty` exemption); pure, so it's the platform's own copy. (owner Jun 22)
"""
from core.points import late_sick_points


def sick_outcome(checked_in: bool, late_inform_mins, shift_min, remaining_min,
                 late_threshold_min: int = 30) -> dict:
    """The point events + payback minutes an own-sick declaration produces.
    `late_inform_mins`: minutes until shift start (negative = already started; None = no shift).
    Returns {points: [(cause, quantity)], payback_min}."""
    if checked_in:
        return {"points": [], "payback_min": max(0, int(remaining_min))}        # leave-early: no −15, remaining only
    late = late_inform_mins is not None and late_inform_mins < late_threshold_min
    return {"points": late_sick_points() if late else [], "payback_min": max(0, int(shift_min))}
