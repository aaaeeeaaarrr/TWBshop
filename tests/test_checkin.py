"""Check-in verdict + scheduling — pure logic."""
from gm_bot import checkin as ci


def test_in_zone_exactly_on_time():
    assert ci.verdict(540, 540, True) == ("ontime", 0)


def test_early_beyond_grace():
    # 9:00 shift, arrive 8:48 (12 min early) -> early +bonus
    assert ci.verdict(528, 540, True) == ("early", 12)


def test_early_within_grace_is_ontime():
    # 3 min early -> no bonus, no penalty
    assert ci.verdict(537, 540, True) == ("ontime", 0)


def test_late_within_grace_free():
    # 5 min late exactly -> free (ontime)
    assert ci.verdict(545, 540, True) == ("ontime", 0)


def test_late_beyond_grace_counts_all():
    # 25 min late -> all 25 count
    assert ci.verdict(565, 540, True) == ("late", 25)


def test_outside_zone_never_checks_in():
    assert ci.verdict(540, 540, False) == ("not_here", 0)


def test_overnight_early():
    # 9pm shift (1260), arrive 8:50pm (1250) = 10 min early
    assert ci.verdict(1250, 1260, True) == ("early", 10)


def test_overnight_after_midnight_late():
    # 9pm shift (1260), arrive 12:30am (30) -> 210 min late
    assert ci.verdict(30, 1260, True) == ("late", 210)


def test_is_due():
    assert ci.is_due(350, 350) is True
    assert ci.is_due(350, 351) is False


# ── shift_for_now: overnight-aware check-in binding (the Jun-16 false-no-show / phantom-session fix) ──
# candidates are (day_offset, working, ws, we), TODAY-FIRST. A night shift is 21:00-06:00 → ws=1260, we=360.

def test_binding_normal_day_checkin_binds_today():
    # 06:00-18:00 day shift, ping 05:53 → today, on the shift start
    cands = [(0, True, 360, 1080), (-1, True, 360, 1080)]
    assert ci.shift_for_now(353, cands) == (0, 360)


def test_binding_night_shift_start_binds_today():
    # 21:00-06:00, ping 20:53 (start) → today's shift
    cands = [(0, True, 1260, 360), (-1, True, 1260, 360)]
    assert ci.shift_for_now(1253, cands) == (0, 1260)


def test_binding_overnight_end_ping_binds_YESTERDAY():
    # THE BUG: 21:00-06:00, ping 06:00 → must bind to YESTERDAY's shift (off=-1), not spawn a today session
    cands = [(0, True, 1260, 360), (-1, True, 1260, 360)]
    assert ci.shift_for_now(360, cands) == (-1, 1260)


def test_binding_overnight_end_ping_slightly_late_still_yesterday():
    # ping 06:20 (20 min past the 06:00 end) → still yesterday (within the 120-min post window)
    cands = [(0, True, 1260, 360), (-1, True, 1260, 360)]
    assert ci.shift_for_now(380, cands) == (-1, 1260)


def test_binding_dayoff_trio_overnight_morning_not_their_shift():
    # off=Tue night staffer: Tue (today) is day-off (not working), Mon (yesterday) WAS worked but its
    # shift ended 06:00 Tue. A ping at 06:00 Tue binds to Mon (the overnight tail it belongs to), never today.
    cands = [(0, False, None, None), (-1, True, 1260, 360)]
    assert ci.shift_for_now(360, cands) == (-1, 1260)


def test_binding_way_early_for_tonight_does_not_bind():
    # 21:00-06:00 worker, ping 06:00 but YESTERDAY was a day off (no overnight tail) → no shift near now.
    # Must NOT bind today's 21:00 shift (15h early) → (None, None). This is what killed the phantom session.
    cands = [(0, True, 1260, 360), (-1, False, None, None)]
    assert ci.shift_for_now(360, cands) == (None, None)


def test_binding_midnight_end_shift_next_morning_does_not_bind():
    # 12:00-00:00 (ends exactly at midnight, we=0 → we2=1440, NOT > 1440) → a 00:30 ping next day does
    # not bind yesterday (it ended at its own midnight); checkout is handled by the armed flow instead.
    cands = [(0, False, None, None), (-1, True, 720, 0)]
    assert ci.shift_for_now(30, cands) == (None, None)


def test_binding_prefers_today_over_yesterday():
    # both days working day-shifts; a midday ping belongs to today
    cands = [(0, True, 360, 1080), (-1, True, 360, 1080)]
    assert ci.shift_for_now(700, cands) == (0, 360)


def test_binding_post_window_excludes_far_after_end():
    # ping 3h after a 06:00 end (09:00) → outside the 120-min post window → no bind
    cands = [(0, True, 1260, 360), (-1, True, 1260, 360)]
    assert ci.shift_for_now(540, cands) == (None, None)


def test_binding_early_bird_within_pre_window():
    # 06:00 shift, ping 05:05 (55 min early, within the 60-min pre window) → today
    cands = [(0, True, 360, 1080), (-1, False, None, None)]
    assert ci.shift_for_now(305, cands) == (0, 360)
