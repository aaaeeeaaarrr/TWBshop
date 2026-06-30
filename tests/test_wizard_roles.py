"""Wizard builder-vs-customer ROLE — deny-by-default authorization (owner 2026-06-30; PRODUCT SECURITY & IP
law). A logged-in CUSTOMER reaches ONLY their own surface; the builder/cut-over console (/, /shadow, /whatif,
export/import, packages/set) is builder-only. Inert while auth is OFF (the owner's localhost view unchanged).
Models tests/test_wizard_auth.py. Complements tests/test_client_builder_separation.py (the Telegram axis)."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app, CUSTOMER_OK, _is_builder
from core.db import create_user

cdb.init_core_db()
ORG = "test_roles"

# A representative set of CUSTOMER routes — the guard must NOT 403 these (a 500 on an empty test org is fine;
# the point is the guard ALLOWS them through).
CUSTOMER_ROUTES = ["/customer", "/customer/config", "/dashboard", "/staff", "/reports", "/presets",
                   "/policy", "/setup", "/automations", "/health", "/audit", "/roadmap", "/packages"]
BUILDER_ROUTES = ["/", "/shadow", "/whatif", "/export"]


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_org_users WHERE org_id=%s", (ORG,))


def _client_as(role):
    create_user(ORG, role + "_u", "pw", role=role)
    c = create_app(ORG).test_client()
    c.post("/login", data={"username": role + "_u", "password": "pw"})
    return c


def test_customer_is_403_from_builder_routes(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = _client_as("customer")
        for route in BUILDER_ROUTES:
            assert c.get(route).status_code == 403, "customer must be 403'd from %s" % route
    finally:
        _clean()


def test_customer_reaches_their_own_pages(monkeypatch):
    """The CUSTOMER_OK allowlist is complete enough — the guard never 403s a legit customer route."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = _client_as("customer")
        for route in CUSTOMER_ROUTES:
            assert c.get(route).status_code != 403, "customer wrongly 403'd from %s (fix CUSTOMER_OK)" % route
    finally:
        _clean()


def test_builder_reaches_the_console(monkeypatch):
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = _client_as("builder")
        assert c.get("/").status_code == 200
        assert c.get("/shadow").status_code == 200
    finally:
        _clean()


def test_owner_role_is_a_builder_no_lockout(monkeypatch):
    """The legacy default role 'owner' is treated as a builder (anti-lockout)."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        assert _is_builder("owner") and _is_builder("builder")
        assert not _is_builder("customer") and not _is_builder(None)
        create_user(ORG, "owner", "pw")                       # default role 'owner'
        c = create_app(ORG).test_client()
        c.post("/login", data={"username": "owner", "password": "pw"})
        assert c.get("/").status_code == 200                  # owner=builder reaches the console
    finally:
        _clean()


def test_deny_by_default_blocks_a_customer_mutation(monkeypatch):
    """A builder-only POST (not in CUSTOMER_OK) is forbidden to a customer — deny-by-default covers mutations,
    not just hidden links."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = _client_as("customer")
        assert c.post("/packages/set", data={}).status_code == 403
    finally:
        _clean()


def test_builder_only_set_is_disjoint_from_customer_ok():
    """Structural: a builder-only route must NEVER be listed in CUSTOMER_OK (would make it customer-visible)."""
    builder_only = {"index", "shadow", "whatif", "packages_set", "export", "import_get", "import_post"}
    assert builder_only.isdisjoint(CUSTOMER_OK), \
        "a builder-only route leaked into CUSTOMER_OK: %s" % (builder_only & CUSTOMER_OK)


def test_customer_html_has_no_admin_nav(monkeypatch):
    """Customer-facing pages carry no ← admin / admin / shadow nav link (builder bleed — DL-F1).
    The _builder_link wrap hides them for a customer session while keeping them for the builder/owner."""
    _clean()
    monkeypatch.setattr(wa, "auth_enabled", lambda: True)
    try:
        c = _client_as("customer")
        for route in ("/customer", "/dashboard", "/customer/config", "/reports", "/staff"):
            html = c.get(route).get_data(as_text=True)
            assert "← admin" not in html, "%s leaks the ← admin link" % route
            assert ">admin</a>" not in html, "%s leaks the admin link" % route
            assert "href='/shadow'" not in html, "%s leaks a /shadow link" % route
    finally:
        _clean()


def test_auth_off_unchanged(monkeypatch):
    """Owner's localhost/tunnel workflow: auth off → the console is open, no role needed, links intact."""
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cl = create_app(ORG).test_client()
    assert cl.get("/").status_code == 200
    assert "← admin" in cl.get("/customer/config").get_data(as_text=True)   # builder/owner still sees nav
