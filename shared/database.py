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
    logger.info("Database ready")


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


# ─── B2B bread orders ─────────────────────────────────────────────────────────

def save_b2b_order(group_chat_id: int, business_name: str, items: list[dict], delivery_date: str) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO b2b_orders "
                "(group_chat_id, business_name, item, quantity, grams, notes, delivery_date, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (group_chat_id, business_name, i["item"], i["qty"],
                     i.get("grams"), i.get("notes"), delivery_date, now)
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


# ─── B2B cake orders ──────────────────────────────────────────────────────────

def save_b2b_cake_order(group_chat_id: int, business_name: str, items: list[dict], delivery_date: str) -> None:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO b2b_cake_orders "
                "(group_chat_id, business_name, item, cake_category, order_type, quantity, slices, delivery_date, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (group_chat_id, business_name, i["item"], i["cake_category"],
                     i["order_type"], i["qty"], i.get("slices"), delivery_date, now)
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
                SELECT id, item, quantity, grams, notes, delivery_date, created_at
                FROM b2b_orders
                WHERE group_chat_id = %s AND status = 'confirmed' AND payment_status = 'unpaid'
                ORDER BY delivery_date, created_at
            """, (group_chat_id,))
            return cur.fetchall()


def get_unpaid_b2b_cake_orders(group_chat_id: int) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, item, cake_category, order_type, quantity, slices, delivery_date, created_at
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
) -> int:
    now = datetime.utcnow().isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO b2b_payments "
                "(group_chat_id, business_name, amount, screenshot_path, group_message_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (group_chat_id, business_name, amount, screenshot_path, group_message_id, now),
            )
            return cur.fetchone()["id"]


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
