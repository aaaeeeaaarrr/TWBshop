"""Wizard /shadow — read-only cut-over readiness (per-vertical shadow agreement). Seeds a few comparisons
and checks the page reports the agreement; nothing is changed."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app

cdb.init_core_db()
ORG = "test_shadow_pg"


def _seed(rows):
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))
            for kind, agree in rows:
                cur.execute("INSERT INTO shadow_comparisons (org_id, kind, agree) VALUES (%s,%s,%s)",
                            (ORG, kind, agree))


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))


def test_shadow_agreement_page(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _seed([("checkin", True), ("checkin", False), ("checkin", True)])     # 2 agree of 3 = 66%
    try:
        body = create_app(ORG).test_client().get("/shadow").get_data(as_text=True)
        assert "Shadow agreement" in body and "checkin" in body
        assert "66%" in body                                              # per-vertical + overall agreement
    finally:
        _clean()
