"""Session 31 UNIFIED OT model — length-based OT, PB↔OT netting, the +PB/+OT end-ladder.
Pure logic, no DB. Times are minutes-of-day (1pm=780, 9h shift = 540 min)."""
from gm_bot import ot

NORMAL = 540   # a 9-hour shift


# ---- OT = worked length beyond normal (the whole model) ----
def test_ot_earned_full_extension():
    assert ot.ot_earned(11 * 60, NORMAL) == 120          # worked 11h vs 9h normal -> 2h OT

def test_ot_earned_normal_day_however_shifted():
    assert ot.ot_earned(NORMAL, NORMAL) == 0             # 9h worked = 0 OT (late/moved doesn't matter)

def test_ot_earned_short_day():
    assert ot.ot_earned(8 * 60, NORMAL) == 0             # left early / came late -> under normal -> 0


# ---- PB <-> OT one currency ----
def test_split_clears_pb_first():
    assert ot.split_ot_pb(60, 120) == (60, 0)            # 1h extension, 2h debt -> all PB
    assert ot.split_ot_pb(120, 120) == (120, 0)          # exactly clears
    assert ot.split_ot_pb(180, 120) == (120, 60)         # clears 2h debt, 1h OT
    assert ot.split_ot_pb(120, 0) == (0, 120)            # no debt -> all OT

def test_apply_ot_to_pb_nets():
    # 3h OT earned + 2h PB owed -> clears 2h, banks 1h, debt now 0  (your "shows as 1 OT")
    assert ot.apply_ot_to_pb(180, 120) == (120, 60, 0)
    # 2h OT + 5h PB -> clears 2h, banks 0, 3h debt remains
    assert ot.apply_ot_to_pb(120, 300) == (120, 0, 180)
    # no debt -> all banks
    assert ot.apply_ot_to_pb(90, 0) == (0, 90, 0)


# ---- the end-ladder tags (matches the owner's example) ----
def test_end_ladder_with_2h_pb():
    # start 1pm (780), 9h normal -> normal end 10pm (1320); 2h PB owed; hourly
    got = ot.end_option_tags(780, NORMAL, pb_balance_min=120, step_min=60)
    assert got == [
        (1320, ""),          # 10pm  (normal end)
        (1380, "+1PB"),      # 11pm  clears 1h debt
        (1440 % 1440, "+2PB"),  # 12am clears 2h debt  -> minute 0
        (60, "+1OT"),        # 1am   debt cleared, 1h OT
        (120, "+2OT"),       # 2am   2h OT
    ]

def test_end_ladder_no_pb_is_all_ot():
    got = ot.end_option_tags(780, NORMAL, pb_balance_min=0, step_min=60)
    assert [t for _e, t in got] == ["", "+1OT", "+2OT", "+3OT", "+4OT"]


# ---- start options (today clipping) ----
def test_start_options_future_day_full():
    opts = ot.start_options()            # 30-min steps, whole day
    assert opts[0] == 0 and opts[-1] == 1410 and len(opts) == 48

def test_start_options_today_drops_past():
    opts = ot.start_options(earliest_min=720)   # noon now -> only afternoon/evening
    assert opts[0] == 720 and all(m >= 720 for m in opts)
