"""core.whatif — read-only 'what would this config change do?' preview for the check-in verdict.
Proves: recomputing under a new grace reclassifies recorded check-ins; same config = no change; the page renders."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

import core.db as cdb
from shared.database import _db
from core.attendance import check_in
from core.whatif import verdict_whatif
import wizard.app as wa
from wizard.app import create_app

cdb.init_core_db()
ORG = "test_whatif"
TZ = "Asia/Phnom_Penh"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM attendance_events WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM shifts WHERE org_id=%s", (ORG,))


def _at(h, m):
    return datetime.combine(datetime.now(ZoneInfo(TZ)).date(), time(h, m), ZoneInfo(TZ))


def test_whatif_reclassifies():
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        r = check_in(ORG, 1, _at(8, 3), "08:00", "17:00", TZ, grace_min=5, early_bonus_min=5)
        assert r["state"] == "on_time"                       # 3 min late, grace 5 → on_time
        res = verdict_whatif(ORG, 2, 5)                       # tighten grace to 2 → it becomes late
        assert res["total"] >= 1 and res["changed"] >= 1
        assert res["by_transition"].get("on_time→late", 0) >= 1
        assert res["current"].get("on_time", 0) >= 1          # current breakdown reported
        assert verdict_whatif(ORG, 5, 5)["changed"] == 0     # same config → nothing reclassifies
    finally:
        _clean()


def test_whatif_page_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        check_in(ORG, 1, _at(8, 3), "08:00", "17:00", TZ, grace_min=5, early_bonus_min=5)
        body = create_app(ORG).test_client().get("/whatif?grace=2&early=5").get_data(as_text=True)
        assert "What-if" in body and "would change" in body and "Currently" in body
    finally:
        _clean()
