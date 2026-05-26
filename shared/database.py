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
