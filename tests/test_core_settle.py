"""core.settle — DRIFT-GUARD parity with live (gm_bot.ot) across the settle space + worked-min cases.
The platform carries its own copy; this test locks it to live so neither can silently diverge."""
from datetime import datetime, timedelta, timezone

import core.settle as cs
import gm_bot.ot as live

UTC = timezone.utc


def test_settle_math_parity_with_live():
    # cross-check ot_earned / split_ot_pb / settle_shift over a wide grid (no cap = parity domain)
    for worked in (0, 60, 480, 540, 600, 720, 900):
        for normal in (480, 540, 600):
            assert cs.ot_earned(worked, normal) == live.ot_earned(worked, normal)
            for pb in (0, 30, 120, 600, 1000):
                assert cs.split_ot_pb(cs.ot_earned(worked, normal), pb) == \
                       live.split_ot_pb(live.ot_earned(worked, normal), pb)
                ot_banked, pb_cleared, new_pb = live.settle_shift(worked, normal, pb)
                got = cs.settle_shift(worked, normal, pb, bank_min=0)   # no cap pressure → matches live
                assert (got["ot_banked"], got["pb_cleared"], got["new_pb"]) == (ot_banked, pb_cleared, new_pb)


def test_settle_bank_cap_drops_overflow_honestly():
    # 6h OT, no payback, bank already at 13h (60 min room) → bank 60, drop 300
    r = cs.settle_shift(worked_min=600, normal_len_min=240, pb_balance_min=0, bank_min=13 * 60)
    assert r["ot_earned"] == 360 and r["ot_banked"] == 60 and r["ot_dropped"] == 300
    assert r["new_bank"] == cs.BANK_CAP_MIN


def test_worked_minutes_caps_at_edges():
    s = datetime(2026, 6, 20, 23, 0, tzinfo=UTC)          # start
    e = s + timedelta(hours=9)                             # end
    # arrived 10 min early, left 20 min late → worked = the full 9h (edges clamp)
    assert cs.worked_minutes(s - timedelta(minutes=10), e + timedelta(minutes=20), s, e) == 540
    # arrived 30 late, left on time → 8h30
    assert cs.worked_minutes(s + timedelta(minutes=30), e, s, e) == 510
    # left 2h early → 7h
    assert cs.worked_minutes(s, e - timedelta(hours=2), s, e) == 420
