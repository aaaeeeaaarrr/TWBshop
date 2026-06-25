"""core.pos — a real, minimal point-of-sale (the POS domain on the platform): record sales → revenue, and
auto-decrement Stock when the sold item is a stock item (the cross-domain integration). Org-scoped,
channel-free, own table (core_sales). NOT TWB's live POS. No model calls. Table via core.db.init_core_db."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db


def record_sale(org_id, item_id, qty, unit_price, item_name=None, actor=None) -> int:
    """Record a sale: log it AND (if it's a stock item) decrement on_hand — one transaction. Returns sale_id."""
    with _db() as conn:
        with conn.cursor() as cur:
            name = item_name
            if item_id and not name:
                cur.execute("SELECT name FROM core_stock_items WHERE org_id=%s AND item_id=%s", (org_id, item_id))
                r = cur.fetchone()
                name = r["name"] if r else None
            cur.execute("SELECT shift_id FROM core_shifts WHERE org_id=%s AND status='open'", (org_id,))
            sr = cur.fetchone()
            shift_id = sr["shift_id"] if sr else None       # the cash counts toward the open shift's drawer
            cur.execute("INSERT INTO core_sales (org_id, item_id, item_name, qty, unit_price, actor, shift_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING sale_id",
                        (org_id, item_id or None, name, qty, unit_price, actor, shift_id))
            sid = cur.fetchone()["sale_id"]
            if item_id:                                          # cross-domain: a sale reduces stock on-hand
                cur.execute("UPDATE core_stock_items SET on_hand = on_hand - %s WHERE org_id=%s AND item_id=%s",
                            (qty, org_id, item_id))
            return sid


def recent_sales(org_id, limit=50) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sale_id, item_name, qty, unit_price, sold_at FROM core_sales "
                        "WHERE org_id=%s ORDER BY sold_at DESC LIMIT %s", (org_id, int(limit)))
            return [dict(r) for r in cur.fetchall()]


def sales_summary(org_id, days: int = 30, tz: str = "Asia/Phnom_Penh") -> dict:
    """Sales over the last `days` days (read-only): {revenue, count, units}."""
    since = (datetime.now(ZoneInfo(tz)) - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n, COALESCE(SUM(qty * unit_price), 0) rev, COALESCE(SUM(qty), 0) units "
                        "FROM core_sales WHERE org_id=%s AND sold_at >= %s", (org_id, since))
            r = cur.fetchone()
    return {"revenue": float(r["rev"]), "count": r["n"], "units": float(r["units"])}
