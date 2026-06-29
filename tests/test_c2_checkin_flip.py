"""C2 — the check-in verdict cut-over net (gm_bot.checkin_net.verdict_via_net routing through core.flip).

The guarantees this locks (HIGH-RISK: live attendance/payroll path):
  • FLAG OFF (default) → byte-identical to today, core never consulted for the result (the safe deploy).
  • FLAG ON + agreeing → core's parity verdict is returned (the flip actually routes to core).
  • FLAG ON + core differs → core wins until divergence trips the auto-revert, which lands back on live.
  • core's 'on_time' vocab maps to live's 'ontime'.

All tests use throwaway org ids (never the live 'twb' flip row). conftest forces the staging DB.
"""
import pytest

from datetime import datetime
from zoneinfo import ZoneInfo

from core import flip
from gm_bot import checkin as ci
from gm_bot.checkin_net import verdict_via_net


@pytest.fixture(autouse=True)
def _isolate_flip():
    """Clear the c2t_* flip authority + divergence log before each test, so divergence rows accumulating
    across suite re-runs can't trip the auto-revert threshold (the override test logs 1 divergence/run →
    ~10 runs would otherwise auto-revert it, flipping its result). Test-isolation only."""
    flip.init_flip_db()
    from shared.database import _db
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_flip_log WHERE org_id LIKE %s", ("c2t_%",))
            cur.execute("DELETE FROM core_flip WHERE org_id LIKE %s", ("c2t_%",))
    yield

TZ = ZoneInfo("Asia/Phnom_Penh")
SD = "2026-06-29"
WS = 9 * 60          # 09:00 shift start, minute-of-day


def _dt(h, m):
    return datetime(2026, 6, 29, h, m, tzinfo=TZ)


def _live(now, grace=5, early=5):
    """What live's gm_bot.checkin.verdict returns for this instant (in_zone always True at the call site)."""
    return ci.verdict(now.hour * 60 + now.minute, WS, True, grace_min=grace, early_bonus_min=early)


def test_flag_off_is_byte_identical_to_live():
    """The safe-deploy guarantee: with the flag OFF, the net echoes live's verdict exactly."""
    flip.init_flip_db()
    org = "c2t_off_identical"
    flip.set_authoritative(org, "checkin", False)
    for now in (_dt(9, 0), _dt(9, 2), _dt(8, 50), _dt(10, 0), _dt(9, 6)):   # ontime / grace / early / late / late
        ls, lm = _live(now)
        assert verdict_via_net(now, SD, WS, 5, 5, ls, lm, org_id=org) == (ls, lm, False)


def test_flag_off_ignores_core_entirely():
    """Even a deliberately WRONG live verdict is returned untouched while OFF — core is never consulted."""
    flip.init_flip_db()
    org = "c2t_off_ignores_core"
    flip.set_authoritative(org, "checkin", False)
    now = _dt(10, 0)                                   # truly 60 min late
    assert verdict_via_net(now, SD, WS, 5, 5, "ontime", 0, org_id=org) == ("ontime", 0, False)


def test_flag_on_agreeing_returns_core_value():
    """Flipped + parity (the expected TWB case): returns core's verdict, which equals live's."""
    flip.init_flip_db()
    org = "c2t_on_agree"
    flip.set_authoritative(org, "checkin", True)
    now = _dt(10, 0)
    ls, lm = _live(now)
    state, mins, rev = verdict_via_net(now, SD, WS, 5, 5, ls, lm, org_id=org)
    assert (state, mins) == (ls, lm) == ("late", 60)
    assert rev is False


def test_flag_on_core_overrides_a_wrong_live():
    """Proves the flip really routes to core: with the flag ON, core's correct verdict wins over a wrong live."""
    flip.init_flip_db()
    org = "c2t_on_override"
    flip.set_authoritative(org, "checkin", True)
    now = _dt(10, 0)                                   # truly 60 late
    state, mins, rev = verdict_via_net(now, SD, WS, 5, 5, "ontime", 0, org_id=org)
    assert (state, mins) == ("late", 60)              # core's correct verdict, not the bogus live one
    assert rev is False                               # a single divergence is below the auto-revert threshold


def test_flag_on_persistent_divergence_auto_reverts_to_live():
    """A misbehaving flip un-flips itself and lands on the (known-good) live result."""
    flip.init_flip_db()
    org = "c2t_on_revert"
    flip.set_authoritative(org, "checkin", True)
    now = _dt(10, 0)                                   # core says late 60; we feed a wrong 'ontime' live
    reverted_seen = False
    for _ in range(15):
        _s, _m, rev = verdict_via_net(now, SD, WS, 5, 5, "ontime", 0, org_id=org)
        reverted_seen = reverted_seen or rev
    assert reverted_seen is True
    assert flip.is_authoritative(org, "checkin") is False
    # now OFF again → lands on the live result it was handed
    assert verdict_via_net(now, SD, WS, 5, 5, "ontime", 0, org_id=org) == ("ontime", 0, False)


def test_vocab_on_time_maps_to_ontime():
    """core's 'on_time' must surface as live's 'ontime' through the bridge."""
    flip.init_flip_db()
    org = "c2t_vocab"
    flip.set_authoritative(org, "checkin", True)
    now = _dt(9, 0)                                    # exactly on time
    state, mins, _rev = verdict_via_net(now, SD, WS, 5, 5, "ontime", 0, org_id=org)
    assert state == "ontime" and mins == 0


def test_failsafe_on_bad_inputs_returns_live():
    """Any error computing core's verdict → return live unchanged (never raise into the live flow)."""
    flip.init_flip_db()
    org = "c2t_failsafe"
    flip.set_authoritative(org, "checkin", True)
    # a non-date shift_date makes core's start reconstruction raise → fail-safe to live
    assert verdict_via_net(_dt(10, 0), "not-a-date", WS, 5, 5, "late", 60, org_id=org) == ("late", 60, False)
