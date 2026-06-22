"""core.leave — DRIFT-GUARD parity with live (gm_bot.al) across the AL deduction space. The platform
carries its own copy; this locks it to live so the balance-math can't silently diverge. Plus the S1
frozen-map invariants (keys == selection, sum == count)."""
from datetime import date

import core.leave as cl
import gm_bot.al as live

TODAY = date(2026, 6, 22)
# a span with a working gap, the staff's Sunday off, and an already-absent day
DAYS = ["2026-06-23", "2026-06-24", "2026-06-26", "2026-06-28", "2026-06-29"]


def test_charged_days_and_count_parity():
    for day_off in (None, "Sunday", "Mon"):
        for nw in (None, {"2026-06-24"}):
            assert cl.al_charged_days(DAYS, day_off, nw) == live.al_charged_days(DAYS, day_off, nw)
            for kind in ("days", "hours"):
                assert cl.al_day_count(DAYS, kind, 0.5, day_off, nw) == \
                       live.al_day_count(DAYS, kind, 0.5, day_off, nw)


def test_deduction_map_parity_and_S1_invariants():
    for day_off in (None, "Sunday"):
        for no_deduct in (False, True):
            dmap, total = cl.al_deduction_map(DAYS, "days", 1.0, day_off, None, no_deduct)
            lmap, ltot = live.al_deduction_map(DAYS, "days", 1.0, day_off, None, no_deduct)
            assert (dmap, total) == (lmap, ltot)
            assert set(dmap.keys()) == set(DAYS)            # S1: every selected day has a frozen charge
            assert round(sum(dmap.values()), 2) == total    # S1: sum == count (refund reads the row)


def test_short_notice_and_fractional_parity():
    assert cl.short_notice_days(DAYS, TODAY) == live.short_notice_days(DAYS, TODAY)
    for sm in (480, 540, 600):
        assert cl.points_cost(2, sm) == live.points_cost(2, sm)
        assert cl.fractional_al(540, 780, sm) == live.fractional_al(540, 780, sm)
