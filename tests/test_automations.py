"""core.automations — one-tap recipes (condition → action) riding our existing detectors (no model cost).
Config-only; the evaluator shows what would fire. + the /automations wizard page (toggle + who-to-alert)."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import automations as au, stock
from core.tenant_config import set_config

ORG = "test_autom"


def _clean():
    cdb.init_core_db()                                  # ensure the schema (incl. automation_dispatches) exists
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            for t in ("core_sales", "core_stock_counts", "core_stock_items", "core_audit",
                      "automation_dispatches"):
                cur.execute("DELETE FROM %s WHERE org_id=%%s" % t, (ORG,))


def test_set_and_enabled_recipes():
    _clean()
    try:
        au.set_recipe(ORG, "low_stock", True, who="buyer")
        au.set_recipe(ORG, "lateness", True)
        en = au.enabled_recipes(ORG)
        assert en["low_stock"]["enabled"] and en["low_stock"]["who"] == "buyer"
        assert en["lateness"]["enabled"]
        assert au.set_recipe(ORG, "not_a_recipe", True) is False        # unknown recipe rejected
    finally:
        _clean()


def test_evaluate_fires_low_stock_only_when_enabled_and_below_par():
    _clean()
    try:
        set_config(ORG, {"categories": {"stock": {"enabled": True}}})
        iid = stock.add_item(ORG, "Milk", "L", par_level=10)
        stock.record_count(ORG, iid, 2)                                 # 2 ≤ par 10 → low stock
        assert au.evaluate(ORG) == []                                  # recipe off → nothing fires
        au.set_recipe(ORG, "low_stock", True, who="buyer")
        fired = au.evaluate(ORG)
        assert any(f["key"] == "low_stock" and f["who"] == "whoever buys stock" and f["fires"] for f in fired)
    finally:
        _clean()


def test_dispatch_sends_to_target_then_debounces():
    _clean()
    try:
        set_config(ORG, {"categories": {"stock": {"enabled": True}}})
        iid = stock.add_item(ORG, "Milk", "L", par_level=10)
        stock.record_count(ORG, iid, 2)                             # low stock fires
        au.set_recipe(ORG, "low_stock", True, who="buyer")
        calls = []

        def send(c, t):
            calls.append((c, t))

        assert au.dispatch(ORG, send) == [] and calls == []        # no target → nothing sent (safe by default)
        au.set_target(ORG, "buyer", 555)
        sent = au.dispatch(ORG, send)
        assert len(sent) == 1 and calls and calls[0][0] == 555      # sent once to the configured target
        assert au.dispatch(ORG, send) == [] and len(calls) == 1    # within cooldown → debounced, no re-send
    finally:
        _clean()


def test_automations_page_toggle(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        c = create_app(ORG).test_client()
        assert "Automations" in c.get("/automations").get_data(as_text=True)
        c.post("/automations/save", data={"on": ["sales_drop"], "who_sales_drop": "owner"})
        assert au.enabled_recipes(ORG).get("sales_drop", {}).get("enabled") is True
        assert au.enabled_recipes(ORG).get("lateness", {}).get("enabled") in (None, False)   # unchecked → off
    finally:
        _clean()
