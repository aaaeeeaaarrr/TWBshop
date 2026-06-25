"""Per-card 'inside' pages — each card opens its own industry-standard menu of options (review → wire),
not the generic editor. /card/<key>."""
import core.db as cdb
import wizard.app as wa
from wizard.app import create_app
from wizard.card_details import CARD_DETAILS

cdb.init_core_db()


def test_card_details_well_formed():
    assert {"accountant", "stock", "pos", "hr_payroll", "coverage", "reports",
            "ai_assist", "automations", "learn", "marketplace", "mobile_app"} <= set(CARD_DETAILS)
    for key, d in CARD_DETAILS.items():
        assert d.get("title") and d.get("what") and d.get("ref") and d.get("options")
        for name, desc, st in d["options"]:
            assert name and desc and st in ("built", "planned", "idea")


def test_card_detail_page_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    c = create_app("twb").test_client()
    body = c.get("/card/accountant").get_data(as_text=True)
    assert "Accountant" in body and "What's inside" in body and "Receipt capture" in body  # its OWN options
    assert "QuickBooks" in body                                                             # industry ref
    assert "checkbox" in body and "Save" in body                                            # wired toggles
    assert "Unknown card" in c.get("/card/nope").get_data(as_text=True)                     # bad key handled


def test_card_toggle_save(monkeypatch):
    from shared.database import _db
    from core.tenant_config import get_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    org = "test_card_tog"
    cdb.ensure_org(org, "T")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
    try:
        c = create_app(org).test_client()
        c.post("/card/accountant/save", data={"categories.accountant.invoices": "on"})   # toggle a planned option ON
        assert get_config(org)["categories"]["accountant"]["invoices"] is True
        c.post("/card/accountant/save", data={})                                          # all absent → off
        assert get_config(org)["categories"]["accountant"]["invoices"] is False
    finally:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))


def test_idea_options_wired_as_preview_toggles(monkeypatch):
    from shared.database import _db
    from core.tenant_config import get_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    org = "test_idea_tog"
    cdb.ensure_org(org, "T")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
    try:
        c = create_app(org).test_client()
        assert "idea — preview" in c.get("/card/stock").get_data(as_text=True)    # idea option marked honestly
        c.post("/card/stock/save", data={"categories.stock.valuation": "on"})     # an idea option is switchable
        assert get_config(org)["categories"]["stock"]["valuation"] is True
    finally:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))


def test_card_master_enable(monkeypatch):
    from shared.database import _db
    from core.tenant_config import get_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    org = "test_card_en"
    cdb.ensure_org(org, "T")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
    try:
        c = create_app(org).test_client()
        assert "This module is OFF" in c.get("/card/stock").get_data(as_text=True)    # off by default
        c.post("/card/stock/save", data={"categories.stock.enabled": "on"})
        assert get_config(org)["categories"]["stock"]["enabled"] is True              # enabled FROM the card
        assert "This module is ON" in c.get("/card/stock").get_data(as_text=True)
    finally:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))


def test_ai_power_tier_on_ai_card(monkeypatch):
    from shared.database import _db
    from core.tenant_config import get_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    org = "test_ai_tier"
    cdb.ensure_org(org, "T")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))
    try:
        c = create_app(org).test_client()
        assert "AI power tier" in c.get("/card/ai_assist").get_data(as_text=True)   # the Computer/AI Power selector
        c.post("/card/ai_assist/save", data={"ai_power": "mixed"})
        assert get_config(org)["ai_power"] == "mixed"                               # tier persists
    finally:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (org,))


def test_each_card_opens_its_own_inside(monkeypatch):
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    org = "test_card_inside"
    cdb.ensure_org(org, "T")
    set_config(org, {"package": "total"})                                                  # unlock all → /card links show
    body = create_app(org).test_client().get("/customer").get_data(as_text=True)
    for link in ("/card/accountant", "/card/stock", "/card/pos", "/card/hr_payroll", "/card/ai_assist"):
        assert link in body                                                                # distinct insides, not the generic editor
