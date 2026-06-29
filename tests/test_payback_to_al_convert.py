"""payback_to_al conversion (gm_bot.al.payback_to_al_days): owed pay-back MINUTES → AL DAYS, proportional
to the staffer's OWN scheduled shift (owner rule 2026-06-29: a full missed shift = 1.0 AL). Pure + fail-safe.
This is the locked conversion both the deduction AND its papers-accept reversal derive from (same number)."""
from gm_bot import al


def test_full_shift_is_one_al_day():
    assert al.payback_to_al_days(540, 540) == 1.0
    assert al.payback_to_al_days(480, 480) == 1.0


def test_partial_is_proportional_and_rounded():
    assert al.payback_to_al_days(270, 540) == 0.5
    assert al.payback_to_al_days(302, 540) == 0.56      # 0.5592… → 0.56
    assert al.payback_to_al_days(30, 540) == 0.06       # a small late → a tiny fraction


def test_failsafe_on_zero_or_unknown_shift():
    assert al.payback_to_al_days(0, 540) == 0.0
    assert al.payback_to_al_days(540, 0) == 0.0         # unknown shift → 0 (never deduct garbage)
    assert al.payback_to_al_days(540, None) == 0.0
    assert al.payback_to_al_days(-50, 540) == 0.0       # negative owed clamped → 0
