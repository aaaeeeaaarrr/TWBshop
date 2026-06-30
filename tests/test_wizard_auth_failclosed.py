"""W3 #2 — auth FAIL-CLOSED + PII behind authz (owner 2026-06-30; PRODUCT SECURITY & IP law).

Locks three invariants so they can't silently regress (DRASTIC/STRUCTURAL-CHANGE protocol — the guard is
the law's enforcement, not my memory):
  • TI-F1  with auth OFF, only a LOOPBACK peer may reach the wizard — a non-loopback request is 403'd, so an
           accidental public / 0.0.0.0 bind without WIZARD_AUTH=1 can't expose the console.
  • TI-F2  with auth ON but no user seeded, the console is DENY-CLOSED (everything → /login), not wide open.
  • TI-F5  employee PII (national id · passport · tax · SSN · address · bank) is rendered + writable ONLY for a
           PII-authorized session; an unauthorized session sees a mask and a crafted POST can't overwrite it.

All INERT for the owner's localhost/tunnel workflow (auth OFF + loopback) — proven by test_auth_off_*.
Complements tests/test_wizard_roles.py (the role allowlist) + tests/test_client_builder_separation.py (Telegram).
"""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core.db import create_user
from core.onboarding_flow import add_staff_manual, get_staff, update_staff_profile

cdb.init_core_db()
ORG = "test_failclosed"

PUBLIC = {"REMOTE_ADDR": "203.0.113.9"}     # a non-loopback peer (TEST-NET-3, RFC 5737)


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_org_users WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))


