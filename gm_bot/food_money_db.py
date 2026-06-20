"""Food-money gives — the per-report-period record behind the 'Day/Night staff food' list (who took
meal cash). Self-contained + INERT until the menu is wired (init runs on staging via tests; prod
migration at go-live). Idempotent: ONE give per (staff, business_day, period) — a re-tap is a no-op,
so a name can't be double-counted (S2: the UNIQUE + ON CONFLICT is the structural backstop).

This records food cash SEPARATELY — it never touches the drawer/report money count (owner: gives happen
pre/post a report, so auto-adding would miscount the current money). The report just SHOWS this list.
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
                    business_day DATE NOT NULL,
                    period       TEXT NOT NULL,            -- 'day' (mid ~4pm) | 'night' (final ~5am)
                    amount_cents INTEGER NOT NULL,
                    given_by     BIGINT,
                    given_at     TIMESTAMPTZ DEFAULT NOW(),
                    is_test      BOOLEAN DEFAULT FALSE,
                    UNIQUE (staff_id, business_day, period, is_test)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_food_gives_period "
                        "ON food_money_gives (business_day, period, is_test)")


def record_food_money_give(staff_id, staff_name, business_day, period, amount_cents,
                           given_by=None, is_test=False) -> bool:
    """Record one give. Idempotent: a second give for the same (staff, business_day, period) is a NO-OP
    (returns False) — the name 'disappears' from the menu so it can't be double-counted. True if newly
    recorded. The UNIQUE constraint is the structural backstop (flip/claim-first, not check-then-write)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO food_money_gives
                           (staff_id, staff_name, business_day, period, amount_cents, given_by, is_test)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (staff_id, business_day, period, is_test) DO NOTHING
                           RETURNING id""",
                        (staff_id, staff_name, business_day, period, amount_cents, given_by, is_test))
            return cur.fetchone() is not None


def food_money_given_ids(business_day, period, is_test=False) -> set:
    """staff_ids already given for this period — exclude them from the menu ('name disappears')."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_id FROM food_money_gives "
                        "WHERE business_day=%s AND period=%s AND is_test=%s",
                        (business_day, period, is_test))
            return {r["staff_id"] for r in cur.fetchall()}


def food_money_list(business_day, period, is_test=False) -> list:
    """[(staff_name, amount_cents)] for the 'Day/Night staff food' sheet, in give order."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT staff_name, amount_cents FROM food_money_gives "
                        "WHERE business_day=%s AND period=%s AND is_test=%s ORDER BY id",
                        (business_day, period, is_test))
            return [(r["staff_name"], r["amount_cents"]) for r in cur.fetchall()]
