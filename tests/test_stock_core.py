"""core.stock — a real inventory domain (item catalog · par · counts · low-stock reorder), shadow-style: its
own tables, not TWB's live stock. + the wizard /stock manager."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import stock

cdb.init_core_db()
ORG = "test_stock_core"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_stock_counts WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_stock_items WHERE org_id=%s", (ORG,))


def test_stock_item_count_and_low():
    _clean()
    try:
        iid = stock.add_item(ORG, "Flour", "kg", "baking", par_level=10)
        assert [i["name"] for i in stock.list_items(ORG)] == ["Flour"]
        stock.record_count(ORG, iid, 4)                                   # below par
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 4
        assert [l["name"] for l in stock.low_stock_items(ORG)] == ["Flour"]
        stock.record_count(ORG, iid, 20)                                  # restock above par
        assert stock.low_stock_items(ORG) == []
        stock.deactivate_item(ORG, iid)
        assert stock.list_items(ORG) == []                               # gone from the active list
    finally:
        _clean()


def test_stock_value_summary():
    _clean()
    try:
        stock.add_item(ORG, "Oil", "L", "kitchen", par_level=5, unit_cost=3)
        iid = stock.list_items(ORG)[0]["item_id"]
        stock.record_count(ORG, iid, 10)                                  # 10 × $3 = $30 on-hand value
        s = stock.stock_summary(ORG)
        assert s["item_count"] == 1 and s["total_value"] == 30.0
    finally:
        _clean()


def test_stock_page_and_actions(monkeypatch):
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        c = create_app(ORG).test_client()
        assert "Turn it on" in c.get("/stock").get_data(as_text=True)     # off → enable prompt
        set_config(ORG, {"categories": {"stock": {"enabled": True}}})
        c.post("/stock/add", data={"name": "Sugar", "unit": "kg", "par_level": "5"})
        assert "Sugar" in c.get("/stock").get_data(as_text=True)          # added via the page
        iid = stock.list_items(ORG)[0]["item_id"]
        c.post("/stock/count", data={"item_id": str(iid), "qty": "2"})    # count below par
        assert "⚠️" in c.get("/stock").get_data(as_text=True)            # shows in reorder
    finally:
        _clean()
