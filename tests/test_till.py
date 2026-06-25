"""core.till — POS shift / cash-drawer money model (harvested from POSBusiness, re-tested from scratch on real
rows): atomic one-open-shift claim · expected_cash formula · variance-reason gate · Z-report · idempotent close ·
sales tie to the shift. HIGH-RISK money."""
import core.db as cdb
from shared.database import _db
from core import till, pos, stock

cdb.init_core_db()
ORG = "test_till"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            for t in ("core_cash_events", "core_shifts", "core_sales", "core_stock_counts", "core_stock_items",
                      "core_audit"):
                cur.execute("DELETE FROM %s WHERE org_id=%%s" % t, (ORG,))


def test_open_is_atomic_and_sale_ties_to_shift():
    _clean()
    try:
        s, err = till.open_shift(ORG, "owner", 50)
        assert err is None and s["shift_id"]
        s2, err2 = till.open_shift(ORG, "owner", 50)                  # S3: a 2nd open shift is rejected
        assert s2 is None and err2 == "already_open"
        iid = stock.add_item(ORG, "Coffee", "cup", par_level=2)
        pos.record_sale(ORG, iid, 2, 3.0)                            # $6 cash → counts toward the shift
        fin = till.shift_summary(ORG)
        assert fin["cash_sales"] == 6.0 and fin["order_count"] == 1 and fin["expected_cash"] == 56.0   # 50 + 6
    finally:
        _clean()


def test_expected_cash_formula():
    _clean()
    try:
        till.open_shift(ORG, "owner", 100)
        iid = stock.add_item(ORG, "Tea", "cup", par_level=2)
        pos.record_sale(ORG, iid, 4, 2.5)                            # $10 cash sales
        till.cash_event(ORG, "drop", 30)                            # $30 to the safe (out)
        till.cash_event(ORG, "payout", 5)                          # $5 payout (out)
        till.cash_event(ORG, "refund", 2.5)                        # $2.50 cash refund (out)
        fin = till.shift_summary(ORG)
        assert fin["expected_cash"] == 72.5                         # 100 + 10 − 30 − 5 − 2.5
        assert fin["drops"] == 30 and fin["refunds"] == 2.5 and fin["net_after_refunds"] == 7.5
    finally:
        _clean()


def test_close_variance_gate_and_zreport():
    _clean()
    try:
        till.open_shift(ORG, "owner", 50)
        iid = stock.add_item(ORG, "Bun", "pc", par_level=2)
        pos.record_sale(ORG, iid, 5, 2.0)                           # $10 → expected 60
        z, err = till.close_shift(ORG, 55, None)                    # short $5, no note → blocked (≥ $2)
        assert z is None and err["code"] == "variance_reason_required" and err["variance"] == -5.0
        z, err = till.close_shift(ORG, 55, "till short, investigating")
        assert err is None and z["expected_cash"] == 60.0 and z["counted_cash"] == 55.0 and z["variance"] == -5.0
        assert z["net_sales"] == 10.0
        z2, err2 = till.close_shift(ORG, 55, "x")                   # S2: shift is closed → no open shift
        assert z2 is None and err2 == "no_open_shift"
    finally:
        _clean()


def test_clean_close_zero_variance_needs_no_note():
    _clean()
    try:
        till.open_shift(ORG, "owner", 40)
        iid = stock.add_item(ORG, "Pie", "pc", par_level=2)
        pos.record_sale(ORG, iid, 1, 5.0)                           # $5 → expected 45
        z, err = till.close_shift(ORG, 45, None)                    # exact → no note required
        assert err is None and z["variance"] == 0.0
    finally:
        _clean()


def test_till_page_flow(monkeypatch):
    import wizard.app as wa
    from wizard.app import create_app
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        set_config(ORG, {"categories": {"pos": {"enabled": True}}})
        c = create_app(ORG).test_client()
        assert "No open shift" in c.get("/till").get_data(as_text=True)     # off → open form
        c.post("/till/open", data={"opening_float": "50"})
        assert "Expected drawer" in c.get("/till").get_data(as_text=True)   # open → summary
        c.post("/till/event", data={"type": "drop", "amount": "10"})
        assert till.shift_summary(ORG)["expected_cash"] == 40.0            # 50 − 10
        r = c.post("/till/close", data={"counted_cash": "40", "note": ""})  # clean close
        assert "closed=" in r.headers.get("Location", "")                  # → Z-report
    finally:
        _clean()


def test_shift_events_are_audited():
    from core import audit
    _clean()
    try:
        till.open_shift(ORG, "owner", 10)
        till.cash_event(ORG, "drop", 5)
        till.close_shift(ORG, 5, None)
        actions = {r["action"] for r in audit.recent(ORG, 10)}
        assert {"shift.opened", "cash_drawer.event", "shift.closed"} <= actions   # all chained
        assert audit.verify_chain(ORG)["result"] == "PASS"
    finally:
        _clean()
