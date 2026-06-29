"""core.settle PAYBACK-SLOT model (roadmap #5): the EXTENSION-worked window (whole / stay-late tail /
come-early head) + the slot settle (clears the debt first, NEVER banks OT). Parity with
gm_bot/bot.py::_settle_redefined_shift's payback-slot branch + gm_bot.ot.split_ot_pb. Pure (no DB)."""
from core import settle as cs
from gm_bot import ot as live_ot


def test_extension_window_day_off_is_the_whole_window():
    assert cs.payback_extension_window(360, 720, 0, True) == (360, 720)
    assert cs.payback_extension_window(360, 720, 0, False) == (360, 720)


def test_extension_window_stay_late_is_the_tail():
    # start unchanged + normal_len 540 → extension = the TAIL [start+540, end]
    assert cs.payback_extension_window(540, 1620, 540, True) == (1080, 1620)


def test_extension_window_come_early_is_the_head():
    # start moved earlier + normal_len 540 → extension = the HEAD [start, end-540]
    assert cs.payback_extension_window(540, 1620, 540, False) == (540, 1080)


def test_slot_clears_debt_first_and_never_banks_ot():
    assert cs.settle_payback_slot(60, 89) == {"pb_cleared": 60, "ot_banked": 0, "new_pb": 29}
    # worked MORE than owed → clears the debt; the surplus is NOT banked (a slot repays only, never OT)
    assert cs.settle_payback_slot(120, 89) == {"pb_cleared": 89, "ot_banked": 0, "new_pb": 0}
    assert cs.settle_payback_slot(0, 89) == {"pb_cleared": 0, "ot_banked": 0, "new_pb": 89}


def test_slot_pb_cleared_parity_with_live_split_ot_pb():
    """pb_cleared must equal live's split_ot_pb(ext_worked, pb)[0]; ot_banked is forced 0 for a slot."""
    for ext, pb in [(30, 89), (89, 89), (200, 89), (0, 50), (45, 0), (7, 7)]:
        live_pb_cleared, _live_ot = live_ot.split_ot_pb(ext, pb)
        out = cs.settle_payback_slot(ext, pb)
        assert out["pb_cleared"] == live_pb_cleared and out["ot_banked"] == 0


def test_end_to_end_extension_worked_then_settle():
    """The intended pairing: window → ext_worked via worked_minutes → slot settle. A stay-late slot
    09:00–23:00 (normal_len 540) with check-in 09:06 (6m late) and checkout 23:10: the extension is the
    18:00–23:00 tail; worked-in-window = 18:00→23:00 = 300, clears a 120 debt fully, banks 0."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Phnom_Penh")

    def dt(h, m):
        return datetime(2026, 6, 29, h, m, tzinfo=tz)

    base = dt(0, 0)
    appr_start, appr_end = 540, 1380                         # 09:00–23:00 (minutes from base)
    ext_s, ext_e = cs.payback_extension_window(appr_start, appr_end, 540, True)
    assert (ext_s, ext_e) == (1080, 1380)                    # 18:00–23:00 tail
    from datetime import timedelta
    ext_worked = cs.worked_minutes(dt(9, 6), dt(23, 10), base + timedelta(minutes=ext_s),
                                   base + timedelta(minutes=ext_e))
    assert ext_worked == 300                                 # full 18:00→23:00 (late-on-the-normal-portion doesn't cut it)
    assert cs.settle_payback_slot(ext_worked, 120) == {"pb_cleared": 120, "ot_banked": 0, "new_pb": 0}
