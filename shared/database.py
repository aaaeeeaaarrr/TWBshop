"""PostgreSQL database — all tables and queries."""

import logging
from contextlib import contextmanager
from datetime import datetime

import psycopg2
import psycopg2.extras
import psycopg2.pool

import config

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(1, 10, config.DATABASE_URL)
    return _pool


@contextmanager
def _db():
    pool = _get_pool()
    conn = pool.getconn()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id            SERIAL PRIMARY KEY,
                    user_id       BIGINT  NOT NULL,
                    customer_name TEXT    NOT NULL DEFAULT 'Unknown',
                    item          TEXT    NOT NULL,
                    quantity      INTEGER NOT NULL DEFAULT 1,
                    status        TEXT    NOT NULL DEFAULT 'confirmed',
                    created_at    TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS photo_submissions (
                    id           SERIAL PRIMARY KEY,
                    user_id      BIGINT  NOT NULL,
                    staff_name   TEXT    NOT NULL,
                    photo_type   TEXT    NOT NULL,
                    file_path    TEXT    NOT NULL,
                    submitted_at TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_customers (
                    group_chat_id   BIGINT PRIMARY KEY,
                    business_name   TEXT   NOT NULL,
                    delivery_method TEXT,
                    delivery_time   TEXT,
                    location        TEXT,
                    menu_message_id BIGINT,
                    updated_at      TEXT   NOT NULL
                )
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS menu_message_id BIGINT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS menu_qty_pending TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS bot_pending TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS bot_state TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS bot_last_confirmation BIGINT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS bot_editing_session TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS bot_cart TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS location_lat DOUBLE PRECISION
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS location_lng DOUBLE PRECISION
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS delivery_cost NUMERIC(8,2)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_orders (
                    id             SERIAL  PRIMARY KEY,
                    group_chat_id  BIGINT  NOT NULL,
                    business_name  TEXT    NOT NULL,
                    item           TEXT    NOT NULL,
                    quantity       INTEGER NOT NULL DEFAULT 1,
                    grams          INTEGER,
                    notes          TEXT,
                    delivery_date  TEXT    NOT NULL DEFAULT '',
                    status         TEXT    NOT NULL DEFAULT 'confirmed',
                    payment_status TEXT    NOT NULL DEFAULT 'unpaid',
                    created_at     TEXT    NOT NULL
                )
            """)
            cur.execute("""
                ALTER TABLE b2b_orders
                ADD COLUMN IF NOT EXISTS batch_id TEXT NOT NULL DEFAULT ''
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_cake_orders (
                    id            SERIAL  PRIMARY KEY,
                    group_chat_id BIGINT  NOT NULL,
                    business_name TEXT    NOT NULL,
                    item          TEXT    NOT NULL,
                    cake_category TEXT    NOT NULL,
                    order_type    TEXT    NOT NULL,
                    quantity      INTEGER NOT NULL DEFAULT 1,
                    slices        INTEGER,
                    delivery_date TEXT    NOT NULL,
                    status        TEXT    NOT NULL DEFAULT 'confirmed',
                    payment_status TEXT   NOT NULL DEFAULT 'unpaid',
                    created_at    TEXT    NOT NULL
                )
            """)
            cur.execute("""
                ALTER TABLE b2b_cake_orders
                ADD COLUMN IF NOT EXISTS batch_id TEXT NOT NULL DEFAULT ''
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_payments (
                    id               SERIAL  PRIMARY KEY,
                    group_chat_id    BIGINT  NOT NULL,
                    business_name    TEXT    NOT NULL,
                    amount           REAL    NOT NULL DEFAULT 0,
                    screenshot_path  TEXT,
                    group_message_id BIGINT,
                    status           TEXT    NOT NULL DEFAULT 'pending',
                    applied_at       TEXT,
                    created_at       TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_recurring_orders (
                    id              SERIAL  PRIMARY KEY,
                    group_chat_id   BIGINT  NOT NULL,
                    business_name   TEXT    NOT NULL,
                    items_json      TEXT    NOT NULL,
                    days_of_week    TEXT    NOT NULL,
                    delivery_time   TEXT    NOT NULL,
                    delivery_method TEXT    NOT NULL,
                    status          TEXT    NOT NULL DEFAULT 'active',
                    created_at      TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_recurring_confirmations (
                    id                 SERIAL  PRIMARY KEY,
                    recurring_order_id INTEGER NOT NULL REFERENCES b2b_recurring_orders(id),
                    fulfillment_date   TEXT    NOT NULL,
                    status             TEXT    NOT NULL DEFAULT 'pending',
                    reminder_sent      INTEGER NOT NULL DEFAULT 0,
                    created_at         TEXT    NOT NULL,
                    UNIQUE(recurring_order_id, fulfillment_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_dispatch_reminders (
                    id                SERIAL  PRIMARY KEY,
                    group_chat_id     BIGINT  NOT NULL,
                    fulfillment_date  TEXT    NOT NULL,
                    fulfillment_time  TEXT    NOT NULL,
                    delivery_method   TEXT    NOT NULL,
                    status            TEXT    NOT NULL DEFAULT 'pending',
                    owner_message_id  INTEGER,
                    snooze_until      TEXT,
                    escalated         BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at        TEXT    NOT NULL,
                    UNIQUE(group_chat_id, fulfillment_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_payment_accounts (
                    id     SERIAL PRIMARY KEY,
                    type   TEXT   NOT NULL,
                    value  TEXT   NOT NULL UNIQUE,
                    active BOOLEAN NOT NULL DEFAULT TRUE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_pending_verifications (
                    id               SERIAL  PRIMARY KEY,
                    group_chat_id    BIGINT  NOT NULL,
                    photo_msg_id     INTEGER NOT NULL,
                    group_ack_msg_id INTEGER,
                    owner_msg_id     INTEGER,
                    amount           FLOAT   NOT NULL DEFAULT 0,
                    business_name    TEXT,
                    file_path        TEXT,
                    status           TEXT    NOT NULL DEFAULT 'pending',
                    created_at       TEXT    NOT NULL,
                    last_nudge_at    TEXT
                )
            """)
            cur.execute("""
                ALTER TABLE b2b_pending_verifications
                ADD COLUMN IF NOT EXISTS tg_file_id TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_pending_verifications
                ADD COLUMN IF NOT EXISTS tg_file_unique_id TEXT
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_wrong_account_alerts (
                    id            SERIAL  PRIMARY KEY,
                    owner_msg_id  INTEGER,
                    business_name TEXT,
                    amount        FLOAT   NOT NULL DEFAULT 0,
                    wrong_detail  TEXT,
                    status        TEXT    NOT NULL DEFAULT 'pending',
                    created_at    TEXT    NOT NULL,
                    last_nudge_at TEXT
                )
            """)
            cur.execute("""
                ALTER TABLE b2b_wrong_account_alerts
                ADD COLUMN IF NOT EXISTS tg_file_id TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_payments
                ADD COLUMN IF NOT EXISTS tg_file_unique_id TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_payments
                ADD COLUMN IF NOT EXISTS method TEXT DEFAULT 'photo'
            """)
            cur.execute("""
                ALTER TABLE b2b_payments
                ADD COLUMN IF NOT EXISTS covered_dates TEXT
            """)
            cur.execute("""
                ALTER TABLE b2b_customers
                ADD COLUMN IF NOT EXISTS credit NUMERIC(8,2) DEFAULT 0
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS b2b_markpaid_requests (
                    id            SERIAL  PRIMARY KEY,
                    group_chat_id BIGINT  NOT NULL,
                    business_name TEXT    NOT NULL,
                    amount        NUMERIC(8,2),
                    method        TEXT,
                    staff_user_id BIGINT  NOT NULL,
                    staff_msg_id  BIGINT,
                    owner_msg_id  BIGINT,
                    status        TEXT    NOT NULL DEFAULT 'draft',
                    covered_dates TEXT,
                    created_at    TEXT    NOT NULL
                )
            """)
    logger.info("Database ready")


# ─── Ops Intelligence ─────────────────────────────────────────────────────────

def init_ops_db() -> None:
    """Create ops_messages table. Called from run_listener.py on startup."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ops_messages (
                    id          BIGSERIAL PRIMARY KEY,
                    chat_id     BIGINT NOT NULL,
                    message_id  BIGINT NOT NULL,
                    chat_title  TEXT,
                    sender_id   BIGINT,
                    sender_name TEXT,
                    text        TEXT,
                    media_type  TEXT,
                    sent_at     TEXT,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(chat_id, message_id)
                )
            """)
    logger.info("Ops DB ready")


def save_ops_message(
    chat_id: int,
    message_id: int,
    chat_title: str | None,
    sender_id: int | None,
    sender_name: str | None,
    text: str,
    media_type: str | None,
    sent_at: str | None,
) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ops_messages
                    (chat_id, message_id, chat_title, sender_id, sender_name,
                     text, media_type, sent_at, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chat_id, message_id) DO NOTHING
            """, (chat_id, message_id, chat_title, sender_id, sender_name,
                  text, media_type, sent_at, now))


def dedup_keeper(ids: list[int], mids: list[int], prefer: set) -> int:
    """Pure: choose which row to KEEP from a duplicate group. Prefer a row whose
    message_id is in `prefer` (e.g. referenced by gm_daily_reports), else the
    smallest id. `ids` and `mids` are aligned (row id, message_id)."""
    for rid, mid in zip(ids, mids):
        if mid in prefer:
            return rid
    return min(ids)


def dedupe_ops_messages(chat_id: int, prefer_message_ids=None,
                        dry_run: bool = True) -> dict:
    """Remove duplicate ops_messages rows for one chat where the same content was
    captured twice (same sender_id + sent_at + text, different message_id — e.g. the
    Telethon listener and the Bot API both logging the same message).

    Keeper per duplicate group: a row whose message_id is in `prefer_message_ids`
    (so referenced rows — e.g. gm_daily_reports.source_message_id — are never
    orphaned), otherwise the row with the smallest id. Only text rows are touched.

    dry_run=True reports what WOULD be deleted without changing anything.
    Returns {groups, deleted, deleted_ids, kept_ids}.
    """
    prefer = set(prefer_message_ids or [])
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT array_agg(id ORDER BY id) AS ids,
                       array_agg(message_id ORDER BY id) AS mids
                FROM ops_messages
                WHERE chat_id = %s AND text IS NOT NULL
                GROUP BY sender_id, sent_at, text
                HAVING count(*) > 1
            """, (chat_id,))
            groups = cur.fetchall()

            to_delete, kept = [], []
            for g in groups:
                keeper = dedup_keeper(g["ids"], g["mids"], prefer)
                kept.append(keeper)
                to_delete.extend(rid for rid in g["ids"] if rid != keeper)

            if to_delete and not dry_run:
                cur.execute("DELETE FROM ops_messages WHERE id = ANY(%s)", (to_delete,))

    return {"groups": len(groups), "deleted": len(to_delete),
            "deleted_ids": to_delete, "kept_ids": kept}


def gm_daily_report_message_ids(chat_id: int) -> list[int]:
    """All source_message_ids referenced by stored daily reports for a chat —
    pass to dedupe_ops_messages so those rows are preferred as keepers."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT source_message_id FROM gm_daily_reports
                WHERE source_chat_id = %s AND source_message_id IS NOT NULL
            """, (chat_id,))
            return [r["source_message_id"] for r in cur.fetchall()]


# ─── Retail orders ────────────────────────────────────────────────────────────

def save_order(user_id: int, customer_name: str, items: list[tuple[str, int]]) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO orders (user_id, customer_name, item, quantity, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(user_id, customer_name, item, qty, now) for item, qty in items],
            )
    logger.info("Saved order for %s (id=%s): %s", customer_name, user_id, items)


def get_daily_totals(date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, SUM(quantity) AS total
                FROM orders
                WHERE LEFT(created_at, 10) = %s AND status = 'confirmed'
                GROUP BY item
                ORDER BY item
            """, (date,))
            return cur.fetchall()


def get_orders_by_user(date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, customer_name, item, quantity
                FROM orders
                WHERE LEFT(created_at, 10) = %s AND status = 'confirmed'
                ORDER BY customer_name, item
            """, (date,))
            return cur.fetchall()


def save_photo_submission(user_id: int, staff_name: str, photo_type: str, file_path: str) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO photo_submissions (user_id, staff_name, photo_type, file_path, submitted_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, staff_name, photo_type, file_path, now),
            )
    logger.info("Photo submission saved: %s by %s (%s)", photo_type, staff_name, user_id)


def get_submissions_today(photo_type: str, date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, staff_name, file_path, submitted_at
                FROM photo_submissions
                WHERE photo_type = %s AND LEFT(submitted_at, 10) = %s
            """, (photo_type, date))
            return cur.fetchall()


# ─── B2B customers ────────────────────────────────────────────────────────────

def upsert_b2b_customer(
    group_chat_id: int,
    business_name: str,
    delivery_method: str | None = None,
    delivery_time: str | None = None,
    location: str | None = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers
                    (group_chat_id, business_name, delivery_method, delivery_time, location, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    business_name   = EXCLUDED.business_name,
                    delivery_method = COALESCE(EXCLUDED.delivery_method, b2b_customers.delivery_method),
                    delivery_time   = COALESCE(EXCLUDED.delivery_time,   b2b_customers.delivery_time),
                    location        = COALESCE(EXCLUDED.location,        b2b_customers.location),
                    updated_at      = EXCLUDED.updated_at
            """, (group_chat_id, business_name, delivery_method, delivery_time, location, now))


def update_b2b_location(
    group_chat_id: int,
    lat: float,
    lng: float,
    delivery_cost: float,
) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE b2b_customers
                SET location_lat = %s, location_lng = %s, delivery_cost = %s, updated_at = %s
                WHERE group_chat_id = %s
            """, (lat, lng, delivery_cost, now, group_chat_id))


def get_b2b_customer(group_chat_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,)
            )
            return cur.fetchone()


def get_menu_message_id(group_chat_id: int) -> int | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT menu_message_id FROM b2b_customers WHERE group_chat_id = %s",
                (group_chat_id,),
            )
            row = cur.fetchone()
            return row["menu_message_id"] if row else None


def set_menu_message_id(group_chat_id: int, message_id: int | None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, menu_message_id, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    menu_message_id = EXCLUDED.menu_message_id,
                    updated_at      = EXCLUDED.updated_at
            """, (group_chat_id, message_id, datetime.utcnow().isoformat()))


def get_qty_pending(group_chat_id: int) -> dict | None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT menu_qty_pending FROM b2b_customers WHERE group_chat_id = %s",
                (group_chat_id,),
            )
            row = cur.fetchone()
            if row and row["menu_qty_pending"]:
                return json.loads(row["menu_qty_pending"])
            return None


def set_qty_pending(group_chat_id: int, state: dict | None) -> None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, menu_qty_pending, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    menu_qty_pending = EXCLUDED.menu_qty_pending,
                    updated_at       = EXCLUDED.updated_at
            """, (group_chat_id, json.dumps(state) if state else None, datetime.utcnow().isoformat()))


def get_pending_order(group_chat_id: int) -> dict | None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT bot_pending FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,))
            row = cur.fetchone()
            return json.loads(row["bot_pending"]) if row and row["bot_pending"] else None

def set_pending_order(group_chat_id: int, state: dict | None) -> None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, bot_pending, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    bot_pending = EXCLUDED.bot_pending, updated_at = EXCLUDED.updated_at
            """, (group_chat_id, json.dumps(state) if state else None, datetime.utcnow().isoformat()))

def get_order_state(group_chat_id: int) -> dict | None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT bot_state FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,))
            row = cur.fetchone()
            return json.loads(row["bot_state"]) if row and row["bot_state"] else None

def set_order_state(group_chat_id: int, state: dict | None) -> None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, bot_state, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    bot_state = EXCLUDED.bot_state, updated_at = EXCLUDED.updated_at
            """, (group_chat_id, json.dumps(state) if state else None, datetime.utcnow().isoformat()))

def get_last_confirmation_msg(group_chat_id: int) -> int | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT bot_last_confirmation FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,))
            row = cur.fetchone()
            return row["bot_last_confirmation"] if row else None

