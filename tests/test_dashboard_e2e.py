"""Dashboard e2e — the full prototype flow coheres on one org: industry template → plan (locks/unlocks the
right cards) → enable a module + a sub-option from its card inside → dashboard reflects it → reports renders."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app, dashboard_cards
from wizard.templates import apply_template
from core.tenant_config import get_config

cdb.init_core_db()
ORG = "test_dash_e2e"


def _reset():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))


def test_dashboard_full_flow(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _reset()
    try:
        c = create_app(ORG).test_client()
        apply_template(ORG, "retail")                                  # 1. template → back_office plan
        assert get_config(ORG)["package"] == "back_office"
        locked = {x["name"] for x in dashboard_cards(ORG)["cards"] if x.get("locked")}
        assert "Turn on POS" in locked and "Turn on accounting" not in locked   # plan gates correctly
        c.post("/card/accountant/save", data={"categories.accountant.enabled": "on",
                                              "categories.accountant.food_money.enabled": "on"})   # 2. from the card
        assert get_config(ORG)["categories"]["accountant"]["enabled"] is True
        food = next(x for x in dashboard_cards(ORG)["cards"] if x["name"] == "Food allowance")
        assert food["done"] == 1                                       # 3. dashboard reflects it
        assert "Reports" in c.get("/reports").get_data(as_text=True)   # 4. reports renders
    finally:
        _reset()
