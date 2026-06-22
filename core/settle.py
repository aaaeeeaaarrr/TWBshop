"""core.settle — checkout settle math (channel-agnostic, per-tenant config). The MONEY core:
worked → OT (hours beyond the normal shift length) → clears outstanding PAYBACK first, the rest banks.
One currency (time). Parity with live (gm_bot.ot), drift-guarded by tests/test_core_settle.py.

This is the PURE math only. The HIGH-RISK orchestration that goes with it at cut-over — WHICH debt, the
atomic claim-or-reject on the bank, the redefine window — stays a deliberate live build (atomic-claim-
first, per docs/STATE_INTEGRITY_LAWS.md). The shadow proves this math against live before any of that.
"""

BANK_CAP_MIN = 14 * 60   # 14h OT-bank cap (per-tenant config; TWB = 14h)


def worked_minutes(check_in_dt, check_out_dt, start_dt, end_dt) -> int:
    """Minutes actually worked: from the later of (arrival, start) to the earlier of (checkout, end) —
    so arriving early or leaving past end never inflates worked. tz-aware datetimes; never negative."""
    begin = max(check_in_dt, start_dt)
    finish = min(check_out_dt, end_dt)
    return max(0, int((finish - begin).total_seconds() // 60))


def ot_earned(worked_min: int, normal_len_min: int) -> int:
    """OT = minutes worked BEYOND the normal shift length (late/short already reduce worked, so a
    normal-length day — however the shift was moved — earns 0). Parity: gm_bot.ot.ot_earned."""
    return max(0, int(worked_min) - int(normal_len_min))


def split_ot_pb(minutes: int, pb_balance_min: int) -> tuple:
    """Split `minutes` against an outstanding PAYBACK balance: clears the debt FIRST, the remainder is
    OT. Returns (pb_cleared, ot). Parity: gm_bot.ot.split_ot_pb."""
    pb = max(0, int(pb_balance_min))
    pb_cleared = min(max(0, int(minutes)), pb)
    return pb_cleared, max(0, int(minutes)) - pb_cleared


def settle_shift(worked_min: int, normal_len_min: int, pb_balance_min: int, bank_min: int = 0,
                 bank_cap_min: int = BANK_CAP_MIN) -> dict:
    """At checkout: OT = worked beyond normal; it clears payback FIRST, the rest banks (up to the cap).
    Returns {ot_earned, pb_cleared, ot_banked, ot_dropped, new_pb, new_bank}. Parity with
    gm_bot.ot.settle_shift on (ot_banked, pb_cleared, new_pb); adds the cap honestly (overflow dropped)."""
    earned = ot_earned(worked_min, normal_len_min)
    pb_cleared, ot = split_ot_pb(earned, pb_balance_min)
    room = max(0, int(bank_cap_min) - int(bank_min))
    ot_banked = min(ot, room)
    return {"ot_earned": earned, "pb_cleared": pb_cleared, "ot_banked": ot_banked,
            "ot_dropped": ot - ot_banked, "new_pb": max(0, int(pb_balance_min)) - pb_cleared,
            "new_bank": int(bank_min) + ot_banked}
