"""W3 #4 — CSRF + login/check-in rate-limit (owner 2026-06-30; PRODUCT SECURITY & IP law).

All gated behind auth_enabled() → INERT for the owner's localhost/tunnel workflow (proven by
test_csrf_inert_when_auth_off). When auth is ON (public/multi-tenant):
  • TI-F4  a state-changing POST from a cross-origin site is rejected (SameSite=Strict cookie is the primary
           defense; the Origin check is the belt). Same-origin / Origin-less requests pass (don't break clients).
  • TI-F6  login is brute-force rate-limited; the public token check-in is abuse rate-limited (per-app, by IP).
Complements tests/test_wizard_auth_failclosed.py (auth fail-closed) + tests/test_wizard_roles.py (roles).
"""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app, _rate_ok
from core.db import create_user

cdb.init_core_db()
ORG = "test_csrf"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_org_users WHERE org_id=%s", (ORG,))


def _builder_client(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    create_user(ORG, "b", "pw", role="builder")
    c = create_app(ORG).test_client()
    c.post("/login", data={"username": "b", "password": "pw"})
    return c


# ── TI-F4: CSRF (cross-origin POST rejected; same-origin / no-Origin allowed) ────
def test_csrf_blocks_cross_origin_post(monkeypatch):
    _clean()
    try:
        c = _builder_client(monkeypatch)
        r = c.post("/staff/add", data={"name": "X"}, headers={"Origin": "http://evil.example"})
        assert r.status_code == 403, "a cross-origin state-changing POST must be rejected"
    finally:
        _clean()


def test_csrf_allows_same_origin_post(monkeypatch):
    _clean()
    try:
        c = _builder_client(monkeypatch)
        r = c.post("/staff/add", data={"name": "X"}, headers={"Origin": "http://localhost"})
        assert r.status_code != 403       # same-origin → allowed (redirect/200, just not the CSRF 403)
    finally:
        _clean()


def test_csrf_allows_missing_origin(monkeypatch):
    """Lenient: a request with NO Origin header passes (many legitimate clients omit it)."""
    _clean()
    try:
        c = _builder_client(monkeypatch)
        assert c.post("/staff/add", data={"name": "X"}).status_code != 403
    finally:
        _clean()


def test_csrf_inert_when_auth_off(monkeypatch):
    """Auth OFF (owner localhost): even a cross-origin POST from loopback is NOT blocked — workflow unchanged."""
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    c = create_app(ORG).test_client()
    assert c.post("/staff/add", data={"name": "X"}, headers={"Origin": "http://evil.example"}).status_code != 403


# ── TI-F6: rate-limit ────────────────────────────────────────────────────────────
def test_login_is_rate_limited(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = create_app(ORG).test_client()                # fresh app → fresh per-app buckets
        codes = [c.post("/login", data={"username": "nobody", "password": "x"}).status_code for _ in range(12)]
        assert 429 in codes, "login must start returning 429 once the per-IP limit is exceeded"
        assert codes[:10].count(429) == 0, "the first 10 attempts must be allowed (under the limit)"
    finally:
        _clean()


def test_rate_ok_helper():
    buckets = {}
    allowed = [_rate_ok(buckets, "t", "1.2.3.4", 3, 100) for _ in range(5)]
    assert allowed == [True, True, True, False, False]   # 3 allowed, then over the limit
    assert _rate_ok(buckets, "t", "9.9.9.9", 3, 100) is True   # a different key has its own window


def test_samesite_cookie_configured():
    app = create_app(ORG)
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Strict"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
