"""F1 live bridge (gm_bot.exceptions_live): fail-safe reads of per-staff exceptions at the live gates.
Locks the two guarantees the live wiring depends on: DEFAULT {} = exempt from nothing (today's behaviour
everywhere, so deploying the wiring is a no-op until an exception is set), and FAIL-SAFE on any bad input."""
from core.db import init_core_db, ensure_org
from core.onboarding_flow import add_staff_manual
from core import exceptions as ex
from gm_bot import exceptions_live as el


def _setup(monkeypatch):
    init_core_db()
    org = "ellive58"
    ensure_org(org, "ExcLiveTest", "Asia/Phnom_Penh")
    monkeypatch.setattr(el, "ORG", org)        # point the live helper at the throwaway test tenant
    return org


def test_default_staffer_is_exempt_from_nothing(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Normal")
    assert el.exceptions_of(sid) == {}
    for k in ("no_attendance", "no_points", "no_lateness", "no_payback", "no_supervisor_posts",
              "no_nudges", "payback_to_al"):
        assert el.exempt(sid, k) is False           # default = today's behaviour everywhere
    assert el.approver(sid, "al") is None


def test_vip_staffer_is_exempt_across_the_bundle(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Tyty")
    ex.set_exceptions(org, sid, ex.apply_preset("vip_exempt"))
    for k in ("no_attendance", "no_al", "no_ot", "no_points", "no_nudges", "no_supervisor_posts", "quiet"):
        assert el.exempt(sid, k) is True
    assert el.exempt(sid, "payback_to_al") is False    # payback_to_al is NOT in the vip bundle


def test_thyda_supervisor_and_approver_override(monkeypatch):
    org = _setup(monkeypatch)
    tyty = add_staff_manual(org, name="Tyty")
    thyda = add_staff_manual(org, name="Thyda")
    ex.set_exceptions(org, thyda, {"no_supervisor_posts": True, "payback_to_al": True, "al_approver_id": tyty})
    assert el.exempt(thyda, "no_supervisor_posts") is True
    assert el.exempt(thyda, "payback_to_al") is True
    assert el.exempt(thyda, "no_points") is False         # still scored (keeps points)
    assert el.approver(thyda, "al") == tyty
    assert el.approver(thyda, "swap") is None             # only AL overridden


def test_fail_safe_on_bad_input(monkeypatch):
    _setup(monkeypatch)
    assert el.exceptions_of(99999999) == {}               # no core_staff row → {} (never raises)
    assert el.exempt(99999999, "no_points") is False
    assert el.exempt(None, "no_points") is False          # non-int → fail-safe
    assert el.approver("nope", "al") is None
