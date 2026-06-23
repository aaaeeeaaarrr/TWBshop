"""Wizard /shadow — read-only cut-over readiness (per-vertical shadow agreement). Seeds a few comparisons
and checks the page reports the agreement; nothing is changed."""
import json

import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app

cdb.init_core_db()
ORG = "test_shadow_pg"


def _seed():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))
            for kind, agree, live, new in [
                ("checkin", True, "{}", "{}"),
                ("checkin", False, json.dumps({"state": "on_time"}), json.dumps({"state": "late"})),
                ("checkin", True, "{}", "{}"),                            # 2 agree of 3 = 66%
            ]:
                cur.execute("INSERT INTO shadow_comparisons (org_id, kind, agree, live, new) "
                            "VALUES (%s,%s,%s,%s,%s)", (ORG, kind, agree, live, new))


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))


def test_shadow_agreement_page(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _seed()
    try:
        body = create_app(ORG).test_client().get("/shadow").get_data(as_text=True)
        assert "Shadow agreement" in body and "checkin" in body and "66%" in body   # agreement
        assert "Recent mismatches" in body and "on_time" in body                     # the diff detail
        assert "Data span" in body                                                   # how long it's gathered
        assert "Cut-over?" in body and "keep watching" in body                       # verdict (3<30 → watch)
    finally:
        _clean()
