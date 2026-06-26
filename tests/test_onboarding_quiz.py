"""wizard.onboarding_quiz — the first-run 'packaging per client-type' questionnaire. Answers map to a starter
template + package + enabled domains; skippable any time; everything stays tweakable. Config-only, nothing live."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from wizard import onboarding_quiz as oq
from core.tenant_config import get_config

ORG = "test_quiz"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_apply_quiz_maps_to_package_and_domains():
    _clean()
    try:
        oq.apply_quiz(ORG, {"industry": "bakery", "size": "large", "pain": ["theft", "payroll"]})
        cfg = get_config(ORG)
        assert cfg["package"] == "total"                            # bakery template = ops, size 'large' bumps to total
        assert cfg["onboarding"]["industry_template"] == "bakery"   # the industry template was applied
        cats = cfg["categories"]
        assert cats["stock"]["enabled"] and cats["pos"]["enabled"]  # theft → stock + pos + accountant ON
        assert cats["hr_payroll"]["enabled"]                        # payroll → HR ON
        assert cfg["onboarding"]["quiz_done"] is True
    finally:
        _clean()


def test_partial_answers_skip_still_sets_up_sensibly():
    _clean()
    try:
        oq.apply_quiz(ORG, {"industry": "cafe"})                    # answered only Q1, skipped the rest
        cfg = get_config(ORG)
        assert cfg["package"] == "ops"                             # cafe template (no size → no bump)
        assert cfg["onboarding"]["quiz_done"] is True              # still finalized
    finally:
        _clean()


def test_welcome_flow_through_the_pages(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        c = create_app(ORG).test_client()
        assert "start setup" in c.get("/customer").get_data(as_text=True)          # first run → dashboard nudges
        assert "What kind of business" in c.get("/welcome").get_data(as_text=True)  # first question
        c.post("/welcome", data={"key": "industry", "v": "retail"})
        c.post("/welcome", data={"key": "size", "v": "small"})
        c.post("/welcome", data={"key": "pain", "v": ["cash", "stock"]})           # multi-select
        c.get("/welcome/skip")                                                      # skip the optional extras → finish
        cfg = get_config(ORG)
        assert cfg["onboarding"]["quiz_done"] is True
        assert cfg["onboarding"]["industry_template"] == "retail"
        assert cfg["categories"]["pos"]["enabled"] and cfg["categories"]["stock"]["enabled"]
        assert "start setup" not in c.get("/customer").get_data(as_text=True)       # done → no more nudge
    finally:
        _clean()
