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
        """)
        # Migration: add customer_name to databases created before Phase 3
        try:
            conn.execute(
                "ALTER TABLE orders ADD COLUMN customer_name TEXT NOT NULL DEFAULT 'Unknown'"
            )
            conn.commit()
            logger.info("Migrated orders table: added customer_name column")
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
