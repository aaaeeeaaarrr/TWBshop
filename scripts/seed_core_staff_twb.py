"""scripts/seed_core_staff_twb.py — give the PLATFORM roster real NAMES + a real employee record.

WHY: the shadow records attendance into core's `attendance_events` keyed by the LIVE `staff_registry` id,
but core's own roster table `core_staff` was empty → the wizard reports/dashboard fell back to
'Staff #<id>'. This copies the live roster into core_staff so those views show real names + the full
universal employee record.

SCOPE / SAFETY (a staff-records write — treated as HIGH-RISK):
  • Writes ONLY to core_staff — a PLATFORM/shadow table read by the wizard + core modules. NO live bot
    reads core_staff (verified by grep), so this changes the owner-only wizard display ONLY. It does NOT
    touch staff_registry, payroll, attendance, or any bot. It is NOT a cut-over.
  • IDENTITY + EMPLOYMENT only: name · call_name · seniority · gender · phone · hours · expertise · day_off ·
    start/end dates · status. NO salary/bonus/pay (salary-privacy rule). The sensitive HR fields
    (national_id, passport, tax_id, …) are left blank for the owner to fill in the wizard.
  • staff_id is set EXPLICITLY = staff_registry.id so the reports' join resolves the name. The serial
    sequence is bumped past the seeded ids so a later add_staff_manual can't collide.
  • ACTIVE → core_staff.status='active'; everyone else (ex-staff) → 'removed' (so their NAME still resolves
    in historical reports, but they don't clutter the active roster page).
  • IDEMPOTENT: ON CONFLICT (staff_id) DO UPDATE — re-running refreshes, never duplicates.

REVERSIBLE:  DELETE FROM core_staff WHERE org_id='twb';
             SELECT setval('public.core_staff_staff_id_seq', 1, false);

RUN (prod):  cd /root/TWBshop && TWBSHOP_ENV=prod /root/venv/bin/python3 scripts/seed_core_staff_twb.py
"""
import json

from core.db import init_core_db
from shared.database import _db

ORG = "twb"


def _exp_list(raw):
    """staff_registry.expertise is a JSON-encoded string ('["bakery"]') → a real list."""
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw) if raw else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    init_core_db()                                   # ensure core_staff + the universal columns exist (additive)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) n FROM core_staff WHERE org_id=%s", (ORG,))
            before = cur.fetchone()["n"]
            cur.execute("SELECT id, canonical_name, call_name, is_senior, expertise, work_start, work_end, "
                        "day_off, status, gender, phone, joined_date, left_at "
                        "FROM staff_registry ORDER BY id")
            rows = cur.fetchall()
            for s in rows:
                windows = ([{"start": s["work_start"], "end": s["work_end"]}]
                           if s["work_start"] and s["work_end"] else [])
                status = "active" if s["status"] == "active" else "removed"
                end_date = (s["left_at"].date() if s["left_at"] else None)
                cur.execute(
                    """INSERT INTO core_staff (staff_id, org_id, name, call_name, is_senior, expertises,
                                               shift_windows, day_off, status, gender, phone, start_date, end_date)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (staff_id) DO UPDATE
                         SET org_id=EXCLUDED.org_id, name=EXCLUDED.name, call_name=EXCLUDED.call_name,
                             is_senior=EXCLUDED.is_senior, expertises=EXCLUDED.expertises,
                             shift_windows=EXCLUDED.shift_windows, day_off=EXCLUDED.day_off,
                             status=EXCLUDED.status, gender=EXCLUDED.gender, phone=EXCLUDED.phone,
                             start_date=EXCLUDED.start_date, end_date=EXCLUDED.end_date""",
                    (s["id"], ORG, s["canonical_name"], s["call_name"], bool(s["is_senior"]),
                     json.dumps(_exp_list(s["expertise"])), json.dumps(windows), s["day_off"], status,
                     s["gender"], s["phone"], s["joined_date"], end_date))
            cur.execute("SELECT setval('public.core_staff_staff_id_seq', (SELECT MAX(staff_id) FROM core_staff))")
            cur.execute("SELECT count(*) n FROM core_staff WHERE org_id=%s", (ORG,))
            cur.execute("SELECT count(*) a FROM core_staff WHERE org_id=%s AND status='active'", (ORG,))
            after_active = cur.fetchone()["a"]
            cur.execute("SELECT count(*) n FROM core_staff WHERE org_id=%s", (ORG,))
            after = cur.fetchone()["n"]
    print("core_staff (%s): before=%d  seeded=%d  after=%d (active=%d)"
          % (ORG, before, len(rows), after, after_active))


if __name__ == "__main__":
    main()
