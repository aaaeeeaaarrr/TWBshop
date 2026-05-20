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
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                item        TEXT NOT NULL,
                quantity    INTEGER NOT NULL DEFAULT 1,
                status      TEXT NOT NULL DEFAULT 'confirmed',
                created_at  TEXT NOT NULL
            );
        """)
    logger.info("Database initialised at %s", DB_PATH)


def save_order(user_id: int, items: list[tuple[str, int]]) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO orders (user_id, item, quantity, created_at) VALUES (?, ?, ?, ?)",
            [(user_id, item, qty, now) for item, qty in items],
        )
    logger.info("Saved order for user %s: %s", user_id, items)


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
    """Return all confirmed orders grouped by user for a given date."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT user_id, item, quantity
            FROM orders
            WHERE DATE(created_at) = ?
              AND status = 'confirmed'
            ORDER BY user_id, item
        """, (date,)).fetchall()
