"""SQLite setup and all read/write functions."""

import sqlite3
import logging
from datetime import datetime

DB_PATH = "twbshop.db"
logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                customer_name TEXT    NOT NULL DEFAULT 'Unknown',
                item          TEXT    NOT NULL,
                quantity      INTEGER NOT NULL DEFAULT 1,
                status        TEXT    NOT NULL DEFAULT 'confirmed',
                created_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS photo_submissions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                staff_name   TEXT    NOT NULL,
                photo_type   TEXT    NOT NULL,
                file_path    TEXT    NOT NULL,
                submitted_at TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS b2b_cake_orders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                group_chat_id INTEGER NOT NULL,
                business_name TEXT    NOT NULL,
                item          TEXT    NOT NULL,
                cake_category TEXT    NOT NULL,
                order_type    TEXT    NOT NULL,
                quantity      INTEGER NOT NULL DEFAULT 1,
                slices        INTEGER,
                delivery_date TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'confirmed',
                created_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS b2b_customers (
                group_chat_id   INTEGER PRIMARY KEY,
                business_name   TEXT    NOT NULL,
                delivery_method TEXT,
                delivery_time   TEXT,
                location        TEXT,
                updated_at      TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS b2b_orders (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                group_chat_id  INTEGER NOT NULL,
                business_name  TEXT    NOT NULL,
                item           TEXT    NOT NULL,
                quantity       INTEGER NOT NULL DEFAULT 1,
                grams          INTEGER,
                notes          TEXT,
                delivery_date  TEXT    NOT NULL DEFAULT '',
                status         TEXT    NOT NULL DEFAULT 'confirmed',
                payment_status TEXT    NOT NULL DEFAULT 'unpaid',
                created_at     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS b2b_payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                group_chat_id   INTEGER NOT NULL,
                business_name   TEXT    NOT NULL,
                amount          REAL    NOT NULL DEFAULT 0,
                screenshot_path TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                applied_at      TEXT,
                created_at      TEXT    NOT NULL
            );
        """)
        # Migration: add delivery_date to b2b_orders for databases created before this change
        try:
            conn.execute("ALTER TABLE b2b_orders ADD COLUMN delivery_date TEXT NOT NULL DEFAULT ''")
            conn.commit()
            logger.info("Migrated b2b_orders table: added delivery_date column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: add customer_name to databases created before Phase 3
        try:
            conn.execute(
                "ALTER TABLE orders ADD COLUMN customer_name TEXT NOT NULL DEFAULT 'Unknown'"
            )
            conn.commit()
            logger.info("Migrated orders table: added customer_name column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        for _migration_sql, _migration_label in [
            ("ALTER TABLE b2b_orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid'",
             "b2b_orders.payment_status"),
            ("ALTER TABLE b2b_cake_orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'unpaid'",
             "b2b_cake_orders.payment_status"),
            ("ALTER TABLE b2b_payments ADD COLUMN group_message_id INTEGER",
             "b2b_payments.group_message_id"),
        ]:
            try:
                conn.execute(_migration_sql)
                conn.commit()
                logger.info("Migrated: added %s column", _migration_label)
            except sqlite3.OperationalError:
                pass  # Column already exists

    logger.info("Database ready at %s", DB_PATH)


def save_order(user_id: int, customer_name: str, items: list[tuple[str, int]]) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO orders (user_id, customer_name, item, quantity, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, customer_name, item, qty, now) for item, qty in items],
        )
    logger.info("Saved order for %s (id=%s): %s", customer_name, user_id, items)


def get_daily_totals(date: str) -> list[sqlite3.Row]:
    """Return aggregated item totals for a given date (YYYY-MM-DD)."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT item, SUM(quantity) AS total
            FROM orders
            WHERE DATE(created_at) = ?
              AND status = 'confirmed'
            GROUP BY item
            ORDER BY item
        """, (date,)).fetchall()


def save_photo_submission(user_id: int, staff_name: str, photo_type: str, file_path: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO photo_submissions (user_id, staff_name, photo_type, file_path, submitted_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, staff_name, photo_type, file_path, now),
        )
    logger.info("Photo submission saved: %s by %s (%s)", photo_type, staff_name, user_id)


def get_submissions_today(photo_type: str, date: str) -> list[sqlite3.Row]:
    """Return all submissions of a given type for a given date (YYYY-MM-DD)."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT user_id, staff_name, file_path, submitted_at
            FROM photo_submissions
            WHERE photo_type = ?
              AND DATE(submitted_at) = ?
        """, (photo_type, date)).fetchall()


def get_orders_by_user(date: str) -> list[sqlite3.Row]:
    """Return all confirmed orders for a given date, one row per line item."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT user_id, customer_name, item, quantity
            FROM orders
            WHERE DATE(created_at) = ?
              AND status = 'confirmed'
            ORDER BY customer_name, item
        """, (date,)).fetchall()


# ─── B2B ─────────────────────────────────────────────────────────────────────

def upsert_b2b_customer(
    group_chat_id: int,
    business_name: str,
    delivery_method: str | None = None,
    delivery_time: str | None = None,
    location: str | None = None,
) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO b2b_customers (group_chat_id, business_name, delivery_method, delivery_time, location, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_chat_id) DO UPDATE SET
                business_name   = excluded.business_name,
                delivery_method = COALESCE(excluded.delivery_method, delivery_method),
                delivery_time   = COALESCE(excluded.delivery_time,   delivery_time),
                location        = COALESCE(excluded.location,        location),
                updated_at      = excluded.updated_at
        """, (group_chat_id, business_name, delivery_method, delivery_time, location, now))


