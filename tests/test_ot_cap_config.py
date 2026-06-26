"""ot.bank_cap_min → config-driven (instant-live), BEHAVIOR-PRESERVING. The OT money path (over-bank class):
cap_room is now parameterized (default = the 14h spec), and the LIVE bank-write cap (bot.py:2542) reads the
tenant config fresh, fail-safe to 14h. Config DEFAULT == the live constant (PROD: TWB ot override=null → 840),
so the cap is unchanged until an owner overrides it — and an over-bank stays blocked either way."""
import core.db as cdb
from shared.database import _db
from gm_bot.ot import cap_room, BANK_CAP_MIN
from core.tenant_config import attendance, set_config

ORG = "test_ot_cap_cfg"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_cap_room_default_unchanged_overbank_blocked():
    assert cap_room(0) == BANK_CAP_MIN == 840           # default = 14h (backward-compatible)
    assert cap_room(13 * 60) == 60
    assert cap_room(14 * 60) == 0                        # full → no room → over-bank blocked


def test_cap_room_honors_override_cap():
    assert cap_room(0, 600) == 600                       # a 10h override cap
    assert cap_room(9 * 60, 600) == 60
    assert cap_room(10 * 60, 600) == 0                   # full at the override → no room


def test_bank_cap_config_default_then_override_still_caps():
    _reset()
    try:
        assert attendance(ORG)["ot"]["bank_cap_min"] == BANK_CAP_MIN == 840    # default == constant (preserving)
        set_config(ORG, {"categories": {"attendance": {"ot": {"bank_cap_min": 600}}}})
        cap = attendance(ORG)["ot"]["bank_cap_min"]
        assert cap == 600                                                      # instant-live
        # what the live banker would apply: min(ot_banked, cap_room(balance, cap)) — over-bank stays blocked
        assert min(120, cap_room(13 * 60, cap)) == 0     # 13h banked, 10h cap → 0 room → can't over-bank
    finally:
        _reset()
