"""core.approvals.reping_decision — the approval-ladder rule (6h × 4 → escalate; expire when window passes)."""
from datetime import datetime, timezone, timedelta

from core.approvals import reping_decision
from core.tenant_config import _APPROVAL_DEFAULT   # the TWB default rule (reping 6h × 4, escalate, expire)

CFG = dict(_APPROVAL_DEFAULT)   # reping_hours=6, reping_max=4, escalate_after_max=True, expire_on_window=True
T0 = datetime(2026, 6, 23, 0, 0, tzinfo=timezone.utc)


def _now(hours):
    return T0 + timedelta(hours=hours)


def test_waits_then_repings_on_each_6h_mark():
    assert reping_decision(T0, _now(0), 0, False, CFG, False) == "wait"     # fresh
    assert reping_decision(T0, _now(5.9), 0, False, CFG, False) == "wait"   # not yet 6h
    assert reping_decision(T0, _now(6), 0, False, CFG, False) == "reping"   # 1st re-ping due
    assert reping_decision(T0, _now(6), 1, False, CFG, False) == "wait"     # already sent #1
    assert reping_decision(T0, _now(12), 1, False, CFG, False) == "reping"  # #2 due
    assert reping_decision(T0, _now(25), 3, False, CFG, False) == "reping"  # catch up to #4


def test_caps_at_4_then_escalates_once():
    assert reping_decision(T0, _now(30), 4, False, CFG, False) == "escalate"  # max done → escalate
    assert reping_decision(T0, _now(30), 4, True, CFG, False) == "wait"       # already escalated
    assert reping_decision(T0, _now(100), 4, False, CFG, False) == "escalate" # never re-pings past max


def test_expire_when_window_passed_beats_everything():
    assert reping_decision(T0, _now(2), 0, False, CFG, True) == "expire"      # AL date gone → expire
    assert reping_decision(T0, _now(30), 4, False, CFG, True) == "expire"
    # but not if the tenant disabled expiry
    no_exp = dict(CFG, expire_when_window_passes=False)
    assert reping_decision(T0, _now(2), 0, False, no_exp, True) == "wait"
