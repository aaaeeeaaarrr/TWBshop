"""Food-money gives — EVENT-DRIVEN (owner: a give counts toward the report that's done NEXT, not a clock
time). A give is recorded OPEN; when a daily report is stored (gm_daily_reports), close_food_period()
attaches every open give to it and the bot renders the 'Day/Night staff food' list. Idempotent: ONE open
give per staff (partial UNIQUE) so a re-tap can't double-count (S2 claim-first). Recorded SEPARATELY —
never touches the drawer/report money count (owner: pre/post-report gives must not miscount the money).
INERT until the menu + the report-close hook are wired (init runs on staging via tests; prod at go-live).
"""
from shared.database import _db


def init_food_money_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS food_money_gives (
                    id           SERIAL PRIMARY KEY,
                    staff_id     INTEGER NOT NULL,
                    staff_name   TEXT,
                    amount_cents INTEGER NOT NULL,
                    given_by     BIGINT,
                    given_at     TIMESTAMPTZ DEFAULT NOW(),
                    report_id    INTEGER,                  -- NULL = OPEN (not yet attached to a report)
                    business_day DATE,                     -- stamped at close (denormalised, supersede-proof)
                    report_kind  TEXT,                     -- 'mid' (day) | 'final' (night), at close
                    is_test      BOOLEAN DEFAULT FALSE
                )
            """)
            # additive forward-migration of an older (clock-based) shape — non-destructive, idempotent.
            cur.execute("ALTER TABLE food_money_gives ADD COLUMN IF NOT EXISTS report_id INTEGER")
            cur.execute("ALTER TABLE food_money_gives ADD COLUMN IF NOT EXISTS report_kind TEXT")
            cur.execute("""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='food_money_gives' AND column_name='period') THEN
                    ALTER TABLE food_money_gives ALTER COLUMN period DROP NOT NULL;
                    ALTER TABLE food_money_gives ALTER COLUMN business_day DROP NOT NULL;
                END IF;
            END $$;""")
            # one OPEN give per staff -> a re-tap is a no-op (claim-first); closed gives never block a new one
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_food_open_give "
                        "ON food_money_gives (staff_id, is_test) WHERE report_id IS NULL")


def food_arrived_staff(shift_dates, is_test=False) -> list:
    """ARRIVED staff for the menu = those with a CHECKED-IN attendance session (checked_in_at NOT NULL)
    on any of `shift_dates` (pass today + yesterday to cover an overnight shift). A scheduled-but-not-
    arrived staffer has no check-in → excluded (owner's rule). Joins staff_registry for the call-name +
    standard shift. Returns [{staff_id, name, work_start, work_end}], earliest check-in first. Read-only."""
    if not shift_dates:
        return []
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT a.staff_id,
                                  COALESCE(r.call_name, r.canonical_name) AS name,
                                  r.work_start, r.work_end
                           FROM attendance_sessions a JOIN staff_registry r ON r.id = a.staff_id
                           WHERE a.checked_in_at IS NOT NULL
                             AND a.shift_date = ANY(%s) AND a.is_test=%s
                           ORDER BY a.checked_in_at""",
                        (list(shift_dates), is_test))
            return [{"staff_id": x["staff_id"], "name": x["name"],
                     "work_start": x["work_start"], "work_end": x["work_end"]}
                    for x in cur.fetchall()]


def record_food_money_give(staff_id, staff_name, amount_cents, given_by=None, is_test=False) -> bool:
    """Record an OPEN give (counts toward the next report stored). Idempotent: a second give while still
    open is a NO-OP (returns False) -> the name 'disappears' from the menu. True if newly recorded."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO food_money_gives (staff_id, staff_name, amount_cents, given_by, is_test)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (staff_id, is_test) WHERE report_id IS NULL DO NOTHING
                           RETURNING id""",
                        (staff_id, staff_name, amount_cents, given_by, is_test))
            return cur.fetchone() is not None


def food_money_open_ids(is_test=False) -> set:
    """staff_ids with an OPEN give -> exclude them from the menu ('name disappears')."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id FROM food_money_gives WHERE report_id IS NULL AND is_test=%s",
                        (is_test,))
            return {r["staff_id"] for r in cur.fetchall()}


def food_money_open_list(is_test=False) -> list:
    """[(staff_name, amount_cents)] currently OPEN (a preview before the next report closes them)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_name, amount_cents FROM food_money_gives "
                        "WHERE report_id IS NULL AND is_test=%s ORDER BY id", (is_test,))
            return [(r["staff_name"], r["amount_cents"]) for r in cur.fetchall()]


def close_food_period(report_id, business_day, report_kind, is_test=False) -> list:
    """A daily report was stored -> attach every OPEN give to it (the owner's 'when the report is done')
    and return the closed list [(staff_name, amount_cents)] in give order. Idempotent: no open gives
    (already closed) -> returns whatever is already on that report. business_day+report_kind are stamped
    so the list survives report supersession."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE food_money_gives SET report_id=%s, business_day=%s, report_kind=%s
                           WHERE report_id IS NULL AND is_test=%s""",
                        (report_id, business_day, report_kind, is_test))
    return food_money_list_for_report(report_id)


def food_money_list_for_report(report_id) -> list:
    """[(staff_name, amount_cents)] attached to a stored report, in give order."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_name, amount_cents FROM food_money_gives "
                        "WHERE report_id=%s ORDER BY id", (report_id,))
            return [(r["staff_name"], r["amount_cents"]) for r in cur.fetchall()]
