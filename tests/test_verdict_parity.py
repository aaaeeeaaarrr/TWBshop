"""PARITY LOCK (s55): the platform's check-in verdict (core.attendance.verdict) must agree with the LIVE
gm_bot.checkin.verdict across the FULL minute grid — that agreement is the whole premise of the shadow and
the eventual cut-over. The state NAMES differ (on_time↔ontime; live also has 'not_here' for off-zone, which
core handles at the location layer, not in verdict), but the classification + reported minutes must match, so
the platform verdict can never silently drift from live."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.attendance import verdict as core_verdict
from gm_bot.checkin import verdict as live_verdict, GRACE_MIN, EARLY_BONUS_MIN

_TZ = "Asia/Phnom_Penh"
_STATE = {"on_time": "ontime", "early": "early", "late": "late"}


def test_core_verdict_matches_live_across_the_minute_grid():
    z = ZoneInfo(_TZ)
    start = datetime(2026, 6, 20, 13, 0, tzinfo=z)        # arbitrary shift start
    start_min = 13 * 60
    for rel in range(-120, 121):                          # 2h early … 2h late, minute by minute
        when = start + timedelta(minutes=rel)
        now_min = (start_min + rel) % 1440
        cs, cl, ce = core_verdict(when, start, _TZ, GRACE_MIN, EARLY_BONUS_MIN)
        ls, lm = live_verdict(now_min, start_min, in_zone=True)
        assert _STATE[cs] == ls, "state drift at rel=%d: core %s vs live %s" % (rel, cs, ls)
        cmin = cl if cs == "late" else (ce if cs == "early" else 0)
        assert cmin == lm, "minutes drift at rel=%d: core %d vs live %d" % (rel, cmin, lm)


def test_core_verdict_respects_tweaked_thresholds():
    """The thresholds are per-tenant config — core honours them (a different grace/early still classifies
    consistently), so a customer can tune them without the verdict logic drifting."""
    z = ZoneInfo(_TZ)
    start = datetime(2026, 6, 20, 9, 0, tzinfo=z)
    assert core_verdict(start + timedelta(minutes=9), start, _TZ, 10, 5)[0] == "on_time"   # 9 ≤ grace 10
    assert core_verdict(start + timedelta(minutes=11), start, _TZ, 10, 5)[0] == "late"     # 11 > grace 10
    assert core_verdict(start - timedelta(minutes=20), start, _TZ, 5, 15)[0] == "early"    # 20 ≥ early 15
    assert core_verdict(start - timedelta(minutes=10), start, _TZ, 5, 15)[0] == "on_time"  # 10 < early 15
