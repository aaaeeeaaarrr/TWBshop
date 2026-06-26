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


def test_record_sale_idempotent_replay():
    """DOMAIN-IDEMP (s55): the SAME client_key replays to the SAME sale_id and decrements stock only ONCE —
    a crash-redelivered / double-tapped sale can't double-count revenue or over-decrement stock."""
    _clean()
    try:
        iid = stock.add_item(ORG, "Bun", "pcs", par_level=5)
        stock.record_count(ORG, iid, 10)
        s1 = pos.record_sale(ORG, iid, 3, 2.0, client_key="ck-1")
        s2 = pos.record_sale(ORG, iid, 3, 2.0, client_key="ck-1")        # replay
        assert s1 == s2                                                  # same sale, not a 2nd
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 7          # decremented once (10-3), not 4
        assert pos.sales_summary(ORG, 30)["count"] == 1                 # one sale, not two
    finally:
        _clean()


def test_oversell_clamps_on_hand_at_zero():
    """STOCK-NEG (s55): selling more than on-hand drives on_hand to 0, never negative (so a later count's
    shrinkage variance can't be corrupted by a phantom-negative book)."""
    _clean()
    try:
        iid = stock.add_item(ORG, "Tart", "pcs", par_level=2)
        stock.record_count(ORG, iid, 3)
        pos.record_sale(ORG, iid, 10, 1.0)                              # oversell by 7
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 0          # clamped at 0, not -7
    finally:
        _clean()


def test_void_sale_restocks_and_excludes_from_revenue():
    """2b refunds/voids (s55): voiding a sale gives the stock back, drops it from revenue (S4), and can be
    voided only ONCE (S1/S2)."""
    _clean()
    try:
        iid = stock.add_item(ORG, "Pie", "pcs", par_level=2)
        stock.record_count(ORG, iid, 10)
        sid = pos.record_sale(ORG, iid, 4, 3.0)                         # revenue 12, on_hand 6
        assert pos.sales_summary(ORG, 30)["revenue"] == 12.0
        info, err = pos.void_sale(ORG, sid, actor="mgr", reason="customer returned")
        assert err is None and info["amount"] == 12.0 and info["restocked"] == 4.0
        assert float(stock.list_items(ORG)[0]["on_hand"]) == 10         # stock given back (6 + 4)
        assert pos.sales_summary(ORG, 30)["revenue"] == 0.0            # revenue excludes the voided sale
        again, err2 = pos.void_sale(ORG, sid)                           # single-void by construction
        assert again is None and err2 == "not_found_or_already_voided"
    finally:
        _clean()


def test_voids_refunds_log_and_actor():
    """Forensics (s55): the voids/refunds log surfaces a voided sale + its drawer refund, and the actor who
    did it (TILL-ACTOR) — the classic POS shrinkage vector, ready for a camera review."""
    from core import investigate, till
    _clean()
    with _db() as c:                                                    # no stale open shift / cash events
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_cash_events WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_shifts WHERE org_id=%s", (ORG,))
    try:
        till.open_shift(ORG, who="cashier", opening_float=50)
        iid = stock.add_item(ORG, "Loaf", "pcs", par_level=2)
        stock.record_count(ORG, iid, 10)
        sid = pos.record_sale(ORG, iid, 2, 4.0)
        pos.void_sale(ORG, sid, actor="mgr", reason="returned")
        log = investigate.voids_refunds_log(ORG, 30)
        assert any("void" in e["what"] and e["amount"] == 8.0 for e in log)        # the void appears
        assert any("refund" in e["what"] and e["by"] == "mgr" for e in log)        # refund + the actor (TILL-ACTOR)
    finally:
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM core_cash_events WHERE org_id=%s", (ORG,))
                cur.execute("DELETE FROM core_shifts WHERE org_id=%s", (ORG,))
        _clean()
