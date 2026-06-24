"""Wizard /dashboard — categorized benefit BOXES with REAL completion + colour-shifting bars, a STABLE
order (find anything), a 'Do this next' spotlight (funnel), and a sticky category FILTER (ergonomics).
Additive (alongside /customer)."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app, dashboard_cards, _bar_color
from core.tenant_config import set_config

cdb.init_core_db()
ORG = "test_dash"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))


def test_bar_colour_progression():
    assert _bar_color(0) == "#9ca3af"        # grey — not started
    assert _bar_color(0.5) == "#d97706"      # amber — mid
    assert _bar_color(1.0) == "#16a34a"      # green — done


def test_boxes_categorized_stable_and_real_progress():
    _reset()
    try:
        d = dashboard_cards(ORG)
        assert len(d["cards"]) == 14
        assert d["cards"][0]["name"] == "Connect bot"                  # highest value, stable top
        assert {c["cat"] for c in d["cards"]} >= {"att", "cover", "acct", "stock", "pos", "hr"}
        assert any(cat[0] == "all" for cat in d["cats"])               # "All tools" filter present
        par = next(c for c in d["cards"] if c["name"] == "Par levels")
        assert par["done"] == 0                                        # sub-step gated: off while stock off
        set_config(ORG, {"categories": {"stock": {"enabled": True, "par_levels": True}}})
        par2 = next(c for c in dashboard_cards(ORG)["cards"] if c["name"] == "Par levels")
        assert par2["done"] == 1                                       # real progress once stock is on
        assert dashboard_cards(ORG)["cards"][0]["name"] == "Connect bot"   # order still stable
        assert all(c.get("cascade") for c in d["cards"])                   # every box has a cascade line
    finally:
        _reset()


def test_customer_landing_is_dashboard(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        c = create_app(ORG).test_client()
        landing = c.get("/customer").get_data(as_text=True)
        assert "Your system" in landing and "Connect bot" in landing       # /customer is the dashboard now
        cfg = c.get("/customer/config").get_data(as_text=True)
        assert "Apply changes" in cfg                                       # editor moved to /customer/config
    finally:
        _reset()


def test_dashboard_renders_filter_spotlight_bars(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        body = create_app(ORG).test_client().get("/dashboard").get_data(as_text=True)
        assert "Your system" in body and "Connect bot" in body
        assert "Do this next" in body                                  # the spotlight
        assert "All tools" in body and "data-cat" in body and "filt(" in body  # sticky filter + JS
        assert "position:sticky" in body                               # follows scroll
        assert "what you unlock" in body and "clock in from their phone" in body  # cascade reveal + copy
        assert "#16a34a" in body or "#9ca3af" in body                  # colour bars
    finally:
        _reset()
