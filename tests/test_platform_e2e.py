"""Platform end-to-end smoke — the pieces actually connect: org → staff → configure (audited) → web
check-in → staff history → what-if data → export. Catches integration regressions the unit tests miss."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core.onboarding_flow import add_staff_manual, ensure_checkin_token
from core.db import recent_config_audit
from core.whatif import verdict_whatif

cdb.init_core_db()
ORG = "test_e2e"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM attendance_events WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM shifts WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_config_audit WHERE org_id=%s", (ORG,))
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))


def test_platform_end_to_end(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "Demo Shop")
    _clean()
    try:
        c = create_app(ORG).test_client()
        sid = add_staff_manual(ORG, "Sok", shift_windows=[{"start": "00:00", "end": "23:59"}])  # 1. staff
        c.post("/customer/apply", data={"categories.attendance.verdict.grace_min": "9", "_scope": ""})  # 2. config
        assert any(r["path"].endswith("grace_min") for r in recent_config_audit(ORG, 10))            # 3. audited
        tok = ensure_checkin_token(ORG, sid)
        assert "Checked in" in c.post("/checkin/%s" % tok, data={}).get_data(as_text=True)             # 4. web check-in
        assert "recent check-ins" in c.get("/checkin/%s" % tok).get_data(as_text=True).lower()         # 5. history
        assert verdict_whatif(ORG, 2, 5)["total"] >= 1                                                  # 6. what-if sees it
        assert "grace_min" in c.get("/export").get_data(as_text=True)                                   # 7. export carries it
    finally:
        _clean()