def set_last_confirmation_msg(group_chat_id: int, msg_id: int | None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, bot_last_confirmation, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    bot_last_confirmation = EXCLUDED.bot_last_confirmation, updated_at = EXCLUDED.updated_at
            """, (group_chat_id, msg_id, datetime.utcnow().isoformat()))

def get_editing_session(group_chat_id: int) -> str | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT bot_editing_session FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,))
            row = cur.fetchone()
            return row["bot_editing_session"] if row else None

def set_editing_session(group_chat_id: int, session_key: str | None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, bot_editing_session, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    bot_editing_session = EXCLUDED.bot_editing_session, updated_at = EXCLUDED.updated_at
            """, (group_chat_id, session_key, datetime.utcnow().isoformat()))


def get_cart_state(group_chat_id: int) -> dict | None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT bot_cart FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,))
            row = cur.fetchone()
            return json.loads(row["bot_cart"]) if row and row["bot_cart"] else None

def set_cart_state(group_chat_id: int, state: dict | None) -> None:
    import json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_customers (group_chat_id, business_name, bot_cart, updated_at)
                VALUES (%s, '', %s, %s)
                ON CONFLICT (group_chat_id) DO UPDATE SET
                    bot_cart = EXCLUDED.bot_cart, updated_at = EXCLUDED.updated_at
            """, (group_chat_id, json.dumps(state) if state else None, datetime.utcnow().isoformat()))


def get_bot_meta(key: str) -> str | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM bot_meta WHERE key = %s", (key,))
            row = cur.fetchone()
            return row["value"] if row else None

def set_bot_meta(key: str, value: str | None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO bot_meta (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, value))


# ─── B2B bread orders ─────────────────────────────────────────────────────────

def save_b2b_order(group_chat_id: int, business_name: str, items: list[dict], delivery_date: str, batch_id: str = "") -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO b2b_orders "
                "(group_chat_id, business_name, item, quantity, grams, notes, delivery_date, batch_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (group_chat_id, business_name, i["item"], i["qty"],
                     i.get("grams"), i.get("notes"), delivery_date, batch_id, now)
                    for i in items
                ],
            )
    logger.info("Saved B2B order for %s (%s) delivery %s", business_name, group_chat_id, delivery_date)


def get_b2b_orders_for_date(group_chat_id: int, delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, quantity, grams, notes
                FROM b2b_orders
                WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'
                ORDER BY created_at
            """, (group_chat_id, delivery_date))
            return cur.fetchall()


def get_b2b_last_order_item(group_chat_id: int, item: str) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT grams, notes
                FROM b2b_orders
                WHERE group_chat_id = %s AND item = %s AND status = 'confirmed'
                ORDER BY created_at DESC
                LIMIT 1
            """, (group_chat_id, item))
            return cur.fetchone()


def get_b2b_daily_totals(delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, SUM(quantity) AS total
                FROM b2b_orders
                WHERE delivery_date = %s AND status = 'confirmed'
                GROUP BY item
                ORDER BY item
            """, (delivery_date,))
            return cur.fetchall()


def get_b2b_orders_by_group(delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT group_chat_id, business_name, item, quantity, grams, notes
                FROM b2b_orders
                WHERE delivery_date = %s AND status = 'confirmed'
                ORDER BY business_name, item
            """, (delivery_date,))
            return cur.fetchall()


def get_b2b_mini_orders_for_reminder(delivery_date: str, mini_items: tuple[str, ...]) -> list[dict]:
    placeholders = ",".join(["%s"] * len(mini_items))
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT group_chat_id, business_name, item, quantity
                FROM b2b_orders
                WHERE delivery_date = %s AND status = 'confirmed'
                  AND item IN ({placeholders})
                ORDER BY business_name, item
            """, (delivery_date, *mini_items))
            return cur.fetchall()


def delete_b2b_orders_for_date(group_chat_id: int, delivery_date: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM b2b_orders WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'",
                (group_chat_id, delivery_date),
            )


def get_last_b2b_order(group_chat_id: int) -> list[dict]:
    """Return bread items from the most recent confirmed order batch for this customer."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, quantity, grams, notes, created_at,
                       CASE WHEN batch_id != '' THEN batch_id ELSE created_at END AS sid
                FROM b2b_orders
                WHERE group_chat_id = %s AND status = 'confirmed'
                ORDER BY created_at DESC
                LIMIT 1
            """, (group_chat_id,))
            row = cur.fetchone()
            if not row:
                return []
            sid = row["sid"]
            cur.execute("""
                SELECT item, quantity, grams, notes
                FROM b2b_orders
                WHERE group_chat_id = %s AND status = 'confirmed'
                  AND CASE WHEN batch_id != '' THEN batch_id ELSE created_at END = %s
                ORDER BY item
            """, (group_chat_id, sid))
            return cur.fetchall()


