"""core.optimize — the 'what the system handled for you' outcome view (read-only, honest counts)."""
import core.db as cdb
from core import optimize
import wizard.app as wa
from wizard.app import create_app

cdb.init_core_db()


def test_automation_summary_shape():
    rows = optimize.automation_summary("twb", 30)
    assert isinstance(rows, list)
    for r in rows:                                       # every row carries the contract keys
        assert {"area", "auto", "of", "label"} <= set(r.keys())
        assert r["auto"] <= r["of"] or r["of"] == r["auto"]
    assert any(r["area"] == "Monitoring" for r in rows)  # monitoring always reported


def test_headline_is_a_sentence():
    h = optimize.headline("twb", 30)
    assert "handled" in h and "automatically" in h


def test_optimize_page_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    page = create_app("twb").test_client().get("/optimize").get_data(as_text=True)
    assert "What your system handled for you" in page and "automatically" in page
