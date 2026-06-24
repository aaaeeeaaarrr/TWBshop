"""Wizard /dashboard — the task-card / completion prototype: benefit-framed cards, colour-shifting progress
bars, real setup/health/config data. Additive (alongside /customer)."""
import core.db as cdb
import wizard.app as wa
from wizard.app import create_app, dashboard_cards, _bar_color

cdb.init_core_db()
ORG = "test_dash"


def test_bar_colour_progression():
    assert _bar_color(0) == "#9ca3af"        # grey — not started
    assert _bar_color(0.5) == "#d97706"      # amber — mid
    assert _bar_color(1.0) == "#16a34a"      # green — done
    assert _bar_color(0.5) != _bar_color(1.0)


def test_dashboard_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    body = create_app(ORG).test_client().get("/dashboard").get_data(as_text=True)
    assert "Your system" in body and "Go live" in body                       # headline + progress
    assert "Track your team" in body and "Connect bot" in body and "Money sorted" in body  # benefit cards
    assert "width:" in body and "#16a34a" in body                            # colour-shifting bars (done=green)


def test_dashboard_cards_use_real_data():
    cdb.ensure_org(ORG, "T")
    d = dashboard_cards(ORG)
    assert len(d["activation"]) == 5 and len(d["modules"]) == 5
    assert all(set(c) >= {"icon", "name", "reward", "done", "total", "link"} for c in d["activation"])
    assert any(c["name"] == "Track your team" for c in d["modules"])          # attendance benefit-framed