def get_b2b_order_sessions(group_chat_id: int, delivery_date: str) -> list[dict]:
    """Return confirmed orders grouped by batch session (batch_id or created_at for old rows).
    Each entry: {session_key, bread: [{item,qty,grams,notes}], cake: [{item,qty,cake_category,order_type,slices}]}
    """
    sid_key = "CASE WHEN batch_id != '' THEN batch_id ELSE created_at END"
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT {sid_key} AS sid, item, quantity, grams, notes, created_at
                FROM b2b_orders
                WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'
                ORDER BY created_at, item
            """, (group_chat_id, delivery_date))
            bread_rows = cur.fetchall()
            cur.execute(f"""
                SELECT {sid_key} AS sid, item, cake_category, order_type, quantity, slices, created_at
                FROM b2b_cake_orders
                WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'
                ORDER BY created_at, item
            """, (group_chat_id, delivery_date))
            cake_rows = cur.fetchall()

    sessions: dict[str, dict] = {}
    order: list[str] = []
    for row in bread_rows:
        sid = row["sid"]
        if sid not in sessions:
            sessions[sid] = {"session_key": sid, "bread": [], "cake": []}
            order.append(sid)
        sessions[sid]["bread"].append({
            "item": row["item"], "qty": row["quantity"],
            "grams": row["grams"], "notes": row["notes"],
        })
    for row in cake_rows:
        sid = row["sid"]
        if sid not in sessions:
            sessions[sid] = {"session_key": sid, "bread": [], "cake": []}
            order.append(sid)
        sessions[sid]["cake"].append({
            "item": row["item"], "qty": row["quantity"],
            "cake_category": row["cake_category"],
            "order_type": row["order_type"],
            "slices": row["slices"],
        })
    return [sessions[sid] for sid in order]


def delete_b2b_order_session(group_chat_id: int, delivery_date: str, session_key: str) -> None:
    """Delete all rows belonging to one order session (identified by batch_id or created_at)."""
    sid_expr = "CASE WHEN batch_id != '' THEN batch_id ELSE created_at END"
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM b2b_orders WHERE group_chat_id = %s AND delivery_date = %s AND {sid_expr} = %s",
                (group_chat_id, delivery_date, session_key),
            )
            cur.execute(
                f"DELETE FROM b2b_cake_orders WHERE group_chat_id = %s AND delivery_date = %s AND {sid_expr} = %s",
                (group_chat_id, delivery_date, session_key),
            )


# ─── B2B cake orders ──────────────────────────────────────────────────────────

def save_b2b_cake_order(group_chat_id: int, business_name: str, items: list[dict], delivery_date: str, batch_id: str = "") -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO b2b_cake_orders "
                "(group_chat_id, business_name, item, cake_category, order_type, quantity, slices, delivery_date, batch_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (group_chat_id, business_name, i["item"], i["cake_category"],
                     i["order_type"], i["qty"], i.get("slices"), delivery_date, batch_id, now)
                    for i in items
                ],
            )
    logger.info("Saved B2B cake order for %s (%s) delivery %s", business_name, group_chat_id, delivery_date)


def get_b2b_cake_orders_for_date(group_chat_id: int, delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, cake_category, order_type, quantity, slices
                FROM b2b_cake_orders
                WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'
                ORDER BY created_at
            """, (group_chat_id, delivery_date))
            return cur.fetchall()


def get_b2b_cake_last_order_item(group_chat_id: int, item: str) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT order_type, slices
                FROM b2b_cake_orders
                WHERE group_chat_id = %s AND item = %s AND status = 'confirmed'
                ORDER BY created_at DESC
                LIMIT 1
            """, (group_chat_id, item))
            return cur.fetchone()


def get_b2b_cake_orders_by_group(delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT group_chat_id, business_name, item, cake_category, order_type, quantity, slices
                FROM b2b_cake_orders
                WHERE delivery_date = %s AND status = 'confirmed'
                ORDER BY business_name, item
            """, (delivery_date,))
            return cur.fetchall()


def get_b2b_cake_daily_totals(delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, cake_category, order_type, SUM(quantity) AS total, slices
                FROM b2b_cake_orders
                WHERE delivery_date = %s AND status = 'confirmed'
                GROUP BY item, order_type, slices, cake_category
                ORDER BY item, order_type
            """, (delivery_date,))
            return cur.fetchall()


def delete_b2b_cake_orders_for_date(group_chat_id: int, delivery_date: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM b2b_cake_orders WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'",
                (group_chat_id, delivery_date),
            )


# ─── Billing ──────────────────────────────────────────────────────────────────

def get_unpaid_b2b_orders(group_chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, item, quantity, grams, notes, delivery_date, created_at, batch_id
                FROM b2b_orders
                WHERE group_chat_id = %s AND status = 'confirmed' AND payment_status = 'unpaid'
                ORDER BY delivery_date, created_at
            """, (group_chat_id,))
            return cur.fetchall()


def get_unpaid_b2b_cake_orders(group_chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, item, cake_category, order_type, quantity, slices, delivery_date, created_at, batch_id
                FROM b2b_cake_orders
                WHERE group_chat_id = %s AND status = 'confirmed' AND payment_status = 'unpaid'
                ORDER BY delivery_date, created_at
            """, (group_chat_id,))
            return cur.fetchall()


def get_groups_with_unpaid_orders() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT group_chat_id, business_name FROM b2b_orders
                WHERE status = 'confirmed' AND payment_status = 'unpaid'
                UNION
                SELECT DISTINCT group_chat_id, business_name FROM b2b_cake_orders
                WHERE status = 'confirmed' AND payment_status = 'unpaid'
                ORDER BY business_name
            """)
            return cur.fetchall()


def get_groups_with_unpaid_on_date(delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT group_chat_id, business_name FROM b2b_orders
                WHERE delivery_date = %s AND status = 'confirmed' AND payment_status = 'unpaid'
                UNION
                SELECT DISTINCT group_chat_id, business_name FROM b2b_cake_orders
                WHERE delivery_date = %s AND status = 'confirmed' AND payment_status = 'unpaid'
                ORDER BY business_name
            """, (delivery_date, delivery_date))
            return cur.fetchall()


def mark_b2b_orders_paid(order_ids: list[int]) -> None:
    placeholders = ",".join(["%s"] * len(order_ids))
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE b2b_orders SET payment_status = 'paid' WHERE id IN ({placeholders})",
                order_ids,
            )


def mark_b2b_cake_orders_paid(order_ids: list[int]) -> None:
    placeholders = ",".join(["%s"] * len(order_ids))
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE b2b_cake_orders SET payment_status = 'paid' WHERE id IN ({placeholders})",
                order_ids,
            )


def save_b2b_payment(
    group_chat_id: int,
    business_name: str,
    amount: float,
    screenshot_path: str | None,
    group_message_id: int | None = None,
    tg_file_unique_id: str | None = None,
    method: str = "photo",
    covered_dates: str | None = None,
) -> int:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO b2b_payments "
                "(group_chat_id, business_name, amount, screenshot_path, group_message_id, "
                "tg_file_unique_id, method, covered_dates, created_at, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'applied') RETURNING id",
                (group_chat_id, business_name, amount, screenshot_path, group_message_id,
                 tg_file_unique_id, method, covered_dates, now),
            )
            return cur.fetchone()["id"]


def is_payment_already_processed(group_chat_id: int, message_id: int, file_unique_id: str | None = None) -> bool:
    """True if this message or file was already processed as a payment (dedup guard)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM b2b_payments WHERE group_chat_id = %s AND group_message_id = %s",
                (group_chat_id, message_id),
            )
            if cur.fetchone():
                return True
            cur.execute(
                "SELECT 1 FROM b2b_pending_verifications WHERE group_chat_id = %s AND photo_msg_id = %s",
                (group_chat_id, message_id),
            )
            if cur.fetchone():
                return True
            if file_unique_id:
                cur.execute(
                    "SELECT 1 FROM b2b_payments WHERE group_chat_id = %s AND tg_file_unique_id = %s",
                    (group_chat_id, file_unique_id),
                )
                if cur.fetchone():
                    return True
                cur.execute(
                    "SELECT 1 FROM b2b_pending_verifications WHERE group_chat_id = %s AND tg_file_unique_id = %s",
                    (group_chat_id, file_unique_id),
                )
                if cur.fetchone():
                    return True
            return False


def get_b2b_payment(payment_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM b2b_payments WHERE id = %s", (payment_id,))
            return cur.fetchone()


def update_b2b_payment_status(payment_id: int, status: str) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_payments SET status = %s, applied_at = %s WHERE id = %s",
                (status, now, payment_id),
            )


def get_b2b_payment_history(group_chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, amount, method, covered_dates, created_at, status FROM b2b_payments "
                "WHERE group_chat_id = %s ORDER BY created_at DESC LIMIT 50",
                (group_chat_id,),
            )
            return cur.fetchall()


def get_all_payment_history() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT business_name, amount, method, covered_dates, created_at, status FROM b2b_payments "
                "ORDER BY business_name, created_at DESC"
            )
            return cur.fetchall()


def get_all_payment_accounts() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, type, value FROM b2b_payment_accounts WHERE active = TRUE ORDER BY type, value")
            return cur.fetchall()


def remove_payment_account(account_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE b2b_payment_accounts SET active = FALSE WHERE id = %s", (account_id,))


def get_all_b2b_customers() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT group_chat_id, business_name FROM b2b_customers ORDER BY business_name")
            return cur.fetchall()


# ─── Credit per customer ───────────────────────────────────────────────────────

def get_b2b_customer_credit(group_chat_id: int) -> float:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT credit FROM b2b_customers WHERE group_chat_id = %s", (group_chat_id,))
            row = cur.fetchone()
            return float(row["credit"] or 0) if row else 0.0


def set_b2b_customer_credit(group_chat_id: int, credit: float) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_customers SET credit = %s WHERE group_chat_id = %s",
                (round(credit, 2), group_chat_id),
            )


# ─── Mark-paid requests ────────────────────────────────────────────────────────

def save_markpaid_request(group_chat_id: int, business_name: str, staff_user_id: int) -> int:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO b2b_markpaid_requests "
                "(group_chat_id, business_name, staff_user_id, status, created_at) "
                "VALUES (%s, %s, %s, 'draft', %s) RETURNING id",
                (group_chat_id, business_name, staff_user_id, now),
            )
            return cur.fetchone()["id"]


