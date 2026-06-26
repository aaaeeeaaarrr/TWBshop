"""core.payroll — a real, minimal payroll (the HR/payroll domain on the platform): per-staff monthly salary →
a pay run that snapshots a payslip per ACTIVE staffer. Org-scoped, channel-free, own tables (core_pay_runs /
core_payslips + core_staff.monthly_salary). NOT TWB's live payroll. No model calls. Tables via init_core_db."""
from shared.database import _db


def staff_with_salary(org_id) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id, COALESCE(call_name, name) nm, COALESCE(monthly_salary, 0) sal "
                        "FROM core_staff WHERE org_id=%s AND status='active' ORDER BY name", (org_id,))
            return [dict(r) for r in cur.fetchall()]


def set_salary(org_id, staff_id, amount) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_staff SET monthly_salary=%s WHERE org_id=%s AND staff_id=%s",
                        (amount or 0, org_id, staff_id))


def run_payroll(org_id, period) -> int:
    """Create a pay run for `period`: a payslip per ACTIVE staffer at their monthly salary — one transaction.
    Idempotent per period (PAYROLL-IDEMP): a re-run (double-click / POST retry) returns the EXISTING run and
    creates NO duplicate run or payslips — UNIQUE(org_id, period) is the claim."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id, COALESCE(call_name, name) nm, COALESCE(monthly_salary, 0) sal "
                        "FROM core_staff WHERE org_id=%s AND status='active' ORDER BY name", (org_id,))
            staff = cur.fetchall()
            total = sum(float(s["sal"]) for s in staff)
            cur.execute("INSERT INTO core_pay_runs (org_id, period, total) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id, period) DO NOTHING RETURNING run_id", (org_id, period, total))
            row = cur.fetchone()
            if row is None:                                  # this period already ran → return it, add nothing
                cur.execute("SELECT run_id FROM core_pay_runs WHERE org_id=%s AND period=%s", (org_id, period))
                return cur.fetchone()["run_id"]
            rid = row["run_id"]
            for s in staff:
                cur.execute("INSERT INTO core_payslips (org_id, run_id, staff_id, staff_name, gross) "
                            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (org_id, run_id, staff_id) DO NOTHING",
                            (org_id, rid, s["staff_id"], s["nm"], s["sal"]))
            return rid


def list_pay_runs(org_id, limit=20) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id, period, total, created_at FROM core_pay_runs "
                        "WHERE org_id=%s ORDER BY created_at DESC LIMIT %s", (org_id, int(limit)))
            return [dict(r) for r in cur.fetchall()]


def payslips(org_id, run_id) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_name, gross FROM core_payslips WHERE org_id=%s AND run_id=%s "
                        "ORDER BY staff_name", (org_id, run_id))
            return [dict(r) for r in cur.fetchall()]


def latest_run(org_id):
    runs = list_pay_runs(org_id, 1)
    return runs[0] if runs else None
