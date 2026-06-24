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


def test_top_card_is_highest_reward_and_modules_show_real_progress():
    _reset()
    try:
        d = dashboard_cards(ORG)
        assert len(d["cards"]) == 6
        assert d["cards"][0]["name"] == "Track your team"            # highest-value incomplete ranked top
        money = next(c for c in d["cards"] if c["name"] == "Money sorted")
        assert money["done"] == 0 and money["total"] == 2            # module off → real 0/2 (not just "off")
        set_config(ORG, {"categories": {"accountant": {"enabled": True}}})
        money2 = next(c for c in dashboard_cards(ORG)["cards"] if c["name"] == "Money sorted")
        assert money2["done"] == 1                                   # turning it on = real progress 1/2
    finally:
        _reset()


def test_dashboard_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        body = create_app(ORG).test_client().get("/dashboard").get_data(as_text=True)
        assert "Your system" in body and "Track your team" in body and "set up" in body
        assert "#16a34a" in body or "#d97706" in body or "#9ca3af" in body     # colour-shifting bars
    finally:
        _reset()