def get_markpaid_request(request_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM b2b_markpaid_requests WHERE id = %s", (request_id,))
            return cur.fetchone()


def set_markpaid_amount(request_id: int, amount: float) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE b2b_markpaid_requests SET amount = %s WHERE id = %s", (amount, request_id))


def set_markpaid_method(request_id: int, method: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_markpaid_requests SET method = %s, status = 'pending' WHERE id = %s",
                (method, request_id),
            )


def set_markpaid_staff_msg(request_id: int, msg_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE b2b_markpaid_requests SET staff_msg_id = %s WHERE id = %s", (msg_id, request_id))


def set_markpaid_owner_msg(request_id: int, msg_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE b2b_markpaid_requests SET owner_msg_id = %s WHERE id = %s", (msg_id, request_id))


def set_markpaid_status(request_id: int, status: str, covered_dates: str | None = None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_markpaid_requests SET status = %s, covered_dates = %s WHERE id = %s",
                (status, covered_dates, request_id),
            )


# ─── B2B recurring orders ─────────────────────────────────────────────────────

_WEEKDAY_ABBREV = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def save_b2b_recurring_order(
    group_chat_id: int,
    business_name: str,
    items: dict,
    days_of_week: list[str],
    delivery_time: str,
    delivery_method: str,
) -> int:
    import json
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_recurring_orders
                    (group_chat_id, business_name, items_json, days_of_week,
                     delivery_time, delivery_method, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'active', %s)
                RETURNING id
            """, (group_chat_id, business_name, json.dumps(items),
                  json.dumps(days_of_week), delivery_time, delivery_method, now))
            return cur.fetchone()["id"]


def get_b2b_recurring_orders(group_chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, group_chat_id, business_name, items_json, days_of_week,
                       delivery_time, delivery_method, status, created_at
                FROM b2b_recurring_orders
                WHERE group_chat_id = %s AND status = 'active'
                ORDER BY created_at
            """, (group_chat_id,))
            return cur.fetchall()


def get_recurring_order(rec_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, group_chat_id, business_name, items_json, days_of_week,
                       delivery_time, delivery_method, status, created_at
                FROM b2b_recurring_orders WHERE id = %s
            """, (rec_id,))
            return cur.fetchone()


def cancel_b2b_recurring_order(rec_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_recurring_orders SET status = 'cancelled' WHERE id = %s",
                (rec_id,),
            )


def get_active_recurring_orders_for_date(target_date: str) -> list[dict]:
    """Return all active recurring orders whose days include target_date's weekday."""
    import json
    from datetime import date as _date
    day_abbrev = _WEEKDAY_ABBREV[_date.fromisoformat(target_date).weekday()]
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, group_chat_id, business_name, items_json, days_of_week,
                       delivery_time, delivery_method, created_at
                FROM b2b_recurring_orders WHERE status = 'active'
            """)
            rows = cur.fetchall()
    return [r for r in rows if day_abbrev in json.loads(r["days_of_week"])]


def get_or_create_recurring_confirmation(rec_id: int, fulfillment_date: str) -> dict:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_recurring_confirmations
                    (recurring_order_id, fulfillment_date, status, reminder_sent, created_at)
                VALUES (%s, %s, 'pending', 0, %s)
                ON CONFLICT (recurring_order_id, fulfillment_date) DO NOTHING
            """, (rec_id, fulfillment_date, now))
            cur.execute("""
                SELECT id, recurring_order_id, fulfillment_date, status, reminder_sent
                FROM b2b_recurring_confirmations
                WHERE recurring_order_id = %s AND fulfillment_date = %s
            """, (rec_id, fulfillment_date))
            return cur.fetchone()


def update_recurring_reminder_count(rec_id: int, fulfillment_date: str, count: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE b2b_recurring_confirmations SET reminder_sent = %s
                WHERE recurring_order_id = %s AND fulfillment_date = %s
            """, (count, rec_id, fulfillment_date))


def confirm_recurring_instance(rec_id: int, fulfillment_date: str) -> bool:
    """Mark a recurring instance confirmed. Returns True if it was pending."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE b2b_recurring_confirmations SET status = 'confirmed'
                WHERE recurring_order_id = %s AND fulfillment_date = %s AND status = 'pending'
            """, (rec_id, fulfillment_date))
            return cur.rowcount > 0


def skip_recurring_instance(rec_id: int, fulfillment_date: str) -> bool:
    """Mark a recurring instance skipped. Returns True if it was pending."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE b2b_recurring_confirmations SET status = 'skipped'
                WHERE recurring_order_id = %s AND fulfillment_date = %s AND status = 'pending'
            """, (rec_id, fulfillment_date))
            return cur.rowcount > 0


def get_pending_recurring_for_date(target_date: str) -> list[dict]:
    """All pending (unconfirmed/unskipped) recurring confirmation rows for a date."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rc.id, rc.recurring_order_id, rc.fulfillment_date, rc.reminder_sent,
                       ro.group_chat_id
                FROM b2b_recurring_confirmations rc
                JOIN b2b_recurring_orders ro ON ro.id = rc.recurring_order_id
                WHERE rc.fulfillment_date = %s AND rc.status = 'pending'
            """, (target_date,))
            return cur.fetchall()


# ─── B2B dispatch reminders ───────────────────────────────────────────────────

def ensure_b2b_dispatch_reminder(
    group_chat_id: int, fulfillment_date: str,
    fulfillment_time: str, delivery_method: str,
) -> dict:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_dispatch_reminders
                    (group_chat_id, fulfillment_date, fulfillment_time, delivery_method, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (group_chat_id, fulfillment_date) DO NOTHING
            """, (group_chat_id, fulfillment_date, fulfillment_time, delivery_method, now))
            cur.execute("""
                SELECT id, group_chat_id, fulfillment_date, fulfillment_time, delivery_method,
                       status, owner_message_id, snooze_until, escalated
                FROM b2b_dispatch_reminders
                WHERE group_chat_id = %s AND fulfillment_date = %s
            """, (group_chat_id, fulfillment_date))
            return cur.fetchone()


def get_pending_dispatch_reminders(today_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, group_chat_id, fulfillment_date, fulfillment_time, delivery_method,
                       status, owner_message_id, snooze_until, escalated
                FROM b2b_dispatch_reminders
                WHERE fulfillment_date = %s AND status != 'confirmed'
            """, (today_date,))
            return cur.fetchall()


def get_dispatch_reminder(reminder_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, group_chat_id, fulfillment_date, fulfillment_time, delivery_method,
                       status, owner_message_id, snooze_until, escalated
                FROM b2b_dispatch_reminders WHERE id = %s
            """, (reminder_id,))
            return cur.fetchone()


def set_dispatch_reminder_reminded(reminder_id: int, owner_message_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE b2b_dispatch_reminders
                SET status = 'reminded', owner_message_id = %s
                WHERE id = %s
            """, (owner_message_id, reminder_id))


def set_dispatch_reminder_snoozed(reminder_id: int, snooze_until: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE b2b_dispatch_reminders
                SET status = 'snoozed', snooze_until = %s, owner_message_id = NULL
                WHERE id = %s
            """, (snooze_until, reminder_id))


def set_dispatch_reminder_confirmed(reminder_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_dispatch_reminders SET status = 'confirmed' WHERE id = %s",
                (reminder_id,),
            )


def set_dispatch_reminder_escalated(reminder_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_dispatch_reminders SET escalated = TRUE WHERE id = %s",
                (reminder_id,),
            )


def get_b2b_bread_orders_for_group_date(group_chat_id: int, delivery_date: str) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT item, quantity, grams, notes
                FROM b2b_orders
                WHERE group_chat_id = %s AND delivery_date = %s AND status = 'confirmed'
                ORDER BY item
            """, (group_chat_id, delivery_date))
            return cur.fetchall()


# ─── Payment account settings ─────────────────────────────────────────────────

def get_valid_payment_accounts() -> dict:
    """Return {'bank': [...], 'seller': [...]} of active payment accounts."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT type, value FROM b2b_payment_accounts WHERE active = TRUE")
            rows = cur.fetchall()
    result: dict[str, list[str]] = {"bank": [], "seller": []}
    for row in rows:
        if row["type"] in result:
            result[row["type"]].append(row["value"])
    return result


def upsert_payment_account(type_: str, value: str, active: bool = True) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_payment_accounts (type, value, active)
                VALUES (%s, %s, %s)
                ON CONFLICT (value) DO UPDATE SET type = EXCLUDED.type, active = EXCLUDED.active
            """, (type_, value, active))


# ─── Pending payment verifications ────────────────────────────────────────────

def save_pending_verification(group_chat_id: int, photo_msg_id: int, group_ack_msg_id: int | None,
                               owner_msg_id: int | None, amount: float, business_name: str,
                               file_path: str | None, tg_file_id: str | None = None,
                               tg_file_unique_id: str | None = None) -> int:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_pending_verifications
                    (group_chat_id, photo_msg_id, group_ack_msg_id, owner_msg_id,
                     amount, business_name, file_path, tg_file_id, tg_file_unique_id,
                     status, created_at, last_nudge_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                RETURNING id
            """, (group_chat_id, photo_msg_id, group_ack_msg_id, owner_msg_id,
                  amount, business_name, file_path, tg_file_id, tg_file_unique_id, now, now))
            return cur.fetchone()["id"]


def get_pending_verifications() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM b2b_pending_verifications WHERE status = 'pending'")
            return cur.fetchall()


def get_pending_verification(verification_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM b2b_pending_verifications WHERE id = %s", (verification_id,))
            return cur.fetchone()


def set_verification_owner_msg(verification_id: int, owner_msg_id: int) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_pending_verifications SET owner_msg_id = %s, last_nudge_at = %s WHERE id = %s",
                (owner_msg_id, now, verification_id),
            )


def set_verification_status(verification_id: int, status: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_pending_verifications SET status = %s WHERE id = %s",
                (status, verification_id),
            )


# ─── Wrong account alerts ──────────────────────────────────────────────────────

