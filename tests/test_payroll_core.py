"""core.payroll — salary → pay run (a payslip per active staffer) + /payroll + the payroll Reports section.
Shadow-style (own tables)."""
import core.db as cdb
from shared.database import _db
import wizard.app as wa
from wizard.app import create_app
from core import payroll

cdb.init_core_db()
ORG = "test_payroll"


def _clean():
    cdb.ensure_org(ORG, "T")
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE orgs SET config='{}' WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_payslips WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_pay_runs WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_staff WHERE org_id=%s", (ORG,))


def _add_staff(name):
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO core_staff (org_id, name, status) VALUES (%s,%s,'active') RETURNING staff_id",
                        (ORG, name))
            return cur.fetchone()["staff_id"]


def test_pay_run_from_salaries():
    _clean()
    try:
        a, b = _add_staff("Alice"), _add_staff("Bob")
        payroll.set_salary(ORG, a, 300)
        payroll.set_salary(ORG, b, 250)
        rid = payroll.run_payroll(ORG, "2026-06")
        slips = payroll.payslips(ORG, rid)
        assert len(slips) == 2 and sum(float(s["gross"]) for s in slips) == 550.0     # payslip per staffer
        assert float(payroll.latest_run(ORG)["total"]) == 550.0
    finally:
        _clean()


def test_payroll_page_and_reports(monkeypatch):
    from core.tenant_config import set_config
    monkeypatch.setattr(wa, "auth_enabled", lambda: False)
    _clean()
    try:
        c = create_app(ORG).test_client()
        assert "Turn it on" in c.get("/payroll").get_data(as_text=True)               # off → enable prompt
        set_config(ORG, {"categories": {"hr_payroll": {"enabled": True}}})
        sid = _add_staff("Carol")
        c.post("/payroll/salary", data={"staff_id": str(sid), "amount": "400"})
        c.post("/payroll/run", data={"period": "2026-06"})
        assert "Carol" in c.get("/payroll").get_data(as_text=True)                    # ran via the page
        assert float(payroll.latest_run(ORG)["total"]) == 400.0
        assert "💼 Payroll" in c.get("/reports").get_data(as_text=True)               # multi-domain reports → 5
    finally:
        _clean()


def test_rerun_payroll_is_idempotent():
    """PAYROLL-IDEMP (s55): re-running the SAME period returns the existing run and creates NO duplicate run
    or payslips (UNIQUE(org,period) + UNIQUE(run,staff))."""
    _clean()
    try:
        a, b = _add_staff("Alice"), _add_staff("Bob")
        payroll.set_salary(ORG, a, 300)
        payroll.set_salary(ORG, b, 250)
        r1 = payroll.run_payroll(ORG, "2026-06")
        r2 = payroll.run_payroll(ORG, "2026-06")                                       # re-run (double-click)
        assert r1 == r2                                                                # same run, not a 2nd
        assert len(payroll.payslips(ORG, r1)) == 2                                     # still one slip per staffer
        assert len(payroll.list_pay_runs(ORG)) == 1                                    # one run total, not two
    finally:
        _clean()
