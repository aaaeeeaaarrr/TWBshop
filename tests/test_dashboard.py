"""Wizard /dashboard — ranked benefit cards with REAL per-card progress + colour-shifting bars. Highest-
reward (most cascade) card on top; modules show real config progress, not just on/off. Additive."""
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


def test_stable_order_real_progress_and_next():
    _reset()
    try:
        d = dashboard_cards(ORG)
        assert len(d["cards"]) == 6
        assert d["cards"][0]["name"] == "Track your team"            # STABLE: highest-value always top
        money = next(c for c in d["cards"] if c["name"] == "Money sorted")
        assert money["done"] == 0 and money["total"] == 2            # module off → real 0/2 (not on/off)
        assert "Money sorted" in [c["name"] for c in d["next"]]      # top-3 incomplete → in the spotlight
        # fully configure accountant → it stays in the grid (stable) but drops from "next"
        set_config(ORG, {"categories": {"accountant": {"enabled": True, "food_money": {"enabled": True}}}})
        d2 = dashboard_cards(ORG)
        m2 = next(c for c in d2["cards"] if c["name"] == "Money sorted")
        assert m2["done"] == m2["total"]                             # real progress → done
        assert "Money sorted" not in [c["name"] for c in d2["next"]]  # left the spotlight
        assert d2["cards"][0]["name"] == "Track your team"           # order unchanged (stable)
    finally:
        _reset()


def test_dashboard_renders_with_spotlight(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        body = create_app(ORG).test_client().get("/dashboard").get_data(as_text=True)
        assert "Your system" in body and "Track your team" in body and "set up" in body
        assert "Do this next" in body                                # the spotlight box
        assert "#16a34a" in body or "#d97706" in body or "#9ca3af" in body     # colour-shifting bars
    finally:
        _reset()