def save_wrong_account_alert(owner_msg_id: int | None, business_name: str, amount: float,
                              wrong_detail: str, tg_file_id: str | None = None) -> int:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO b2b_wrong_account_alerts
                    (owner_msg_id, business_name, amount, wrong_detail, tg_file_id, status, created_at, last_nudge_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
                RETURNING id
            """, (owner_msg_id, business_name, amount, wrong_detail, tg_file_id, now, now))
            return cur.fetchone()["id"]


def get_pending_wrong_account_alerts() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM b2b_wrong_account_alerts WHERE status = 'pending'")
            return cur.fetchall()


def set_wrong_alert_owner_msg(alert_id: int, owner_msg_id: int) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_wrong_account_alerts SET owner_msg_id = %s, last_nudge_at = %s WHERE id = %s",
                (owner_msg_id, now, alert_id),
            )


def set_wrong_alert_seen(alert_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b2b_wrong_account_alerts SET status = 'seen' WHERE id = %s",
                (alert_id,),
            )


# ─── Supplier price intelligence ──────────────────────────────────────────────

def init_supplier_prices_db() -> None:
    """Create supplier price tables. Called from run_extract_prices.py on startup."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS supplier_price_items (
                    id            SERIAL PRIMARY KEY,
                    supplier_name TEXT NOT NULL,
                    product_name  TEXT NOT NULL,
                    price         NUMERIC(10, 3),
                    currency      TEXT DEFAULT 'USD',
                    unit          TEXT,
                    price_notes   TEXT,
                    source_file   TEXT NOT NULL,
                    price_date    DATE,
                    extracted_at  TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(supplier_name, product_name, source_file)
                );
                CREATE TABLE IF NOT EXISTS supplier_files_processed (
                    file_path    TEXT PRIMARY KEY,
                    processed_at TIMESTAMPTZ DEFAULT NOW(),
                    item_count   INTEGER DEFAULT 0,
                    status       TEXT DEFAULT 'ok'
                );
            """)
    logger.info("Supplier prices DB ready")


def is_supplier_file_processed(file_path: str) -> bool:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM supplier_files_processed WHERE file_path = %s",
                (file_path,),
            )
            return cur.fetchone() is not None


def save_supplier_price_items(
    supplier_name: str,
    items: list[dict],
    source_file: str,
    price_date: str | None,
) -> int:
    if not items:
        return 0
    saved = 0
    with _db() as conn:
        with conn.cursor() as cur:
            for item in items:
                product = (item.get("product") or "").strip()
                if not product:
                    continue
                price_val = item.get("price")
                if price_val is not None:
                    try:
                        price_val = float(price_val)
                    except (ValueError, TypeError):
                        price_val = None
                cur.execute("""
                    INSERT INTO supplier_price_items
                        (supplier_name, product_name, price, currency, unit,
                         price_notes, source_file, price_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (supplier_name, product_name, source_file) DO UPDATE
                        SET price        = EXCLUDED.price,
                            currency     = EXCLUDED.currency,
                            unit         = EXCLUDED.unit,
                            price_notes  = EXCLUDED.price_notes,
                            price_date   = EXCLUDED.price_date,
                            extracted_at = NOW()
                """, (
                    supplier_name, product, price_val,
                    item.get("currency", "USD"),
                    item.get("unit"),
                    item.get("notes"),
                    source_file, price_date,
                ))
                saved += 1
    return saved


def mark_supplier_file_processed(file_path: str, item_count: int, status: str = "ok") -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO supplier_files_processed (file_path, item_count, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE
                    SET processed_at = NOW(),
                        item_count   = EXCLUDED.item_count,
                        status       = EXCLUDED.status
            """, (file_path, item_count, status))


def query_supplier_prices(keyword: str | None = None, supplier: str | None = None) -> list[dict]:
    """Return latest price per product×supplier matching the keyword."""
    with _db() as conn:
        with conn.cursor() as cur:
            where_clauses = [
                "spi.price_date = latest.max_date",
            ]
            params: list = []
            if keyword:
                where_clauses.append("LOWER(spi.product_name) LIKE %s")
                params.append(f"%{keyword.lower()}%")
            if supplier:
                where_clauses.append("LOWER(spi.supplier_name) LIKE %s")
                params.append(f"%{supplier.lower()}%")
            where_sql = " AND ".join(where_clauses)
            cur.execute(f"""
                SELECT spi.supplier_name, spi.product_name, spi.price,
                       spi.currency, spi.unit, spi.price_notes, spi.price_date
                FROM supplier_price_items spi
                JOIN (
                    SELECT supplier_name, product_name, MAX(price_date) as max_date
                    FROM supplier_price_items
                    WHERE price IS NOT NULL
                    GROUP BY supplier_name, product_name
                ) latest ON latest.supplier_name = spi.supplier_name
                       AND latest.product_name  = spi.product_name
                WHERE {where_sql}
                ORDER BY spi.product_name, spi.price ASC NULLS LAST
            """, params)
            return [dict(r) for r in cur.fetchall()]


# ─── GM Manager Bot ───────────────────────────────────────────────────────────

