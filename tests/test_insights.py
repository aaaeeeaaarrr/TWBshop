"""core.insights — the cross-domain 'needs attention' feed (lateness · stock low · spend spike · sales drop),
+ the AI-card feed + the dashboard banner."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import insights, stock
from core.tenant_config import set_config

cdb.init_core_db()
ORG = "test_insights"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            for t in ("core_stock_items", "core_stock_counts", "core_stock_prices", "core_sales", "core_expenses"):
                cur.execute("DELETE FROM %s WHERE org_id=%%s" % t, (ORG,))


def test_attention_feed_cross_domain():
    _clean()
    try:
        assert insights.attention_feed(ORG) == []                    # nothing on → no alerts
        set_config(ORG, {"categories": {"stock": {"enabled": True}}})
        iid = stock.add_item(ORG, "Flour", "kg", par_level=10)
        stock.record_count(ORG, iid, 2)                              # below par
        feed = insights.attention_feed(ORG)
        assert any(a["domain"] == "stock" for a in feed)             # stock-low surfaced in the cross-domain feed
    finally:
        _clean()


def test_feed_on_ai_card_and_dashboard(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        set_config(ORG, {"categories": {"stock": {"enabled": True}}})
        iid = stock.add_item(ORG, "Sugar", "kg", par_level=5)
        stock.record_count(ORG, iid, 1)
        c = create_app(ORG).test_client()
        assert "Needs attention" in c.get("/card/ai_assist").get_data(as_text=True)   # the AI feed (cross-domain)
        assert "Needs attention" in c.get("/dashboard").get_data(as_text=True)        # the dashboard banner
    finally:
        _clean()
