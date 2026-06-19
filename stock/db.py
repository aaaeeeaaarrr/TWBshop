"""Stock-lane-owned schema + DB helpers — the count event log.

`stock_count_events` records every physical count (one row per item per day; a re-count the same day
upserts the figure). On-hand still lives in the shared `stock_movements` ledger — a count writes
BOTH: its event row here AND a reconciling movement there (the delta). This table answers
"when did we last count?" (the no-sheet escalation the order brain supports) and persists the counted
figure for the later 3-way reconciliation.

It stays in the stock lane (sole writer/reader today). When the accountant's reconciliation needs
counted figures (Phase D2), promote it to the shared seam via an integrator step — don't reach into
it cross-lane before then. Distinct from GM's legacy `stock_counts` (name-keyed), which is removed at
the GM cutover.

Conventions match accountant/db.py + shared/stock_shared.py: idempotent CREATE TABLE IF NOT EXISTS,
SERIAL PK, TIMESTAMPTZ NOW(), NUMERIC qty, is_test isolation. It FKs to the shared `acc_items`.
"""
from datetime import date as _date

from shared.database import _db


def init_stock_db() -> None:
    """Create the stock-lane schema (idempotent). Called from the worker startup."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_count_events (
                    id          SERIAL PRIMARY KEY,
                    item_id     INTEGER NOT NULL REFERENCES acc_items(id),
                    counted_qty NUMERIC NOT NULL,
                    unit        TEXT,
                    count_date  DATE NOT NULL,
                    source      TEXT,                  -- count | appsheet | sheet | manual
                    ref_id      INTEGER,               -- soft ref (AppSheet row / sheet msg id)
                    movement_id INTEGER,               -- the reconciling stock_movements row (NULL if no change)
                    note        TEXT,
                    reconciled  BOOLEAN DEFAULT FALSE,  -- is its effect in the stock_movements ledger yet?
                    at          TIMESTAMPTZ DEFAULT NOW(),
                    is_test     BOOLEAN DEFAULT FALSE,
                    UNIQUE (item_id, count_date, is_test)
                )
            """)
            cur.execute("ALTER TABLE stock_count_events ADD COLUMN IF NOT EXISTS reconciled BOOLEAN DEFAULT FALSE")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_count_date "
                        "ON stock_count_events (count_date, is_test)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_count_pending "
                        "ON stock_count_events (is_test) WHERE NOT reconciled")


def record_count_event(item_id, counted_qty, count_date, *, unit=None, source=None,
                       ref_id=None, movement_id=None, note=None, reconciled=False,
                       is_test=False) -> int:
    """Upsert the day's count for an item (the latest figure of the day wins). COALESCE keeps an
    existing field when the new value is None (a partial re-count never blanks data). `reconciled`
    is set by the writer: apply_count reconciles inline (True); a direct AppSheet write leaves it
    False so the worker's reconcile pass picks it up. A re-count carries the writer's reconciled
    state, so a fresh AppSheet figure (False) re-arms reconciliation. Returns the id."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO stock_count_events
                    (item_id, counted_qty, unit, count_date, source, ref_id, movement_id, note,
                     reconciled, is_test)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (item_id, count_date, is_test) DO UPDATE SET
                    counted_qty = EXCLUDED.counted_qty,
                    unit        = COALESCE(EXCLUDED.unit, stock_count_events.unit),
                    source      = COALESCE(EXCLUDED.source, stock_count_events.source),
                    ref_id      = COALESCE(EXCLUDED.ref_id, stock_count_events.ref_id),
                    movement_id = COALESCE(EXCLUDED.movement_id, stock_count_events.movement_id),
                    note        = COALESCE(EXCLUDED.note, stock_count_events.note),
                    reconciled  = EXCLUDED.reconciled,
                    at          = NOW()
                RETURNING id
            """, (item_id, counted_qty, unit, count_date, source, ref_id, movement_id, note,
                  reconciled, is_test))
            return cur.fetchone()["id"]


def last_count_date(is_test: bool = False):
    """The most recent count_date across all items (a `date`), or None if nothing's been counted."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT max(count_date) AS d FROM stock_count_events WHERE is_test=%s",
                        (is_test,))
            return cur.fetchone()["d"]


def days_since_last_count(today, is_test: bool = False):
    """Whole days since the most recent count (for the no-sheet escalation). None if never counted.
    `today`: a date or ISO string (Phnom-Penh calendar day)."""
    d = last_count_date(is_test=is_test)
    if d is None:
        return None
    if isinstance(today, str):
        today = _date.fromisoformat(today)
    return (today - d).days


def counts_on(count_date, is_test: bool = False) -> dict:
    """{item_id: counted_qty} for a given date (float qty)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT item_id, counted_qty FROM stock_count_events "
                        "WHERE count_date=%s AND is_test=%s", (count_date, is_test))
            return {r["item_id"]: float(r["counted_qty"]) for r in cur.fetchall()}


def pending_counts(is_test: bool = False) -> list[dict]:
    """Count events whose effect isn't in the ledger yet (reconciled=FALSE), oldest first — what the
    worker's reconcile pass consumes (counts written directly by AppSheet under the direct-bind path)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, item_id, counted_qty, count_date, unit, source, ref_id, note "
                        "FROM stock_count_events WHERE NOT reconciled AND is_test=%s "
                        "ORDER BY count_date, id", (is_test,))
            return [dict(r) for r in cur.fetchall()]


def mark_reconciled(event_id, movement_id=None) -> None:
    """Mark a count event reflected in the ledger, linking the reconciling movement (if any)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE stock_count_events SET reconciled=TRUE, "
                        "movement_id=COALESCE(%s, movement_id) WHERE id=%s", (movement_id, event_id))
