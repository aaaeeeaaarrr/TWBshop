"""Read-only proof that staging is a clean, faithful base for the AL build:
key tables exist, NO prod data leaked (every table empty except the seeded rules),
and staff_registry carries the columns the AL/payroll code reads."""
import os

os.environ.setdefault("TWBSHOP_ENV", "staging")  # this tool verifies STAGING, only ever
from shared.database import raw_connect

conn = raw_connect()
with conn.cursor() as cur:
    cur.execute("SELECT current_database()")
    print("connected to:", cur.fetchone()[0])
    key = ["staff_registry", "al_requests", "al_approvals", "special_leaves",
           "payback_debts", "shift_changes", "points_events", "points_rules",
           "attendance_sessions", "gm_flow_state"]
    print("\n-- key AL-build tables: row counts (expect 0 except points_rules) --")
    for t in key:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(f"  {t:22} {cur.fetchone()[0]}")
    print("\n-- staff_registry columns the AL/payroll code needs --")
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='staff_registry' "
        "AND column_name IN ('al_left','salary_usd','bonus_usd','first_pay_usd','second_pay_usd') "
        "ORDER BY 1"
    )
    print("  present:", [r[0] for r in cur.fetchall()])
conn.close()
