"""core.pos — a real, minimal point-of-sale (the POS domain on the platform): record sales → revenue, and
auto-decrement Stock when the sold item is a stock item (the cross-domain integration). Org-scoped,
channel-free, own table (core_sales). NOT TWB's live POS. No model calls. Table via core.db.init_core_db."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db
from core import audit


def record_sale(org_id, item_id, qty, unit_price, item_name=None, actor=None, client_key=None) -> int:
    """Record a sale: log it AND (if it's a stock item) decrement on_hand — one transaction. Returns sale_id.
    With a client_key, a crash-redelivery / double-tap re-applies NOTHING (returns the original sale_id, with
    no second stock decrement) — the offline-queue S2 cure. The decrement is clamped at 0 (STOCK-NEG)."""
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
            cur.execute("INSERT INTO core_sales (org_id, item_id, item_name, qty, unit_price, actor, shift_id, "
                        "client_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (org_id, client_key) WHERE client_key IS NOT NULL DO NOTHING RETURNING sale_id",
                        (org_id, item_id or None, name, qty, unit_price, actor, shift_id, client_key))
            row = cur.fetchone()
            if row is None:                                  # idempotent replay → original sale, no re-decrement
                cur.execute("SELECT sale_id FROM core_sales WHERE org_id=%s AND client_key=%s",
                            (org_id, client_key))
                return cur.fetchone()["sale_id"]
            sid = row["sale_id"]
            if item_id:                                      # cross-domain: a sale reduces stock on-hand (≥ 0)
                cur.execute("UPDATE core_stock_items SET on_hand = GREATEST(0, on_hand - %s) "
                            "WHERE org_id=%s AND item_id=%s", (qty, org_id, item_id))
            return sid


def void_sale(org_id, sale_id, actor=None, reason=None):
    """Void a sale — the S1 inverse of record_sale, single-void by construction. ONE transaction: claim the
    sale (a 2nd void is rejected), give the stock back, and (if a shift is open) record a 'refund' drawer
    event so the till reconciles + a same-txn audit row. Returns (info|None, error). Revenue (sales_summary)
    then excludes the voided sale; the drawer nets to zero via the refund event."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_sales SET voided_at=NOW() WHERE org_id=%s AND sale_id=%s "
                        "AND voided_at IS NULL RETURNING item_id, qty, unit_price", (org_id, sale_id))
            row = cur.fetchone()
            if row is None:
                return None, "not_found_or_already_voided"
            amount = float(row["qty"]) * float(row["unit_price"])
            if row["item_id"]:                               # S1: give the stock back
                cur.execute("UPDATE core_stock_items SET on_hand = on_hand + %s WHERE org_id=%s AND item_id=%s",
                            (row["qty"], org_id, row["item_id"]))
            cur.execute("SELECT shift_id FROM core_shifts WHERE org_id=%s AND status='open'", (org_id,))
            sr = cur.fetchone()
            shift_id = sr["shift_id"] if sr else None
            if shift_id:                                     # cash goes back out of the open drawer
                cur.execute("INSERT INTO core_cash_events (org_id, shift_id, type, amount, note, actor) "
                            "VALUES (%s,%s,'refund',%s,%s,%s)",
                            (org_id, shift_id, amount, reason or ("void sale %s" % sale_id), actor))
            audit.write(org_id, actor, "sale.voided", "sale", str(sale_id),
                        {"amount": str(amount), "item_id": row["item_id"], "reason": reason}, cur=cur)
            return {"sale_id": sale_id, "amount": amount,
                    "restocked": float(row["qty"]) if row["item_id"] else 0.0,
                    "drawer_refund": bool(shift_id)}, None


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
                        "FROM core_sales WHERE org_id=%s AND sold_at >= %s AND voided_at IS NULL", (org_id, since))
            r = cur.fetchone()
    return {"revenue": float(r["rev"]), "count": r["n"], "units": float(r["units"])}
