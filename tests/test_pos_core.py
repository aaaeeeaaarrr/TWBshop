"""core.pos — a real POS (record sale → revenue + auto-decrement Stock = cross-domain), + /pos + the sales
Reports section. Shadow-style (own table)."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import pos, stock

cdb.init_core_db()
ORG = "test_pos"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_sales WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_stock_counts WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_stock_items WHERE org_id=%s", (ORG,))


def test_sale_records_and_decrements_stock():
    _clean()
    try:
        iid = stock.add_item(ORG, "Bread", "loaf", par_level=5)
        stock.record_count(ORG, iid, 20)                                 # on_hand 20
        pos.record_sale(ORG, iid, 3, 1.5)                                # sell 3 → revenue 4.5
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 17          # cross-domain: stock auto-decremented
        s = pos.sales_summary(ORG, 30)
        assert s["revenue"] == 4.5 and s["count"] == 1 and s["units"] == 3
    finally:
        _clean()


def test_pos_page_sale_and_reports(monkeypatch):
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        c = create_app(ORG).test_client()
        assert "Turn it on" in c.get("/pos").get_data(as_text=True)      # off → enable prompt
        set_config(ORG, {"categories": {"pos": {"enabled": True}}})
        iid = stock.add_item(ORG, "Cake", "pcs", par_level=2)
        stock.record_count(ORG, iid, 10)
        c.post("/pos/sale", data={"item_id": str(iid), "qty": "2", "unit_price": "4"})
        assert pos.sales_summary(ORG, 30)["revenue"] == 8.0             # sale recorded via the page
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 8          # stock decremented (10 - 2)
        assert "🛒 Sales" in c.get("/reports").get_data(as_text=True)   # multi-domain reports → 4
    finally:
        _clean()
