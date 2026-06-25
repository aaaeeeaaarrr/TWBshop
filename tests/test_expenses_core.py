"""core.expenses — a real expense log (the Accountant domain): record by supplier/category + summaries, +
the wizard /expenses page + its Reports section. Shadow-style (own table)."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import expenses

cdb.init_core_db()
ORG = "test_expenses"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_expenses WHERE org_id=%s", (ORG,))


def test_expense_log_and_summary():
    _clean()
    try:
        expenses.add_expense(ORG, 12.5, "Market A", "produce")
        expenses.add_expense(ORG, 7.5, "Market A", "produce")
        expenses.add_expense(ORG, 20, "Gas Co", "utilities")
        s = expenses.expense_summary(ORG, 30)
        assert s["total"] == 40.0 and s["count"] == 3
        cats = {c["category"]: c["total"] for c in s["by_category"]}
        assert cats["produce"] == 20.0 and cats["utilities"] == 20.0
        assert len(expenses.list_expenses(ORG)) == 3
    finally:
        _clean()


def test_expenses_page_add_and_reports(monkeypatch):
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        c = create_app(ORG).test_client()
        assert "Turn it on" in c.get("/expenses").get_data(as_text=True)         # off → enable prompt
        set_config(ORG, {"categories": {"accountant": {"enabled": True}}})
        c.post("/expenses/add", data={"amount": "15", "supplier": "Shop", "category": "supplies"})
        assert "supplies" in c.get("/expenses").get_data(as_text=True)           # logged via the page
        assert "🍚 Expenses" in c.get("/reports").get_data(as_text=True)         # multi-domain reports → 3
    finally:
        _clean()