def get_b2b_customer(group_chat_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM b2b_customers WHERE group_chat_id = ?", (group_chat_id,)
        ).fetchone()


def save_b2b_order(group_chat_id: int, business_name: str, items: list[dict], delivery_date: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO b2b_orders "
            "(group_chat_id, business_name, item, quantity, grams, notes, delivery_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (group_chat_id, business_name, i["item"], i["qty"],
                 i.get("grams"), i.get("notes"), delivery_date, now)
                for i in items
            ],
        )
    logger.info("Saved B2B order for %s (%s) delivery %s: %s", business_name, group_chat_id, delivery_date, items)


def get_b2b_orders_for_date(group_chat_id: int, delivery_date: str) -> list[sqlite3.Row]:
    """Return confirmed orders for a group on a given delivery date."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT item, quantity, grams, notes
            FROM b2b_orders
            WHERE group_chat_id = ? AND delivery_date = ? AND status = 'confirmed'
            ORDER BY created_at
        """, (group_chat_id, delivery_date)).fetchall()


def get_b2b_last_order_item(group_chat_id: int, item: str) -> sqlite3.Row | None:
    """Return grams and notes from the most recent confirmed order of this item for the group."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT grams, notes
            FROM b2b_orders
            WHERE group_chat_id = ? AND item = ? AND status = 'confirmed'
            ORDER BY created_at DESC
            LIMIT 1
        """, (group_chat_id, item)).fetchone()


def get_b2b_daily_totals(delivery_date: str) -> list[sqlite3.Row]:
    """Return aggregated production totals for a given delivery date."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT item, SUM(quantity) AS total
            FROM b2b_orders
            WHERE delivery_date = ? AND status = 'confirmed'
            GROUP BY item
            ORDER BY item
        """, (delivery_date,)).fetchall()


def save_b2b_cake_order(group_chat_id: int, business_name: str, items: list[dict], delivery_date: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO b2b_cake_orders "
            "(group_chat_id, business_name, item, cake_category, order_type, quantity, slices, delivery_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (group_chat_id, business_name, i["item"], i["cake_category"],
                 i["order_type"], i["qty"], i.get("slices"), delivery_date, now)
                for i in items
            ],
        )
    logger.info("Saved B2B cake order for %s (%s) delivery %s: %s", business_name, group_chat_id, delivery_date, items)


def get_b2b_cake_orders_for_date(group_chat_id: int, delivery_date: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT item, cake_category, order_type, quantity, slices
            FROM b2b_cake_orders
            WHERE group_chat_id = ? AND delivery_date = ? AND status = 'confirmed'
            ORDER BY created_at
        """, (group_chat_id, delivery_date)).fetchall()


def get_b2b_cake_last_order_item(group_chat_id: int, item: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("""
            SELECT order_type, slices
            FROM b2b_cake_orders
            WHERE group_chat_id = ? AND item = ? AND status = 'confirmed'
            ORDER BY created_at DESC
            LIMIT 1
        """, (group_chat_id, item)).fetchone()


def get_b2b_cake_orders_by_group(delivery_date: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT group_chat_id, business_name, item, cake_category, order_type, quantity, slices
            FROM b2b_cake_orders
            WHERE delivery_date = ? AND status = 'confirmed'
            ORDER BY business_name, item
        """, (delivery_date,)).fetchall()


