"""Config-change audit (PRODUCT SECURITY law #5) — apply_changes logs who/what/when; secrets log the ACT,
never the value; the /audit page renders."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app, apply_changes
from core.db import recent_config_audit

cdb.init_core_db()
ORG = "test_audit"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_config_audit WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_org_secrets WHERE org_id=%s", (ORG,))


def test_config_change_is_logged():
    _reset()
    try:
        apply_changes(ORG, {"categories.attendance.verdict.grace_min": "9"})
        rows = recent_config_audit(ORG, 10)
        hit = [r for r in rows if r["path"] == "categories.attendance.verdict.grace_min"]
        assert hit and hit[0]["new_val"] == "9" and hit[0]["old_val"] == "5"   # before/after captured
    finally:
        _reset()


def test_secret_logged_without_value():
    _reset()
    try:
        apply_changes(ORG, {"connections.telegram.bot_token": "123456:SECRETTOKEN"})
        sec = [r for r in recent_config_audit(ORG, 10) if "bot_token" in r["path"]]
        assert sec and "SECRETTOKEN" not in (sec[0]["new_val"] or "")          # value never in the log
        assert sec[0]["new_val"] == "(secret set)"
    finally:
        _reset()


def test_audit_page_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        apply_changes(ORG, {"categories.attendance.verdict.grace_min": "8"})
        body = create_app(ORG).test_client().get("/audit").get_data(as_text=True)
        assert "Config change log" in body and "grace_min" in body
    finally:
        _reset()
