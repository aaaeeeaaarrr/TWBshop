"""grace_min / early_bonus_min migration → config-driven (instant-live), BEHAVIOR-PRESERVING.

checkin.verdict is now parameterized (defaults = the locked spec 5/5), and the tenant-config DEFAULT a fresh
tenant gets EQUALS the live constant — so wiring the live caller to read config changes nothing until an owner
overrides it (proven on PROD: TWB has no verdict override → effective grace_min = 5). An override drives it live.
"""
import core.db as cdb
from shared.database import _db
from gm_bot.checkin import verdict, GRACE_MIN, EARLY_BONUS_MIN
from core.tenant_config import verdict_cfg, set_config

ORG = "test_verdict_cfg"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_verdict_default_param_equals_hardcoded():
    # 6 min late: default grace 5 → late; passing the constants explicitly is identical (backward-compatible)
    assert verdict(366, 360, True) == ("late", 6)
    assert verdict(366, 360, True, grace_min=GRACE_MIN, early_bonus_min=EARLY_BONUS_MIN) == ("late", 6)


def test_verdict_override_changes_behavior():
    assert verdict(366, 360, True, grace_min=9) == ("ontime", 0)          # 6 ≤ 9 grace → on time
    assert verdict(348, 360, True, early_bonus_min=15) == ("ontime", 0)   # 12 early < 15 bonus → on time, not 'early'


def test_config_default_equals_live_constant_then_override_is_live():
    _reset()
    try:
        # the config DEFAULT a fresh tenant gets == the live hardcoded constant → migrating is behavior-preserving
        assert verdict_cfg(ORG)["grace_min"] == GRACE_MIN == 5
        assert verdict_cfg(ORG)["early_bonus_min"] == EARLY_BONUS_MIN == 5
        # an override is read fresh (instant-live) — what the wired live caller would now pass to verdict()
        set_config(ORG, {"categories": {"attendance": {"verdict": {"grace_min": 9}}}})
        assert verdict_cfg(ORG)["grace_min"] == 9
        g = verdict_cfg(ORG)["grace_min"]
        assert verdict(366, 360, True, grace_min=g) == ("ontime", 0)      # config flows through → behavior changes
    finally:
        _reset()
