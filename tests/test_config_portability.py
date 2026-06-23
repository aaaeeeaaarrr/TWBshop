"""Config export / import — a tenant's setup is portable (back up / clone). Import goes through the SAME
whitelist as the editor: only safe (non-live) knobs apply, live ones are ignored, bad JSON is rejected."""
import json
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app, apply_changes
from core.tenant_config import get_config

cdb.init_core_db()
ORG = "test_port"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_config_audit WHERE org_id=%s", (ORG,))


def test_export_shows_overrides(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        apply_changes(ORG, {"categories.attendance.verdict.grace_min": "9"})
        body = create_app(ORG).test_client().get("/export").get_data(as_text=True)
        assert "grace_min" in body and "Export config" in body
        assert "Your customizations" in body and "5 → <b>9</b>" in body   # readable default→value diff
    finally:
        _reset()


def test_import_applies_safe_only(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        blob = json.dumps({"categories": {"attendance": {
            "verdict": {"grace_min": 11},                      # SHADOW → applied
            "approvals": {"al": {"reping_hours": 99}},         # LIVE → ignored
        }}})
        r = create_app(ORG).test_client().post("/import", data={"blob": blob})
        assert "Imported" in r.get_data(as_text=True)
        cfg = get_config(ORG)
        assert cfg["categories"]["attendance"]["verdict"]["grace_min"] == 11           # safe applied
        assert cfg["categories"]["attendance"]["approvals"]["al"]["reping_hours"] == 6  # live untouched
    finally:
        _reset()


def test_oversized_post_rejected(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    big = "x" * (3 * 1024 * 1024)                                   # 3MB > the 2MB cap
    r = create_app(ORG).test_client().post("/import", data={"blob": big})
    assert r.status_code == 413                                     # Request Entity Too Large (memory-DoS guard)


def test_import_bad_json(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        r = create_app(ORG).test_client().post("/import", data={"blob": "not json"})
        assert "Invalid JSON" in r.get_data(as_text=True)
    finally:
        _reset()
