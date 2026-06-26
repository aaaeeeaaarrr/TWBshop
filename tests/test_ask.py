"""core.ask — 'Ask your business': the computer-tier NL router answers from the tenant's real data (no API), and
an unmatched question stays OFF the model unless AI-power is on. Fin-inspired, lean."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import ask

cdb.init_core_db()
ORG = "test_ask"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_computer_tier_routing():
    _clean()
    cases = [
        ("how many late this week?", "attendance"),
        ("what were sales last month?", "sales"),
        ("anything low on stock or to reorder?", "par"),
        ("any shrinkage?", "variance"),
        ("what needs attention?", "attention"),
        ("how much did we spend?", "expenses"),
        ("last pay run?", "payroll"),
        ("who is working today?", "attendance today"),
        ("what's the stock value?", "stock"),
    ]
    for q, src in cases:
        r = ask.ask(ORG, q)
        assert r["tier"] == "computer", "%s → %r" % (q, r)
        assert src in r["source"], "%s → source %r (want %r)" % (q, r["source"], src)


def test_unmatched_stays_off_the_model():
    _clean()
    r = ask.ask(ORG, "what is the meaning of life")              # ai_power default 'computer' → NO API call
    assert r["tier"] == "none" and "AI power" in r["answer"]


def test_ask_page_renders_an_answer(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    body = create_app(ORG).test_client().get("/ask?q=how+many+late+this+week").get_data(as_text=True)
    assert "Ask your business" in body and "on-time" in body     # the real answer rendered
