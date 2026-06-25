"""core.reports + /reports — the first frontier capability built out: attendance trends over the platform's
own data (read-only)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core.attendance import check_in
from core.reports import attendance_report, staff_attendance_report

cdb.init_core_db()
ORG = "test_reports"
TZ = "Asia/Phnom_Penh"


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM attendance_events WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM shifts WHERE org_id=%s", (ORG,))


def test_attendance_report_aggregates():
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        now = datetime.now(ZoneInfo(TZ))
        check_in(ORG, 1, now, "00:00", "23:59", TZ)
        check_in(ORG, 2, now, "00:00", "23:59", TZ)
        rep = attendance_report(ORG, 14)
        assert rep["total"] == 2 and rep["daily"][-1]["total"] == 2     # both today
        assert 0 <= rep["on_time_rate"] <= 100
    finally:
        _clean()


def test_staff_attendance_report():
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        now = datetime.now(ZoneInfo(TZ))
        check_in(ORG, 1, now, "00:00", "23:59", TZ)
        check_in(ORG, 2, now, "00:00", "23:59", TZ)
        rep = staff_attendance_report(ORG, 14)
        assert len(rep) == 2                                            # one row per staff
        assert all(s["name"] and s["total"] == 1 for s in rep)         # name (fallback) + count
        assert all(0 <= s["on_time_rate"] <= 100 for s in rep)
    finally:
        _clean()


def test_reports_page_renders(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        check_in(ORG, 1, datetime.now(ZoneInfo(TZ)), "00:00", "23:59", TZ)
        body = create_app(ORG).test_client().get("/reports?days=30").get_data(as_text=True)
        assert "Reports" in body and "Daily trend" in body and "Punctuality by staff" in body
        assert "Period:" in body and "30d" in body                     # selectable period
        assert "Export CSV" in body                                    # export link
    finally:
        _clean()


def test_reports_csv_export(monkeypatch):
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    cdb.ensure_org(ORG, "T")
    _clean()
    try:
        check_in(ORG, 1, datetime.now(ZoneInfo(TZ)), "00:00", "23:59", TZ)
        r = create_app(ORG).test_client().get("/reports/export?days=14")
        assert r.headers["Content-Type"].startswith("text/csv")
        assert "attachment" in r.headers["Content-Disposition"]
        body = r.get_data(as_text=True)
        assert "section,key,check_ins,late,on_time_pct" in body         # header row
        assert "daily," in body and "staff," in body                    # both sections exported
    finally:
        _clean()
