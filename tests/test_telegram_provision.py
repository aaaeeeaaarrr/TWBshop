"""adapters.telegram_provision + the wizard's guided bot-setup screen. The Bot API is mocked (no real bot):
provision verifies + configures; the /bot screen shows the guided steps; a successful provision stores the
verified token (encrypted store) + the bot username (config)."""
from unittest.mock import MagicMock

import core.db as cdb
from shared.database import _db
import adapters.telegram_provision as tp
from wizard.app import create_app
from core.db import has_org_secret
from core.tenant_config import get_config

cdb.init_core_db()


class _FakeBot:
    def __init__(self, token):
        self.token = token
        self.cmds = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get_me(self):
        m = MagicMock()
        m.username, m.id, m.first_name = "testbot", 42, "Test"
        return m

    async def set_my_commands(self, cmds):
        self.cmds = cmds

    async def set_my_name(self, n):
        pass

    async def set_my_description(self, d):
        pass


def test_provision_no_token():
    assert tp.provision("")["ok"] is False


def test_provision_verifies_and_configures(monkeypatch):
    monkeypatch.setattr(tp, "Bot", _FakeBot)
    res = tp.provision("123:abc")
    assert res["ok"] is True and res["username"] == "testbot" and res["id"] == 42


def test_provision_handles_bad_token(monkeypatch):
    def _boom(token):
        raise RuntimeError("Unauthorized")
    monkeypatch.setattr(tp, "Bot", _boom)
    res = tp.provision("bad")
    assert res["ok"] is False and "Unauthorized" in res["error"]


def test_bot_setup_screen_renders():
    body = create_app("test_botx").test_client().get("/bot").get_data(as_text=True)
    assert "BotFather" in body and "/newbot" in body and "Verify" in body and "setprivacy" in body


def test_provision_route_stores_on_success(monkeypatch):
    monkeypatch.setattr("adapters.telegram_provision.provision",
                        lambda token, **k: {"ok": True, "username": "tbot", "id": 1, "name": "T"})
    org = "test_bot2"
    cdb.ensure_org(org, "T")
    try:
        r = create_app(org).test_client().post("/bot/provision", data={"token": "123:abc"})
        assert r.status_code in (302, 303)
        assert has_org_secret(org, "telegram_bot_token") is True
        assert get_config(org)["connections"]["telegram"]["bot_username"] == "tbot"
    finally:
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM core_org_secrets WHERE org_id=%s", (org,))
                cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