def init_gm_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_concerns (
                    id              SERIAL PRIMARY KEY,
                    source_chat_id  BIGINT,
                    source_msg_key  TEXT,           -- composite key to avoid re-flagging
                    concern_type    TEXT NOT NULL,  -- low_stock | cleanliness | waste | mistake | staffing | photo
                    severity        TEXT DEFAULT 'warning',  -- info | warning | critical
                    sender_name     TEXT,
                    description     TEXT NOT NULL,
                    detected_at     TIMESTAMPTZ DEFAULT NOW(),
                    sent_msg_id     INTEGER,        -- Telegram msg ID in owner chat
                    reviewed_at     TIMESTAMPTZ,
                    review_action   TEXT,           -- all_good | real_issue | teach
                    teaching_note   TEXT,
                    UNIQUE(source_msg_key, concern_type)
                );
                CREATE TABLE IF NOT EXISTS gm_rules (
                    id           SERIAL PRIMARY KEY,
                    concern_type TEXT,
                    pattern      TEXT NOT NULL,
                    action       TEXT NOT NULL,  -- ignore | downgrade | escalate
                    note         TEXT,
                    created_at   TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS gm_state (
                    key        TEXT PRIMARY KEY,
                    value      TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS gm_proposals (
                    id                  SERIAL PRIMARY KEY,
                    proposal_type       TEXT NOT NULL DEFAULT 'correction', -- correction | recognition
                    group_name          TEXT NOT NULL,
                    concern_type        TEXT DEFAULT 'mixed',
                    concern_ids         TEXT NOT NULL DEFAULT '[]',  -- JSON array of concern IDs
                    root_cause          TEXT,
                    solution_text       TEXT NOT NULL,               -- message to eventually send
                    recipients          TEXT DEFAULT 'group',        -- group | individual
                    staff_names         TEXT DEFAULT '[]',           -- JSON array of names
                    points              INTEGER DEFAULT 0,           -- points to award (recognition only)
                    status              TEXT DEFAULT 'draft',        -- draft | approved | skipped | rejected
                    model               TEXT DEFAULT 'claude-sonnet-4-6', -- which model generated this
                    refinement_history  TEXT DEFAULT '[]',           -- JSON array of {note, at} entries
                    created_at          TIMESTAMPTZ DEFAULT NOW(),
                    approved_at         TIMESTAMPTZ,
                    skipped_at          TIMESTAMPTZ,
                    owner_msg_id        INTEGER
                );
                -- Migrations for existing deployments
                ALTER TABLE gm_proposals ADD COLUMN IF NOT EXISTS model TEXT DEFAULT 'claude-sonnet-4-6';
                ALTER TABLE gm_proposals ADD COLUMN IF NOT EXISTS skipped_at TIMESTAMPTZ;
                ALTER TABLE gm_proposals ADD COLUMN IF NOT EXISTS refinement_history TEXT DEFAULT '[]';
                CREATE TABLE IF NOT EXISTS gm_staff_points (
                    id          SERIAL PRIMARY KEY,
                    staff_name  TEXT NOT NULL,
                    points      INTEGER NOT NULL DEFAULT 1,
                    reason      TEXT,
                    concern_id  INTEGER,
                    awarded_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)


def gm_get_state(key: str) -> str | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM gm_state WHERE key = %s", (key,))
            row = cur.fetchone()
            return row["value"] if row else None


def gm_set_state(key: str, value: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_state (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """, (key, value))


def gm_save_concern(source_chat_id: int, source_msg_key: str, concern_type: str,
                    severity: str, sender_name: str | None, description: str) -> int | None:
    """Insert a concern. Returns the new id, or None if already exists."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_concerns
                    (source_chat_id, source_msg_key, concern_type, severity, sender_name, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_msg_key, concern_type) DO NOTHING
                RETURNING id
            """, (source_chat_id, source_msg_key, concern_type, severity, sender_name, description))
            row = cur.fetchone()
            return row["id"] if row else None


def gm_get_unsent_concerns() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_chat_id, source_msg_key, concern_type, severity, sender_name, description, detected_at
                FROM gm_concerns
                WHERE sent_msg_id IS NULL AND review_action IS NULL
                ORDER BY detected_at ASC
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_unsent_by_sender(sender_query: str) -> list[dict]:
    """
    Return unsent concerns for a sender. Tries exact match first, then prefix,
    then contains. Returns None if more than one distinct sender matches
    (caller should show the ambiguous list instead of sending).
    """
    with _db() as conn:
        with conn.cursor() as cur:
            for pattern in [sender_query, sender_query + '%', '%' + sender_query + '%']:
                cur.execute("""
                    SELECT DISTINCT sender_name FROM gm_concerns
                    WHERE sent_msg_id IS NULL AND review_action IS NULL
                      AND sender_name ILIKE %s
                """, (pattern,))
                matches = [r["sender_name"] for r in cur.fetchall()]
                if matches:
                    break

            if not matches:
                return []
            if len(matches) > 1:
                return None  # ambiguous — caller will list the options

            exact = matches[0]
            cur.execute("""
                SELECT id, source_chat_id, source_msg_key, concern_type, severity, sender_name, description, detected_at
                FROM gm_concerns
                WHERE sent_msg_id IS NULL AND review_action IS NULL
                  AND sender_name = %s
                ORDER BY detected_at ASC
            """, (exact,))
            return [dict(r) for r in cur.fetchall()]


def gm_get_pending_by_sender() -> list[dict]:
    """Return each sender with their count of unsent concerns, sorted by count desc."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sender_name, COUNT(*) as count,
                       SUM(CASE WHEN concern_type = 'mistake' THEN 1 ELSE 0 END) as mistakes,
                       SUM(CASE WHEN concern_type = 'waste' THEN 1 ELSE 0 END) as waste,
                       SUM(CASE WHEN concern_type = 'low_stock' THEN 1 ELSE 0 END) as low_stock
                FROM gm_concerns
                WHERE sent_msg_id IS NULL AND review_action IS NULL
                GROUP BY sender_name
                ORDER BY count DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_unreviewed_by_sender() -> list[dict]:
    """Concerns already sent to owner but not yet reviewed (button not tapped)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sender_name, COUNT(*) as count,
                       SUM(CASE WHEN concern_type = 'mistake' THEN 1 ELSE 0 END) as mistakes,
                       SUM(CASE WHEN concern_type = 'waste' THEN 1 ELSE 0 END) as waste,
                       SUM(CASE WHEN concern_type = 'low_stock' THEN 1 ELSE 0 END) as low_stock
                FROM gm_concerns
                WHERE sent_msg_id IS NOT NULL AND review_action IS NULL
                GROUP BY sender_name
                ORDER BY count DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_unreviewed_by_sender_name(sender_name: str) -> list[dict]:
    """Return all unreviewed (sent but no button tapped) concerns for an exact sender name."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_chat_id, source_msg_key, concern_type,
                       severity, sender_name, description, detected_at
                FROM gm_concerns
                WHERE sent_msg_id IS NOT NULL AND review_action IS NULL
                  AND sender_name = %s
                ORDER BY detected_at ASC
            """, (sender_name,))
            return [dict(r) for r in cur.fetchall()]


def gm_save_proposal(proposal_type: str, group_name: str, concern_type: str,
                     concern_ids: list, root_cause: str, solution_text: str,
                     recipients: str, staff_names: list, points: int = 0,
                     model: str = "claude-sonnet-4-6") -> int:
    import json as _json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_proposals
                    (proposal_type, group_name, concern_type, concern_ids,
                     root_cause, solution_text, recipients, staff_names, points, model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (proposal_type, group_name, concern_type,
                  _json.dumps(concern_ids), root_cause, solution_text,
                  recipients, _json.dumps(staff_names), points, model))
            return cur.fetchone()["id"]


def gm_get_proposal(proposal_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM gm_proposals WHERE id = %s", (proposal_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def gm_get_draft_proposals() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_proposals WHERE status = 'draft' ORDER BY created_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_approved_policy_for_type(concern_type: str) -> dict | None:
    """Most recently approved group-correction policy matching a concern type.
    Used to voice an approved policy live when a matching message appears.
    Matches the exact type or a 'mixed' policy; returns None if none approved."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_proposals
                WHERE status = 'approved'
                  AND proposal_type = 'correction'
                  AND recipients = 'group'
                  AND (concern_type = %s OR concern_type = 'mixed')
                ORDER BY approved_at DESC NULLS LAST
                LIMIT 1
            """, (concern_type,))
            row = cur.fetchone()
            return dict(row) if row else None


def gm_approve_proposal(proposal_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_proposals SET status = 'approved', approved_at = NOW()
                WHERE id = %s
            """, (proposal_id,))


def gm_reject_proposal(proposal_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE gm_proposals SET status = 'rejected' WHERE id = %s", (proposal_id,))


def gm_skip_proposal(proposal_id: int) -> None:
    """Soft-skip: mark proposal as skipped and return its concerns to the unreviewed pool."""
    import json as _json
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT concern_ids FROM gm_proposals WHERE id = %s", (proposal_id,))
            row = cur.fetchone()
            if not row:
                return
            concern_ids = _json.loads(row["concern_ids"] or "[]")
            if concern_ids:
                cur.execute(
                    "UPDATE gm_concerns SET review_action = NULL, reviewed_at = NULL WHERE id = ANY(%s)",
                    (concern_ids,)
                )
            cur.execute(
                "UPDATE gm_proposals SET status = 'skipped', skipped_at = NOW() WHERE id = %s",
                (proposal_id,)
            )


def gm_get_stale_draft_proposals(hours: int = 24) -> list[dict]:
    """Return draft proposals older than `hours` hours."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_proposals
                WHERE status = 'draft'
                AND created_at < NOW() - (%s * INTERVAL '1 hour')
            """, (hours,))
            return [dict(r) for r in cur.fetchall()]


_MODEL_RANK = {
    "claude-haiku-4-5-20251001": 1,
    "claude-sonnet-4-6":         2,
    "claude-opus-4-7":           3,
}


def gm_purge_lower_ranked_drafts(keep_model: str) -> int:
    """Delete draft proposals generated by a lower-ranked model than keep_model.
    Returns concerns to unreviewed pool. Returns count of purged proposals."""
    import json as _json
    keep_rank = _MODEL_RANK.get(keep_model, 0)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, concern_ids, model FROM gm_proposals WHERE status = 'draft'")
            rows = cur.fetchall()
            to_delete = []
            all_concern_ids = []
            for r in rows:
                rank = _MODEL_RANK.get(r["model"] or "", 0)
                if rank < keep_rank:
                    to_delete.append(r["id"])
                    all_concern_ids.extend(_json.loads(r["concern_ids"] or "[]"))
            if not to_delete:
                return 0
            if all_concern_ids:
                cur.execute(
                    "UPDATE gm_concerns SET review_action = NULL, reviewed_at = NULL WHERE id = ANY(%s)",
                    (all_concern_ids,)
                )
            cur.execute("DELETE FROM gm_proposals WHERE id = ANY(%s)", (to_delete,))
            return len(to_delete)


def gm_update_proposal_solution(proposal_id: int, solution_text: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE gm_proposals SET solution_text = %s WHERE id = %s",
                        (solution_text, proposal_id))


def gm_append_refinement_note(proposal_id: int, note: str) -> None:
    """Append one owner feedback note to the proposal's refinement history."""
    import json as _json
    from datetime import datetime, timezone
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT refinement_history FROM gm_proposals WHERE id = %s", (proposal_id,))
            row = cur.fetchone()
            history = _json.loads(row["refinement_history"] or "[]") if row else []
            history.append({"note": note, "at": datetime.now(timezone.utc).isoformat()})
            cur.execute(
                "UPDATE gm_proposals SET refinement_history = %s WHERE id = %s",
                (_json.dumps(history), proposal_id),
            )


def gm_set_proposal_msg_id(proposal_id: int, msg_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE gm_proposals SET owner_msg_id = %s WHERE id = %s",
                        (msg_id, proposal_id))


def gm_award_points(staff_name: str, points: int, reason: str,
                    concern_id: int | None = None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_staff_points (staff_name, points, reason, concern_id)
                VALUES (%s, %s, %s, %s)
            """, (staff_name, points, reason, concern_id))


def gm_get_points_summary(since_days: int = 30) -> list[dict]:
    """Return monthly point totals per staff, ordered by total desc."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT staff_name,
                       SUM(CASE WHEN points > 0 THEN points ELSE 0 END) AS good_points,
                       SUM(CASE WHEN points < 0 THEN points ELSE 0 END) AS bad_points,
                       COUNT(*) AS entries
                FROM gm_staff_points
                WHERE awarded_at >= NOW() - INTERVAL '%s days'
                GROUP BY staff_name
                ORDER BY good_points DESC
            """, (since_days,))
            return [dict(r) for r in cur.fetchall()]


def gm_mark_sent(concern_id: int, telegram_msg_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE gm_concerns SET sent_msg_id = %s WHERE id = %s",
                (telegram_msg_id, concern_id)
            )


def gm_review_concern(concern_id: int, action: str, teaching_note: str | None = None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_concerns
                SET review_action = %s, teaching_note = %s, reviewed_at = NOW()
                WHERE id = %s
            """, (action, teaching_note, concern_id))


def gm_get_concern_by_msg_id(telegram_msg_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM gm_concerns WHERE sent_msg_id = %s",
                (telegram_msg_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def gm_save_rule(concern_type: str, pattern: str, action: str, note: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_rules (concern_type, pattern, action, note)
                VALUES (%s, %s, %s, %s)
            """, (concern_type, pattern, action, note))


def gm_get_rules() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM gm_rules ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]


# ── Lateness / pay-back ladder ────────────────────────────────────────────────

def init_gm_lateness_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_lateness_cases (
                    id                  SERIAL PRIMARY KEY,
                    chat_id             BIGINT NOT NULL,
                    chat_title          TEXT,
                    case_msg_id         BIGINT NOT NULL,       -- senior's report; we reply to this
                    last_question_msg_id BIGINT,               -- GM's latest question (senior or group)
                    reporter_name       TEXT,
                    reporter_uid        BIGINT,
                    late_person         TEXT,
                    late_uid            BIGINT,
                    payback_day         TEXT,
                    status              TEXT NOT NULL DEFAULT 'awaiting_payback',
                    asked_senior_at     TIMESTAMPTZ,
                    asked_group_at      TIMESTAMPTZ,
                    escalated_at        TIMESTAMPTZ,
                    resolved_at         TIMESTAMPTZ,
                    created_at          TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (chat_id, case_msg_id)
                );
            """)


def gm_create_lateness_case(chat_id: int, chat_title: str | None, case_msg_id: int,
                            reporter_name: str | None, reporter_uid: int | None,
                            late_person: str | None, late_uid: int | None,
                            last_question_msg_id: int | None) -> int | None:
    """Open a case (status awaiting_payback). Idempotent on (chat_id, case_msg_id).
    Returns the new id, or None if a case already exists for that message."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_lateness_cases
                    (chat_id, chat_title, case_msg_id, reporter_name, reporter_uid,
                     late_person, late_uid, last_question_msg_id, status, asked_senior_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'awaiting_payback', NOW())
                ON CONFLICT (chat_id, case_msg_id) DO NOTHING
                RETURNING id
            """, (chat_id, chat_title, case_msg_id, reporter_name, reporter_uid,
                  late_person, late_uid, last_question_msg_id))
            row = cur.fetchone()
            return row["id"] if row else None


def gm_get_open_lateness_cases() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_lateness_cases
                WHERE status IN ('awaiting_payback', 'group_asked')
                ORDER BY created_at
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_open_lateness_in_chat(chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_lateness_cases
                WHERE chat_id = %s AND status IN ('awaiting_payback', 'group_asked')
                ORDER BY created_at DESC
            """, (chat_id,))
            return [dict(r) for r in cur.fetchall()]


def gm_mark_lateness_group_asked(case_id: int, question_msg_id: int | None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_lateness_cases
                SET status = 'group_asked', asked_group_at = NOW(),
                    last_question_msg_id = COALESCE(%s, last_question_msg_id)
                WHERE id = %s
            """, (question_msg_id, case_id))


def gm_resolve_lateness(case_id: int, payback_day: str | None) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_lateness_cases
                SET status = 'resolved', payback_day = %s, resolved_at = NOW()
                WHERE id = %s
            """, (payback_day, case_id))


def gm_escalate_lateness(case_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_lateness_cases
                SET status = 'escalated', escalated_at = NOW()
                WHERE id = %s
            """, (case_id,))


# ── Leave / time-off events (accumulate now; AL deduction once balances seeded) ──

def init_gm_leave_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_leave_events (
                    id              SERIAL PRIMARY KEY,
                    chat_id         BIGINT NOT NULL,
                    chat_title      TEXT,
                    source_msg_id   BIGINT NOT NULL,
                    reporter_name   TEXT,
                    reporter_uid    BIGINT,
                    person          TEXT,
                    leave_type      TEXT,          -- al | sick | off | unspecified
                    said_al         BOOLEAN DEFAULT FALSE,
                    dates_text      TEXT,
                    reason          TEXT,
                    needs_clarification BOOLEAN DEFAULT FALSE,
                    clarification_id    INTEGER,
                    status          TEXT DEFAULT 'logged',
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (chat_id, source_msg_id)
                );
            """)


def gm_create_leave_event(chat_id: int, chat_title: str | None, source_msg_id: int,
                          reporter_name: str | None, reporter_uid: int | None,
                          person: str | None, leave_type: str, said_al: bool,
                          dates_text: str | None, reason: str | None,
                          needs_clarification: bool) -> int | None:
    """Record a detected leave announcement. Idempotent on (chat_id, source_msg_id)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_leave_events
                    (chat_id, chat_title, source_msg_id, reporter_name, reporter_uid,
                     person, leave_type, said_al, dates_text, reason, needs_clarification)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chat_id, source_msg_id) DO NOTHING
                RETURNING id
            """, (chat_id, chat_title, source_msg_id, reporter_name, reporter_uid,
                  person, leave_type, said_al, dates_text, reason, needs_clarification))
            row = cur.fetchone()
            return row["id"] if row else None


def gm_link_leave_clarification(event_id: int, clarification_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE gm_leave_events SET clarification_id = %s WHERE id = %s",
                        (clarification_id, event_id))


def gm_get_sales_history() -> list[dict]:
    """One total_sales figure per business day (latest FINAL report wins), for the
    sales-anomaly framework. Falls back to any report for a day with no final."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (business_day) business_day, total_sales
                FROM gm_daily_reports
                WHERE superseded = FALSE AND total_sales IS NOT NULL
                ORDER BY business_day,
                         CASE WHEN report_kind = 'final' THEN 0 ELSE 1 END,
                         posted_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_staff_uid(display_name: str | None) -> int | None:
    """Latest Telegram user id seen for this exact display name in any group.
    Used to build a pinging mention. Returns None if never seen."""
    if not display_name:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sender_id FROM ops_messages
                WHERE sender_name = %s AND sender_id IS NOT NULL
                ORDER BY sent_at DESC LIMIT 1
            """, (display_name,))
            row = cur.fetchone()
            return row["sender_id"] if row else None


# ── Finance label aliases (learned from AI fallback) ──────────────────────────

def init_gm_finance_aliases_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_finance_aliases (
                    id          SERIAL PRIMARY KEY,
                    field       TEXT NOT NULL,
                    label       TEXT NOT NULL,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (field, label)
                );
            """)


def gm_add_finance_alias(field: str, label: str) -> None:
    """Learn a label→field mapping the deterministic parser missed. Idempotent."""
    label = (label or "").strip().lower()
    if not field or not label:
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_finance_aliases (field, label) VALUES (%s, %s)
                ON CONFLICT (field, label) DO NOTHING
            """, (field, label))


def gm_get_finance_aliases() -> dict:
    """Return {field: [labels]} of all learned aliases."""
    out: dict = {}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT field, label FROM gm_finance_aliases")
            for r in cur.fetchall():
                out.setdefault(r["field"], []).append(r["label"])
    return out


def gm_get_lateness_cases_since(days: int = 7) -> list[dict]:
    """All lateness cases created within the last `days` (any status)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_lateness_cases
                WHERE created_at >= NOW() - (%s || ' days')::interval
                ORDER BY created_at
            """, (days,))
            return [dict(r) for r in cur.fetchall()]


def gm_get_concerns_since(concern_type: str, days: int = 7) -> list[dict]:
    """Concerns of a given type created within the last `days`."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_concerns
                WHERE concern_type = %s AND detected_at >= NOW() - (%s || ' days')::interval
                ORDER BY detected_at
            """, (concern_type, days))
            return [dict(r) for r in cur.fetchall()]


def gm_get_low_stock_history(chat_id: int, since_days: int = 7) -> list[dict]:
    """Return recent low-stock alert messages grouped by sender and date."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sender_name, text, sent_at::date as day
                FROM ops_messages
                WHERE chat_id = %s
                  AND (LOWER(text) LIKE '%%almost out%%'
                       OR LOWER(text) LIKE '%%out of stock%%'
                       OR LOWER(text) LIKE '%%almost out%%'
                       OR LOWER(text) LIKE '%%please buy%%'
                       OR LOWER(text) LIKE '%%please order%%'
                       OR LOWER(text) LIKE '%%running low%%')
                  AND sent_at::timestamptz >= NOW() - INTERVAL '%s days'
                ORDER BY sender_name, sent_at
            """, (chat_id, since_days))
            return [dict(r) for r in cur.fetchall()]


def gm_get_new_messages(chat_id: int, since: str) -> list[dict]:
    """Return messages newer than `since` ISO timestamp."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, message_id, chat_id, chat_title, sender_name, text, media_type, sent_at
                FROM ops_messages
                WHERE chat_id = %s AND sent_at::timestamptz > %s::timestamptz
                ORDER BY sent_at ASC
            """, (chat_id, since))
            return [dict(r) for r in cur.fetchall()]


def gm_get_new_messages_multi(chat_ids: list[int], since: str) -> list[dict]:
    """Return messages newer than `since` from multiple chats, ordered by time."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, message_id, chat_id, chat_title, sender_name, text, media_type, sent_at
                FROM ops_messages
                WHERE chat_id = ANY(%s) AND sent_at::timestamptz > %s::timestamptz
                ORDER BY sent_at ASC
            """, (chat_ids, since))
            return [dict(r) for r in cur.fetchall()]


def gm_get_related_photos(chat_id: int, ops_msg_id: int, sender_name: str,
                          window_secs: int = 600) -> list[int]:
    """
    Return Telegram message_ids of photos from the same sender within
    window_secs of the given ops_messages.id. Includes the source message
    itself if it has media. Used to attach photos when sending historical concerns.
    """
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT message_id, sent_at, media_type FROM ops_messages WHERE id = %s",
                (ops_msg_id,)
            )
            ref = cur.fetchone()
            if not ref:
                return []

            results = []
            # Include source message if it has media
            if ref["media_type"] in ("photo", "video", "document"):
                results.append(ref["message_id"])

            # Nearby media from same sender within the window
            cur.execute("""
                SELECT message_id FROM ops_messages
                WHERE chat_id = %s
                  AND sender_name = %s
                  AND media_type IN ('photo', 'video', 'document')
                  AND id != %s
                  AND ABS(EXTRACT(EPOCH FROM (
                      sent_at::timestamptz - %s::timestamptz
                  ))) <= %s
                ORDER BY sent_at
                LIMIT 5
            """, (chat_id, sender_name, ops_msg_id, ref["sent_at"], window_secs))
            for r in cur.fetchall():
                if r["message_id"] not in results:
                    results.append(r["message_id"])

            return results[:4]  # cap at 4 total


# ─── Receipt clarifications ───────────────────────────────────────────────────

def init_receipt_clarifications_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS receipt_clarifications (
                    id              SERIAL PRIMARY KEY,
                    chat_id         BIGINT NOT NULL,
                    photo_msg_id    INTEGER NOT NULL,   -- original receipt message
                    bot_msg_id      INTEGER,            -- GM's question message
                    question        TEXT NOT NULL,
                    answer          TEXT,
                    sender_name     TEXT,
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    answered_at     TIMESTAMPTZ,
                    UNIQUE (chat_id, photo_msg_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hiring_candidates (
                    id              SERIAL PRIMARY KEY,
                    name            TEXT NOT NULL,
                    candidate_type  TEXT NOT NULL DEFAULT 'applicant',  -- 'applicant' or 'staff'
                    position        TEXT,
                    quiz_date       DATE,
                    score_a         INTEGER,        -- Part A: /60
                    score_b         INTEGER,        -- Part B: /22
                    written_pct     INTEGER,        -- Part C+D: 0-100
                    overall_pct     INTEGER,        -- 0-100
                    classification  TEXT,           -- 'strong', 'conditional', 'borderline', 'reject'
                    red_flags       JSONB,          -- list of flag strings
                    retest_questions JSONB,         -- list of question numbers to retest verbally
                    notes           TEXT,
                    hired           BOOLEAN,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hiring_feedback_templates (
                    id              SERIAL PRIMARY KEY,
                    candidate_id    INTEGER REFERENCES hiring_candidates(id),
                    candidate_name  TEXT,           -- denormalized for easy lookup
                    score_range     TEXT,           -- 'high','medium','low' — NULL if candidate-specific
                    topic           TEXT,           -- 'punctuality','mistake_reporting','quiet_time', etc.
                    point_number    INTEGER,
                    english_text    TEXT NOT NULL,
                    khmer_text      TEXT NOT NULL,
                    is_generic      BOOLEAN DEFAULT FALSE,  -- TRUE = reusable for similar future candidates
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)


# ── Hiring ────────────────────────────────────────────────────────────────────

def hiring_save_candidate(name: str, candidate_type: str = "applicant", **kwargs) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            fields = ["name", "candidate_type"] + list(kwargs.keys())
            values = [name, candidate_type] + list(kwargs.values())
            placeholders = ", ".join(["%s"] * len(values))
            cols = ", ".join(fields)
            cur.execute(
                f"INSERT INTO hiring_candidates ({cols}) VALUES ({placeholders}) RETURNING id",
                values
            )
            return cur.fetchone()["id"]


def hiring_save_feedback(candidate_name: str, points: list[dict],
                          candidate_id: int = None, score_range: str = None,
                          is_generic: bool = False):
    """points: list of {point_number, topic, english_text, khmer_text}"""
    with _db() as conn:
        with conn.cursor() as cur:
            for p in points:
                cur.execute("""
                    INSERT INTO hiring_feedback_templates
                        (candidate_id, candidate_name, score_range, topic,
                         point_number, english_text, khmer_text, is_generic)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (candidate_id, candidate_name, score_range, p.get("topic"),
                      p["point_number"], p["english_text"], p["khmer_text"], is_generic))