def get_b2b_orders_by_group(delivery_date: str) -> list[sqlite3.Row]:
    """Return all confirmed orders for a delivery date, grouped by business."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT group_chat_id, business_name, item, quantity, grams, notes
            FROM b2b_orders
            WHERE delivery_date = ? AND status = 'confirmed'
            ORDER BY business_name, item
        """, (delivery_date,)).fetchall()


def get_b2b_mini_orders_for_reminder(delivery_date: str, mini_items: tuple[str, ...]) -> list[sqlite3.Row]:
    """Return confirmed mini-item orders for a given delivery date (for 48h-before reminder)."""
    placeholders = ",".join("?" * len(mini_items))
    with get_connection() as conn:
        return conn.execute(f"""
            SELECT group_chat_id, business_name, item, quantity
            FROM b2b_orders
            WHERE delivery_date = ? AND status = 'confirmed'
              AND item IN ({placeholders})
            ORDER BY business_name, item
        """, (delivery_date, *mini_items)).fetchall()


def get_b2b_cake_daily_totals(delivery_date: str) -> list[sqlite3.Row]:
    """Return aggregated cake production totals for a given delivery date."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT item, cake_category, order_type, SUM(quantity) AS total, slices
            FROM b2b_cake_orders
            WHERE delivery_date = ? AND status = 'confirmed'
            GROUP BY item, order_type, slices
            ORDER BY item, order_type
        """, (delivery_date,)).fetchall()


# ─── Billing ──────────────────────────────────────────────────────────────────

def get_unpaid_b2b_orders(group_chat_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, item, quantity, grams, notes, delivery_date, created_at
            FROM b2b_orders
            WHERE group_chat_id = ? AND status = 'confirmed' AND payment_status = 'unpaid'
            ORDER BY delivery_date, created_at
        """, (group_chat_id,)).fetchall()


def get_unpaid_b2b_cake_orders(group_chat_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, item, cake_category, order_type, quantity, slices, delivery_date, created_at
            FROM b2b_cake_orders
            WHERE group_chat_id = ? AND status = 'confirmed' AND payment_status = 'unpaid'
            ORDER BY delivery_date, created_at
        """, (group_chat_id,)).fetchall()


def get_groups_with_unpaid_orders() -> list[sqlite3.Row]:
    """All groups that have any unpaid confirmed orders (bread or cake)."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT DISTINCT group_chat_id, business_name FROM b2b_orders
            WHERE status = 'confirmed' AND payment_status = 'unpaid'
            UNION
            SELECT DISTINCT group_chat_id, business_name FROM b2b_cake_orders
            WHERE status = 'confirmed' AND payment_status = 'unpaid'
            ORDER BY business_name
        """).fetchall()


def get_groups_with_unpaid_on_date(delivery_date: str) -> list[sqlite3.Row]:
    """Groups with unpaid orders for a specific delivery date."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT DISTINCT group_chat_id, business_name FROM b2b_orders
            WHERE delivery_date = ? AND status = 'confirmed' AND payment_status = 'unpaid'
            UNION
            SELECT DISTINCT group_chat_id, business_name FROM b2b_cake_orders
            WHERE delivery_date = ? AND status = 'confirmed' AND payment_status = 'unpaid'
            ORDER BY business_name
        """, (delivery_date, delivery_date)).fetchall()


def mark_b2b_orders_paid(order_ids: list[int]) -> None:
    placeholders = ",".join("?" * len(order_ids))
    with get_connection() as conn:
        conn.execute(
            f"UPDATE b2b_orders SET payment_status = 'paid' WHERE id IN ({placeholders})",
            order_ids,
        )


def mark_b2b_cake_orders_paid(order_ids: list[int]) -> None:
    placeholders = ",".join("?" * len(order_ids))
    with get_connection() as conn:
        conn.execute(
            f"UPDATE b2b_cake_orders SET payment_status = 'paid' WHERE id IN ({placeholders})",
            order_ids,
        )


def save_b2b_payment(group_chat_id: int, business_name: str, amount: float, screenshot_path: str | None, group_message_id: int | None = None) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO b2b_payments (group_chat_id, business_name, amount, screenshot_path, group_message_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (group_chat_id, business_name, amount, screenshot_path, group_message_id, now),
        )
        return cursor.lastrowid


def get_b2b_payment(payment_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM b2b_payments WHERE id = ?", (payment_id,)
        ).fetchone()


def update_b2b_payment_status(payment_id: int, status: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE b2b_payments SET status = ?, applied_at = ? WHERE id = ?",
            (status, now, payment_id),
        )
