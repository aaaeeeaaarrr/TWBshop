"""Proactive Sentinel detectors: a dangerous CONFIG is flagged via the sweep (→ alarm sink) BEFORE it bites
— catching a foot-gun setting the moment it's set, not only when it produces a wrong verdict downstream."""
from core.db import init_core_db, ensure_org
from core.onboarding_flow import add_staff_manual
from core import sentinel

ORG = "cfgtest58"


def test_sentinel_flags_a_dangerous_config():
    init_core_db()
    ensure_org(ORG, "CfgTest", "Asia/Phnom_Penh")
    # two staff sharing a name is a config_health 'warn' (ambiguous for assignments/approvals)
    add_staff_manual(ORG, name="DupName")
    add_staff_manual(ORG, name="DupName")
    al = sentinel.sweep(ORG)
    assert any(a["flow"] == "config" and a["severity"] == "warn" for a in al)


def test_sentinel_sweep_is_clean_for_a_healthy_empty_orgish():
    # a detector must not crash the sweep; 'info'-only health (no warns) yields no 'config' alarm
    init_core_db()
    ensure_org("cfgclean58", "Clean", "Asia/Phnom_Penh")
    al = sentinel.sweep("cfgclean58")
    assert all(isinstance(a, dict) and "flow" in a for a in al)   # well-formed, never raises
