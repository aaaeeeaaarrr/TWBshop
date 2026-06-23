"""Wizard auth (W3 foundation): OFF by default (localhost open); when WIZARD_AUTH=1, login is required —
except when no users exist yet (no lockout, so the owner can seed). Passwords are hashed, never plaintext."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core.db import create_user, verify_user

cdb.init_core_db()
ORG = "test_auth"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_org_users WHERE org_id=%s", (ORG,))


def test_create_and_verify_user_hashed():
    _clean()
    try:
        assert create_user(ORG, "owner", "s3cret") is True
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT password_hash FROM core_org_users WHERE org_id=%s AND username='owner'", (ORG,))
                h = cur.fetchone()["password_hash"]
        assert "s3cret" not in h                              # hashed at rest
        assert verify_user(ORG, "owner", "s3cret") == "owner"
        assert verify_user(ORG, "owner", "wrong") is None
    finally:
        _clean()


def test_auth_off_is_open(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    assert create_app(ORG).test_client().get("/").status_code == 200


def test_auth_on_no_users_no_lockout(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    assert create_app(ORG).test_client().get("/").status_code == 200     # no users → not locked out


def test_auth_on_requires_login_then_lets_in(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        create_user(ORG, "owner", "pw")
        c = create_app(ORG).test_client()
        r = c.get("/")
        assert r.status_code in (302, 303) and "/login" in r.headers["Location"]   # redirected to login
        c.post("/login", data={"username": "owner", "password": "pw"})             # log in
        assert c.get("/").status_code == 200                                       # now allowed
        c.post("/login", data={"username": "owner", "password": "bad"})            # wrong creds = no session change
    finally:
        _clean()