def hiring_get_feedback(candidate_name: str = None, score_range: str = None,
                         generic_only: bool = False) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            if generic_only:
                cur.execute("""
                    SELECT * FROM hiring_feedback_templates
                    WHERE is_generic = TRUE AND (score_range = %s OR score_range IS NULL)
                    ORDER BY point_number
                """, (score_range,))
            else:
                cur.execute("""
                    SELECT * FROM hiring_feedback_templates
                    WHERE candidate_name = %s
                    ORDER BY point_number
                """, (candidate_name,))
            return cur.fetchall()


def receipt_save_clarification(chat_id: int, photo_msg_id: int, bot_msg_id: int,
                                question: str, sender_name: str) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO receipt_clarifications (chat_id, photo_msg_id, bot_msg_id, question, sender_name)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chat_id, photo_msg_id) DO UPDATE
                    SET bot_msg_id = EXCLUDED.bot_msg_id, question = EXCLUDED.question
                RETURNING id
            """, (chat_id, photo_msg_id, bot_msg_id, question, sender_name))
            return cur.fetchone()["id"]


def receipt_get_pending(chat_id: int, bot_msg_id: int) -> dict | None:
    """Return a pending clarification that the staff member is replying to."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM receipt_clarifications
                WHERE chat_id = %s AND bot_msg_id = %s AND answer IS NULL
            """, (chat_id, bot_msg_id))
            return cur.fetchone()


def receipt_save_answer(clarification_id: int, answer: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE receipt_clarifications
                SET answer = %s, answered_at = NOW()
                WHERE id = %s
            """, (answer, clarification_id))


def receipt_get_answered_examples(chat_id: int, limit: int = 8) -> list[dict]:
    """Return recent answered clarifications for a chat — used as few-shot context for AI."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT question, answer
                FROM receipt_clarifications
                WHERE chat_id = %s AND answer IS NOT NULL
                ORDER BY answered_at DESC
                LIMIT %s
            """, (chat_id, limit))
            return [dict(r) for r in cur.fetchall()]


