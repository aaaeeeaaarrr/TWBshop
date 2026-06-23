"""core.onboarding — the wizard engine. Validates answers (required/type/choice + skip→default) and
applies them into a real tenant config (org created, knobs set). Real staging DB; isolated test org."""
import core.db as cdb
from core import onboarding as ob
from core.tenant_config import get_config
from shared.database import _db

ORG = "test_onboard"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_validate_required_type_and_choice():
    assert ob.validate({})["errors"].get("name") == "required"          # name required
    assert "grace_min" in ob.validate({"name": "X", "grace_min": "abc"})["errors"]   # bad int
    assert "channels" in ob.validate({"name": "X", "channels": "carrier-pigeon"})["errors"]  # bad choice
    ok = ob.validate({"name": "X"})                                     # rest fall back to defaults (skip)
    assert ok["ok"] and ok["cleaned"]["grace_min"] == 5 and ok["cleaned"]["channels"] == "telegram"


def test_apply_writes_tenant_config():
    cdb.init_core_db()
    cdb.ensure_org(ORG, "old")
    _clean()
    try:
        r = ob.apply(ORG, {"name": "TWB Two", "channels": "both", "package": "total", "grace_min": 0})
        assert r["ok"]
        cfg = get_config(ORG)
        assert cfg["channels"] == ["telegram", "web"]     # 'both' → both adapters
        assert cfg["package"] == "total"
        assert cfg["categories"]["attendance"]["verdict"]["grace_min"] == 0   # nested, config-driven
        # a bad apply changes nothing + reports errors
        bad = ob.apply(ORG, {"name": "", "grace_min": "x"})
        assert bad["ok"] is False and "name" in bad["errors"]
    finally:
        _clean()
