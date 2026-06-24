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
    assert "built" in body and "QuickBooks" in body                                        # status + industry ref
    assert "Unknown card" in c.get("/card/nope").get_data(as_text=True)                     # bad key handled


def test_each_card_opens_its_own_inside(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    body = create_app("twb").test_client().get("/customer").get_data(as_text=True)
    for link in ("/card/accountant", "/card/stock", "/card/pos", "/card/hr_payroll", "/card/ai_assist"):
        assert link in body                                                                # distinct insides, not the generic editor
