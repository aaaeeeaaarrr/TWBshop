"""core.health — read-only config health-check. Flags likely misconfigurations; clean defaults raise no
WARNs; the /health page renders."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core.health import config_health
from core.tenant_config import set_config

cdb.init_core_db()
ORG = "test_health"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))


def test_health_flags_expertise_no_roles():
    _reset()
    try:
        set_config(ORG, {"categories": {"attendance": {"expertise": {"enabled": True, "roles": []}}}})
        assert any(lvl == "warn" and "Expertise" in m for lvl, m in config_health(ORG))
    finally:
        _reset()


def test_health_flags_ot_bank_zero_cap():
    _reset()
    try:
        set_config(ORG, {"categories": {"attendance": {"ot": {"disposition": "bank", "bank_cap_min": 0}}}})
        assert any(lvl == "warn" and "bank cap is 0" in m for lvl, m in config_health(ORG))
    finally:
        _reset()


def test_health_default_config_has_no_warns():
    _reset()
    try:
        assert [m for lvl, m in config_health(ORG) if lvl == "warn"] == []   # defaults are sane (infos ok)
    finally:
        _reset()


def test_health_page_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        assert "health-check" in create_app(ORG).test_client().get("/health").get_data(as_text=True).lower()
    finally:
        _reset()
