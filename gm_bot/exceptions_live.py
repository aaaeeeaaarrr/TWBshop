"""gm_bot.exceptions_live — F1: the LIVE bridge that reads per-staff EXCEPTIONS (core/exceptions.py) at
each gate in the live gm bot.

Design = SAFE BY CONSTRUCTION:
  • DEFAULT NO-CHANGE: a staffer with no exceptions ({} — the state of EVERY staffer until the owner sets
    one via the wizard) is exempt from nothing → every gate behaves exactly as today. So deploying the
    wiring while no exceptions are set is a true no-op; SETTING an exception is the behaviour change.
  • FAIL-SAFE: any error (DB hiccup, bad data, core_staff row missing) → NOT exempt / no override →
    today's normal behaviour. An exception lookup can never break a live attendance/payroll flow.

Each live gate calls `exempt(staff_id, key)` right before the thing the exception suppresses, e.g.
    if not exceptions_live.exempt(sid, "no_points"):
        points_record(...)
or, on a hot path that checks several keys, fetch once and test locally:
    exc = exceptions_live.exceptions_of(sid)
    if core_exceptions.is_exempt(exc, "no_attendance"): return
    ...
Approval routing uses `approver(staff_id, kind)` → a staff_id override, or None = the normal ladder.

TWBshop is org 'twb'. INERT until a gate calls these AND the staffer has an exception set.
"""
from core.exceptions import get_exceptions, is_exempt, approver_for, escalate_to as _escalate_to

ORG = "twb"


def exceptions_of(staff_id) -> dict:
    """A staffer's exceptions dict ({} = a normal staffer, and = fail-safe on any error). Fetch once per
    flow when several keys are checked, then use core.exceptions.is_exempt(exc, key) locally."""
    try:
        return get_exceptions(ORG, int(staff_id)) or {}
    except Exception:
        return {}


def exempt(staff_id, key: str) -> bool:
    """Is this staffer exempt from `key`? Fail-safe → False (normal behaviour). For one-off gates; on a
    hot path checking several keys prefer exceptions_of() + is_exempt() to avoid repeat queries."""
    try:
        return is_exempt(exceptions_of(staff_id), key)
    except Exception:
        return False


def approver(staff_id, kind: str):
    """The override approver staff_id for kind in {'al','leave','swap'}, or None = the normal ladder.
    Fail-safe → None."""
    try:
        return approver_for(exceptions_of(staff_id), kind)
    except Exception:
        return None


def escalate_to(staff_id):
    """The staff_id this staffer's Supervisors-group attendance posts REROUTE to (a private DM), or
    None = the normal Supervisors group. Fail-safe → None (normal behaviour). The gm bot resolves the
    returned staff_id to a telegram uid at the send site."""
    try:
        return _escalate_to(exceptions_of(staff_id))
    except Exception:
        return None
