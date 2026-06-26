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
            cur.execute("DELETE FROM core_expenses WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_stock_prices WHERE org_id=%s", (ORG,))
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


def test_stock_variance_detects_shrinkage():
    _clean()
    try:
        iid = stock.add_item(ORG, "Whisky", "btl", par_level=2)
        stock.record_count(ORG, iid, 20)                                 # baseline (book_before 0) → not flagged
        stock.record_count(ORG, iid, 17)                                 # book 20, counted 17 → short by 3
        var = stock.stock_variance(ORG)
        assert len(var) == 1 and var[0]["item"] == "Whisky" and var[0]["variance"] == -3.0
        stock.record_count(ORG, iid, 17)                                 # book 17, counted 17 → variance 0
        assert stock.stock_variance(ORG) == []                          # a matching recount clears it
    finally:
        _clean()


def test_receive_purchase_restocks_and_logs_expense():
    from core import expenses
    _clean()
    try:
        iid = stock.add_item(ORG, "Milk", "L", par_level=10)
        stock.record_count(ORG, iid, 2)                                  # low
        stock.receive_purchase(ORG, iid, 20, 30, "Dairy Co")            # receive 20 @ $30 total
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 22          # restocked (2 + 20) — stock side
        es = expenses.expense_summary(ORG, 30)
        assert es["total"] == 30.0 and any(c["category"] == "stock" for c in es["by_category"])  # accountant side
    finally:
        _clean()


def test_stock_price_compare():
    _clean()
    try:
        iid = stock.add_item(ORG, "Eggs", "tray", par_level=2)
        for sup, pr in [("Market A", 5.0), ("Market B", 4.2), ("Market C", 4.8)]:
            stock.add_price(ORG, iid, sup, pr)
        cheap = stock.cheapest_overview(ORG)
        assert cheap[iid]["supplier"] == "Market B" and cheap[iid]["price"] == 4.2   # cheapest flagged
        assert len(stock.item_prices(ORG, iid)) == 3
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


def test_record_count_idempotent_replay():
    """DOMAIN-IDEMP (s55): the same client_key replays to the same count_id and doesn't re-set on_hand."""
    _clean()
    try:
        iid = stock.add_item(ORG, "Rice", "kg", par_level=5)
        c1 = stock.record_count(ORG, iid, 8, client_key="cnt-1")
        c2 = stock.record_count(ORG, iid, 99, client_key="cnt-1")        # replay (even a different qty) → ignored
        assert c1 == c2                                                  # same count row
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 8         # on_hand from the ORIGINAL count, not 99
    finally:
        _clean()


def test_receive_purchase_idempotent_replay():
    from core import expenses
    _clean()
    try:
        iid = stock.add_item(ORG, "Sugar", "kg", par_level=5)
        stock.record_count(ORG, iid, 2)
        e1 = stock.receive_purchase(ORG, iid, 20, 30, "Sup A", client_key="rcv-1")
        e2 = stock.receive_purchase(ORG, iid, 20, 30, "Sup A", client_key="rcv-1")    # replay
        assert e1 == e2                                                  # same expense, not a 2nd
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 22        # restocked ONCE (2+20), not 42
        assert expenses.expense_summary(ORG, 30)["total"] == 30.0      # expense logged ONCE
    finally:
        _clean()