# ── TI-F1: loopback fail-closed when auth is OFF ─────────────────────────────────
def test_nonloopback_is_403_when_auth_off(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    c = create_app(ORG).test_client()
    # a public (non-loopback) peer is refused at every route, even with auth off
    for route in ("/", "/customer", "/staff", "/shadow"):
        assert c.get(route, environ_overrides=PUBLIC).status_code == 403, \
            "%s must 403 a non-loopback peer when auth is off" % route


def test_loopback_open_when_auth_off(monkeypatch):
    """Owner's localhost/tunnel workflow is unchanged — a loopback peer (the test client default) is open."""
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    c = create_app(ORG).test_client()
    assert c.get("/").status_code == 200
    assert c.get("/customer/config").status_code == 200


def test_loopback_helper_semantics():
    app = create_app(ORG)
    with app.test_request_context(environ_overrides={"REMOTE_ADDR": "127.0.0.1"}):
        assert wa._is_loopback_request() is True
    with app.test_request_context(environ_overrides={"REMOTE_ADDR": "::1"}):
        assert wa._is_loopback_request() is True
    with app.test_request_context(environ_overrides={"REMOTE_ADDR": "203.0.113.9"}):
        assert wa._is_loopback_request() is False
    with app.test_request_context(environ_overrides={"REMOTE_ADDR": ""}):
        assert wa._is_loopback_request() is False     # unknown peer → not trusted as local


# ── TI-F2: no-user bootstrap window is deny-closed when auth is ON ───────────────
def test_no_user_bootstrap_is_failclosed(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = create_app(ORG).test_client()             # 0 users seeded
        r = c.get("/")                                 # was wide-open before the fix
        assert r.status_code == 302 and "/login" in r.headers.get("Location", ""), \
            "0-users + auth-on must redirect to /login, not open the console"
        # the login page itself stays reachable (so the operator can seed + log in) + shows a bootstrap hint
        lg = c.get("/login")
        assert lg.status_code == 200 and "No accounts exist" in lg.get_data(as_text=True)
    finally:
        _clean()


def test_seeded_builder_still_reaches_console(monkeypatch):
    """The fail-closed bootstrap doesn't lock anyone out: seed a builder via the (CLI) create_user → log in → in."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        create_user(ORG, "b", "pw", role="builder")
        c = create_app(ORG).test_client()
        c.post("/login", data={"username": "b", "password": "pw"})
        assert c.get("/").status_code == 200
    finally:
        _clean()


# ── TI-F5: PII behind authz (render + write) ────────────────────────────────────
def _staff_with_pii():
    sid = add_staff_manual(ORG, "Pat Test", role="baker")
    update_staff_profile(ORG, sid, {"national_id": "SECRET-NID-123", "bank_account": "ACCT-999"})
    return sid


def test_pii_shown_to_authorized(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)   # owner localhost → authorized (inert)
    try:
        sid = _staff_with_pii()
        c = create_app(ORG).test_client()
        html = c.get("/staff/edit/%d" % sid).get_data(as_text=True)
        assert "SECRET-NID-123" in html and "ACCT-999" in html   # authorized sees the real values
    finally:
        _clean()


def test_pii_masked_for_unauthorized(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    monkeypatch.setattr(wa, "_pii_authorized", lambda: False)   # a future lesser/unknown role
    try:
        sid = _staff_with_pii()
        c = create_app(ORG).test_client()
        html = c.get("/staff/edit/%d" % sid).get_data(as_text=True)
        assert "SECRET-NID-123" not in html and "ACCT-999" not in html, "raw PII leaked to an unauthorized view"
        assert "hidden" in html                                  # the masked control is shown instead
    finally:
        _clean()


def test_pii_write_blocked_for_unauthorized(monkeypatch):
    """Server-side belt: an unauthorized POST can't overwrite PII even if the field is hand-crafted into the form."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    monkeypatch.setattr(wa, "_pii_authorized", lambda: False)
    try:
        sid = _staff_with_pii()
        c = create_app(ORG).test_client()
        c.post("/staff/update", data={"staff_id": str(sid), "name": "Pat Test",
                                      "national_id": "HACKED", "bank_account": "HACKED"})
        s = get_staff(ORG, sid)
        assert s["national_id"] == "SECRET-NID-123" and s["bank_account"] == "ACCT-999", \
            "unauthorized POST overwrote PII"
    finally:
        _clean()


def test_pii_write_allowed_for_authorized(monkeypatch):
    """The same edit DOES land for an authorized session (the gate doesn't break normal editing)."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)       # authorized
    try:
        sid = _staff_with_pii()
        c = create_app(ORG).test_client()
        c.post("/staff/update", data={"staff_id": str(sid), "name": "Pat Test", "national_id": "NEW-NID"})
        assert get_staff(ORG, sid)["national_id"] == "NEW-NID"
    finally:
        _clean()


# ── TI-F3: session ↔ org binding (a session is valid only for the tenant it logged into) ─────────
def test_session_bound_to_its_org(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        create_user(ORG, "b", "pw", role="builder")
        c = create_app(ORG).test_client()
        with c.session_transaction() as sess:                    # a cookie minted for ANOTHER org
            sess["user"], sess["role"], sess["org"] = "b", "builder", "OTHER_ORG"
        r = c.get("/")
        assert r.status_code in (302, 303) and "/login" in r.headers.get("Location", ""), \
            "a foreign-org session must be bounced, not honored"
        c.post("/login", data={"username": "b", "password": "pw"})   # real login binds org=ORG
        assert c.get("/").status_code == 200
    finally:
        _clean()


# ── DL-F2: a failed web check-in returns a GENERIC message, never the raw exception text ─────────
def test_web_checkin_error_is_generic(monkeypatch):
    import core.attendance as ca
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    monkeypatch.setattr(wa, "get_config", lambda o: {})          # no DB
    monkeypatch.setattr(ca, "check_in", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("DB host secret-internal.example at 10.1.2.3 refused")))
    staff = {"org_id": ORG, "staff_id": 1, "shift_windows": [{"start": "09:00", "end": "17:00"}]}
    res = wa._do_web_checkin(staff, "11.5", "104.9")
    assert res["ok"] is False
    assert "secret-internal" not in res["error"] and "10.1.2.3" not in res["error"]   # no internals leaked
    assert "try again" in res["error"]
