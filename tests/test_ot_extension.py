"""Session 31: shift-extension OT credit/points math — the money-critical exploit guards.
Pure logic, no DB. Times are minutes-of-day (7am=420, 4pm=960)."""
from gm_bot import ot

S0, S1 = 420, 960          # shift 7:00 -> 16:00
PRE = (360, 420)           # before-shift OT 6:00 -> 7:00 (60 min)
POST = (960, 1080)         # after-shift OT 16:00 -> 18:00 (120 min)


def out(grants, ci, co):
    return ot.ot_outcome(S0, S1, grants, ci, co)


# ---- committed / union ----
def test_committed_pre_post_union():
    assert ot.committed_ot(S0, S1, [PRE]) == 60
    assert ot.committed_ot(S0, S1, [POST]) == 120
    assert ot.committed_ot(S0, S1, [PRE, POST]) == 180
    # overlapping after-shift grants collapse to ONE window (no double count)
    assert ot.committed_ot(S0, S1, [(960, 1080), (960, 1020)]) == 120


# ---- before-shift ----
def test_before_full_ontime():
    w, lbl, pts = out([PRE], 360, 960)          # arrive 6:00 exactly, work all day
    assert (w, lbl, pts) == (60, "ok", 0)

def test_before_early_bonus():
    w, lbl, pts = out([PRE], 350, 960)          # arrive 5:50 (10m early), full
    assert (w, lbl, pts) == (60, "early", 10)

def test_before_cameo_last_5min_is_no_show():
    w, lbl, pts = out([PRE], 415, 960)          # show only 6:55 -> shift; 5 min of OT
    assert w == 5 and lbl == "no_show" and pts == -10   # paid 5, still -10

def test_before_early_then_leave_loophole_killed():
    # arrive "early" 5:50 but leave 6:05 -> only 5 min OT -> no_show, NO +10
    w, lbl, pts = out([PRE], 350, 365)
    assert lbl == "no_show" and pts == -10

def test_before_no_show_but_on_time_for_shift():
    # skip the 6am OT, arrive 7:00 for the shift: 0 OT, no_show penalty, shift itself on-time
    w, lbl, pts = out([PRE], 420, 960)
    assert w == 0 and lbl == "no_show" and pts == -10


# ---- after-shift ----
def test_after_full():
    w, lbl, pts = out([POST], 420, 1080)        # work shift + full OT
    assert (w, lbl, pts) == (120, "ok", 0)

def test_after_exactly_half_is_ok():
    w, lbl, pts = out([POST], 420, 1020)        # leave 17:00 -> 60 of 120 = half
    assert w == 60 and lbl == "ok" and pts == 0

def test_after_under_half_is_no_show():
    w, lbl, pts = out([POST], 420, 1000)        # leave 16:40 -> 40 of 120
    assert w == 40 and lbl == "no_show" and pts == -10

def test_after_never_early():
    # arriving early for the shift gives no OT-early bonus (after-shift OT only)
    w, lbl, pts = out([POST], 400, 1080)
    assert lbl == "ok" and pts == 0


# ---- overlap / both edges / overnight ----
def test_overlap_no_double_bank():
    w, lbl, pts = out([(960, 1080), (960, 1020)], 420, 1080)
    assert w == 120                              # union 16:00-18:00, not 120+60

def test_both_edges_same_day():
    w, lbl, pts = out([PRE, POST], 350, 1080)    # arrive 5:50 (early), work both edges
    assert w == 180 and lbl == "early"           # 60 pre + 120 post

def test_both_edges_ontime_is_ok():
    w, lbl, pts = out([PRE, POST], 360, 1080)    # arrive 6:00 exactly = on-time, not early
    assert w == 180 and lbl == "ok"

def test_overnight_after_shift_monotonic():
    # OT 16:00 -> 01:00 next day == minute 1500; presence to 1500
    w, lbl, pts = out([(960, 1500)], 420, 1500)
    assert w == 540 and lbl == "ok"


# ---- degenerate ----
def test_no_grant():
    assert out([], 420, 960) == (0, "none", 0)

def test_zero_presence():
    assert ot.worked_ot(S0, S1, [POST], 1080, 1080) == 0


# ---- picker options ----
def test_pre_shift_options():
    assert ot.pre_shift_start_options(420) == [180, 240, 300, 360]   # 3,4,5,6am
def test_post_shift_options():
    assert ot.post_shift_end_options(960) == [1020, 1080, 1140, 1200]  # 5,6,7,8pm
