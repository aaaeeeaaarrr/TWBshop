"""Shared stock tables — the accountant <-> stock-lane seam (design §E7 / §E11).

These live in the SHARED zone because BOTH lanes touch them, but NEITHER lane edits the other's
code — the seam is DATA, not code:
  - the accountant writes a `+received` movement when a receipt confirms (a one-line insert);
  - the stock lane writes `-used / -counted` movements and reads on-hand = SUM(qty_delta).
Each lane imports these helpers from `shared.` (importing shared is allowed; importing another
lane is not). Schema is additive + idempotent (CREATE TABLE IF NOT EXISTS), same conventions as
`accountant/db.py` (acc_ prefix, SERIAL PK, TIMESTAMPTZ NOW(), is_test, NUMERIC qty). These tables
hold QUANTITIES (kg / pieces), not money — money stays in the accountant's cents columns.

State-integrity (STATE_INTEGRITY_LAWS S5): `stock_movements` is an APPEND-ONLY ledger with ONE
resolver for on-hand (= SUM of qty_delta per item). Every writer (receipt goods-in, AppSheet count,
POS, waste, adjust) appends a row; nobody mutates a running total. `is_test` movements never affect
real on-hand (the `on_hand` resolver is is_test-scoped) — same isolation the rest of the system uses.

NOTE (catalog-link alias, deferred): mapping a supplier's written item name -> a catalog item_id is
a later, coordinated step — the accountant already owns `acc_item_aliases` (orig_name -> english_name
translation). Unifying that with an `item_id` link is decided WITH the accountant lane (P4+), not here.
"""
from shared.database import _db


def init_stock_shared_db() -> None:
    """Create the shared stock schema (idempotent). Safe to call from any service startup (the stock
    service and/or the accountant bot). Applied to whichever DB the TWBSHOP_ENV switch selects."""
    with _db() as conn:
        with conn.cursor() as cur:
            # ── acc_items — the item catalog (seeded from the owner's ~143-item reorder sheet) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_items (
                    id           SERIAL PRIMARY KEY,
                    name         TEXT NOT NULL,        -- canonical English name
                    category     TEXT,
                    unit         TEXT,                 -- canonical counting unit (kg / piece / box ...)
                    min_qty      NUMERIC,              -- reorder trigger
                    reorder_qty  NUMERIC,              -- order back up to this
                    active       BOOLEAN DEFAULT TRUE,
                    created_at   TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_items_name ON acc_items (lower(name))")

            # ── stock_movements — the append-only on-hand ledger (on-hand = SUM(qty_delta)) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stock_movements (
                    id         SERIAL PRIMARY KEY,
                    item_id    INTEGER NOT NULL REFERENCES acc_items(id),
                    qty_delta  NUMERIC NOT NULL,       -- +received / -used / signed adjust
                    unit       TEXT,                   -- the unit this movement was recorded in
                    reason     TEXT NOT NULL,          -- received | used | counted | waste | adjust
                    source     TEXT,                   -- receipt | count | pos | manual
                    ref_id     INTEGER,                -- receipt id / count id / etc. (soft ref)
                    note       TEXT,
                    at         TIMESTAMPTZ DEFAULT NOW(),
                    is_test    BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_mov_item ON stock_movements (item_id, is_test)")


# ── catalog helpers (both lanes) ──

def upsert_item(name, category=None, unit=None, min_qty=None, reorder_qty=None) -> int:
    """Add or update a catalog item, keyed on the canonical name (case-insensitive). Returns the id.
    COALESCE keeps an existing field when the new value is None (a partial update never blanks data)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO acc_items (name, category, unit, min_qty, reorder_qty)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (lower(name)) DO UPDATE SET
                    category    = COALESCE(EXCLUDED.category, acc_items.category),
                    unit        = COALESCE(EXCLUDED.unit, acc_items.unit),
                    min_qty     = COALESCE(EXCLUDED.min_qty, acc_items.min_qty),
                    reorder_qty = COALESCE(EXCLUDED.reorder_qty, acc_items.reorder_qty),
                    active      = TRUE
                RETURNING id
            """, ((name or "").strip(), category, unit, min_qty, reorder_qty))
            return cur.fetchone()["id"]


def get_item(item_id) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_items WHERE id=%s", (item_id,))
            return cur.fetchone()


def get_item_by_name(name) -> dict | None:
    if not name:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_items WHERE lower(name)=lower(%s)", ((name or "").strip(),))
            return cur.fetchone()


def list_items(active_only: bool = True) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_items %s ORDER BY category NULLS LAST, name"
                        % ("WHERE active" if active_only else ""))
            return list(cur.fetchall())


# ── movement ledger (both lanes; on-hand has ONE resolver) ──

def add_movement(item_id, qty_delta, reason, unit=None, source=None, ref_id=None,
                 note=None, is_test=False) -> int:
    """Append a stock movement (S5: append-only — never mutate a running total). Returns the row id."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO stock_movements
                (item_id, qty_delta, unit, reason, source, ref_id, note, is_test)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (item_id, qty_delta, unit, reason, source, ref_id, note, is_test))
            return cur.fetchone()["id"]


def on_hand(item_id, is_test: bool = False) -> float:
    """The ONE resolver for current stock: SUM(qty_delta) for this item (is_test-scoped). 0.0 if none."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(qty_delta),0) AS oh FROM stock_movements "
                        "WHERE item_id=%s AND is_test=%s", (item_id, is_test))
            return float(cur.fetchone()["oh"])


def on_hand_all(is_test: bool = False) -> dict:
    """on-hand for every item that has movements: {item_id: qty} (is_test-scoped)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT item_id, COALESCE(SUM(qty_delta),0) AS oh FROM stock_movements "
                        "WHERE is_test=%s GROUP BY item_id", (is_test,))
            return {r["item_id"]: float(r["oh"]) for r in cur.fetchall()}
