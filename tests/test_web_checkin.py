"""Web check-in channel — a per-staff token link → a browser page → core.check_in. Records to the platform
(core attendance_events), NEVER TWB's live attendance. Staging; org-scoped; cleaned."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core.onboarding_flow import add_staff_manual, ensure_checkin_token, staff_by_checkin_token

cdb.init_core_db()
ORG = "test_web"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM attendance_events WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM shifts WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))


def test_token_gen_and_lookup():
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        sid = add_staff_manual(ORG, "Sok", shift_windows=[{"start": "06:00", "end": "14:00"}])
        tok = ensure_checkin_token(ORG, sid)
        assert tok and ensure_checkin_token(ORG, sid) == tok        # idempotent
        s = staff_by_checkin_token(tok)
        assert s and s["staff_id"] == sid and s["org_id"] == ORG
        assert staff_by_checkin_token("bogus") is None
    finally:
        _clean()


def test_checkin_page_and_records(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        sid = add_staff_manual(ORG, "Sok", shift_windows=[{"start": "00:00", "end": "23:59"}])  # always binds
        tok = ensure_checkin_token(ORG, sid)
        c = create_app(ORG).test_client()
        assert "isn't valid" in c.get("/checkin/nope").get_data(as_text=True)        # bad token
        page = c.get("/checkin/%s" % tok).get_data(as_text=True)
        assert "Check in now" in page and "geolocation" in page                       # the page + JS
        body = c.post("/checkin/%s" % tok, data={"lat": "11.5", "lon": "104.9"}).get_data(as_text=True)
        assert "Checked in" in body or "already checked in" in body
        with _db() as cc:
            with cc.cursor() as cur:
                cur.execute("SELECT count(*) n FROM attendance_events WHERE org_id=%s AND type='checked_in'", (ORG,))
                assert cur.fetchone()["n"] >= 1                                        # recorded to the platform
    finally:
        _clean()


def test_staff_link_page(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        sid = add_staff_manual(ORG, "Sok")
        body = create_app(ORG).test_client().get("/staff/link/%d" % sid).get_data(as_text=True)
        assert "/checkin/" in body and "Sok" in body
    finally:
        _clean()