def receipt_upsert_answered(chat_id: int, photo_msg_id: int, bot_msg_id: int,
                             question: str, answer: str, sender_name: str) -> None:
    """Insert a pre-answered clarification (for backfill). Ignores duplicates."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO receipt_clarifications
                    (chat_id, photo_msg_id, bot_msg_id, question, answer, sender_name,
                     created_at, answered_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (chat_id, photo_msg_id) DO UPDATE
                    SET answer = EXCLUDED.answer, answered_at = NOW()
            """, (chat_id, photo_msg_id, bot_msg_id, question, answer, sender_name))


# ─── GM daily finance reports ─────────────────────────────────────────────────

def init_gm_finance_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_daily_reports (
                    id                 SERIAL PRIMARY KEY,
                    business_day       DATE NOT NULL,
                    report_kind        TEXT NOT NULL,            -- mid | final
                    source_chat_id     BIGINT NOT NULL,
                    source_message_id  BIGINT NOT NULL,
                    posted_at          TIMESTAMPTZ,
                    stated_date        DATE,
                    raw_text           TEXT,
                    -- raw fields as written
                    cash_on_hand       NUMERIC,
                    cash_income        NUMERIC,
                    aba_income         NUMERIC,
                    total_sales        NUMERIC,
                    cash_expense       NUMERIC,
                    aba_expense        NUMERIC,
                    stated_total       NUMERIC,
                    cash_count         NUMERIC,
                    over_amount        NUMERIC,
                    lost_amount        NUMERIC,
                    -- recomputed
                    expected_drawer    NUMERIC,
                    over_lost_computed NUMERIC,
                    total_math_error   NUMERIC,
                    sales_check        NUMERIC,
                    math_ok            BOOLEAN DEFAULT TRUE,
                    notes              TEXT,
                    created_at         TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (source_chat_id, source_message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_gm_daily_reports_day
                    ON gm_daily_reports (business_day, report_kind);
                ALTER TABLE gm_daily_reports
                    ADD COLUMN IF NOT EXISTS superseded BOOLEAN DEFAULT FALSE;
            """)
    logger.info("GM finance DB ready")


def _recompute_superseded(cur, business_day: str, report_kind: str) -> None:
    """Mark all but the latest report (by posted_at) for a day+shift as superseded.
    Handles staff correcting a report and deleting the old one."""
    cur.execute("""
        UPDATE gm_daily_reports d
        SET superseded = (d.id <> latest.id)
        FROM (
            SELECT id FROM gm_daily_reports
            WHERE business_day = %s AND report_kind = %s
            ORDER BY posted_at DESC NULLS LAST, id DESC
            LIMIT 1
        ) latest
        WHERE d.business_day = %s AND d.report_kind = %s
    """, (business_day, report_kind, business_day, report_kind))


def save_daily_report(
    business_day: str,
    report_kind: str,
    source_chat_id: int,
    source_message_id: int,
    posted_at: str | None,
    raw_text: str,
    raw: dict,
    computed: dict,
) -> int | None:
    """
    Store one parsed daily report. Idempotent on (source_chat_id, source_message_id):
    re-parsing the same message updates the row rather than duplicating.
    Returns the row id.
    """
    notes = computed.get("notes") or []
    notes_text = " | ".join(notes) if notes else None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_daily_reports
                    (business_day, report_kind, source_chat_id, source_message_id,
                     posted_at, stated_date, raw_text,
                     cash_on_hand, cash_income, aba_income, total_sales,
                     cash_expense, aba_expense, stated_total, cash_count,
                     over_amount, lost_amount,
                     expected_drawer, over_lost_computed, total_math_error,
                     sales_check, math_ok, notes)
                VALUES (%s,%s,%s,%s, %s,%s,%s,
                        %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,
                        %s,%s,%s, %s,%s,%s)
                ON CONFLICT (source_chat_id, source_message_id) DO UPDATE SET
                    business_day = EXCLUDED.business_day,
                    report_kind  = EXCLUDED.report_kind,
                    posted_at    = EXCLUDED.posted_at,
                    stated_date  = EXCLUDED.stated_date,
                    raw_text     = EXCLUDED.raw_text,
                    cash_on_hand = EXCLUDED.cash_on_hand,
                    cash_income  = EXCLUDED.cash_income,
                    aba_income   = EXCLUDED.aba_income,
                    total_sales  = EXCLUDED.total_sales,
                    cash_expense = EXCLUDED.cash_expense,
                    aba_expense  = EXCLUDED.aba_expense,
                    stated_total = EXCLUDED.stated_total,
                    cash_count   = EXCLUDED.cash_count,
                    over_amount  = EXCLUDED.over_amount,
                    lost_amount  = EXCLUDED.lost_amount,
                    expected_drawer    = EXCLUDED.expected_drawer,
                    over_lost_computed = EXCLUDED.over_lost_computed,
                    total_math_error   = EXCLUDED.total_math_error,
                    sales_check  = EXCLUDED.sales_check,
                    math_ok      = EXCLUDED.math_ok,
                    notes        = EXCLUDED.notes
                RETURNING id
            """, (
                business_day, report_kind, source_chat_id, source_message_id,
                posted_at, raw.get("stated_date"), raw_text,
                raw.get("cash_on_hand"), raw.get("cash_income"), raw.get("aba_income"),
                raw.get("total_sales"), raw.get("cash_expense"), raw.get("aba_expense"),
                raw.get("stated_total"), raw.get("cash_count"),
                raw.get("over"), raw.get("lost"),
                computed.get("expected_drawer"), computed.get("over_lost_computed"),
                computed.get("total_math_error"), computed.get("sales_check"),
                computed.get("math_ok", True), notes_text,
            ))
            row = cur.fetchone()
            report_id = row["id"] if row else None
            # Latest report per day+shift wins; older/corrected ones marked superseded.
            _recompute_superseded(cur, business_day, report_kind)
            return report_id


def get_daily_reports_for_day(business_day: str, active_only: bool = True) -> list[dict]:
    """Parsed reports for a business day (mid + final). active_only hides superseded."""
    where = "business_day = %s" + (" AND NOT superseded" if active_only else "")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM gm_daily_reports
                WHERE {where}
                ORDER BY posted_at NULLS LAST, id
            """, (business_day,))
            return [dict(r) for r in cur.fetchall()]


def recompute_all_superseded() -> int:
    """One-shot: recompute superseded flags across every day+shift. Returns groups processed."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT business_day, report_kind FROM gm_daily_reports")
            groups = cur.fetchall()
            for g in groups:
                _recompute_superseded(cur, str(g["business_day"]), g["report_kind"])
            return len(groups)


# ─── GM clarification escalation ladder ───────────────────────────────────────

def init_gm_clarifications_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_clarifications (
                    id              SERIAL PRIMARY KEY,
                    chat_id         BIGINT NOT NULL,
                    chat_title      TEXT,
                    topic           TEXT NOT NULL,        -- report_math | receipt_clarity
                    question_msg_id BIGINT,               -- GM's question message (replies detected on this)
                    target_msg_id   BIGINT,               -- the message being asked about
                    question_text   TEXT,
                    context_ref     TEXT,                 -- e.g. report id
                    sender_name     TEXT,
                    status          TEXT DEFAULT 'open',  -- open | checking | answered | escalated | closed
                    nudge_count     INTEGER DEFAULT 0,
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    last_nudge_at   TIMESTAMPTZ,
                    next_action_at  TIMESTAMPTZ,
                    answer_text     TEXT,
                    answered_at     TIMESTAMPTZ,
                    escalated_at    TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS idx_gm_clar_active
                    ON gm_clarifications (status) WHERE status IN ('open','checking');
                CREATE INDEX IF NOT EXISTS idx_gm_clar_qmsg
                    ON gm_clarifications (chat_id, question_msg_id);
            """)
    logger.info("GM clarifications DB ready")


def gm_create_clarification(chat_id: int, chat_title: str | None, topic: str,
                            question_msg_id: int | None, target_msg_id: int | None,
                            question_text: str, sender_name: str | None,
                            context_ref: str | None, first_nudge_after_min: int = 10) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gm_clarifications
                    (chat_id, chat_title, topic, question_msg_id, target_msg_id,
                     question_text, sender_name, context_ref, status,
                     created_at, next_action_at)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,'open',
                        NOW(), NOW() + (%s || ' minutes')::interval)
                RETURNING id
            """, (chat_id, chat_title, topic, question_msg_id, target_msg_id,
                  question_text, sender_name, context_ref, str(first_nudge_after_min)))
            return cur.fetchone()["id"]


def gm_get_active_clarifications() -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_clarifications
                WHERE status IN ('open','checking')
                ORDER BY created_at
            """)
            return [dict(r) for r in cur.fetchall()]


def gm_get_active_clarifications_for_chat(chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_clarifications
                WHERE chat_id = %s AND status IN ('open','checking')
                ORDER BY created_at
            """, (chat_id,))
            return [dict(r) for r in cur.fetchall()]


def gm_find_clarification_by_question_msg(chat_id: int, question_msg_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM gm_clarifications
                WHERE chat_id = %s AND question_msg_id = %s
                ORDER BY id DESC LIMIT 1
            """, (chat_id, question_msg_id))
            row = cur.fetchone()
            return dict(row) if row else None


def gm_record_clarification_nudge(clar_id: int, next_action_at) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_clarifications
                SET nudge_count = nudge_count + 1, last_nudge_at = NOW(),
                    next_action_at = %s
                WHERE id = %s
            """, (next_action_at, clar_id))


def gm_set_clarification_checking(clar_id: int, next_action_at) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_clarifications
                SET status = 'checking', next_action_at = %s
                WHERE id = %s AND status = 'open'
            """, (next_action_at, clar_id))


def gm_answer_clarification(clar_id: int, answer_text: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_clarifications
                SET status = 'answered', answer_text = %s, answered_at = NOW()
                WHERE id = %s
            """, (answer_text, clar_id))


def gm_escalate_clarification(clar_id: int) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_clarifications
                SET status = 'escalated', escalated_at = NOW()
                WHERE id = %s
            """, (clar_id,))


def gm_resolve_open_clarifications(chat_id: int, topic: str, answer_text: str) -> int:
    """Resolve all open/checking clarifications of a topic in a chat (e.g. a clear
    receipt arrived after a 'send again'). Returns how many were resolved."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gm_clarifications
                SET status = 'answered', answer_text = %s, answered_at = NOW()
                WHERE chat_id = %s AND topic = %s AND status IN ('open','checking')
            """, (answer_text, chat_id, topic))
            return cur.rowcount
