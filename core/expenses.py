"""core.expenses — a real, minimal expense log (the Accountant domain on the platform): record expenses by
supplier/category + spend summaries. Org-scoped, channel-free, its OWN table (core_expenses). NOT TWB's live
accountant lane (receipt OCR etc.). No model calls. Table created by core.db.init_core_db."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db
from core import audit


def add_expense(org_id, amount, supplier=None, category=None, note=None, actor=None, client_key=None) -> int:
    """Record an expense. With a client_key, a crash-redelivery / double-tap re-applies NOTHING (returns the
    original expense_id) — the offline-queue S2 cure."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_expenses (org_id, supplier, category, amount, note, actor, client_key) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (org_id, client_key) WHERE client_key IS NOT NULL DO NOTHING RETURNING expense_id",
                        (org_id, (supplier or None), (category or None), amount, (note or None), actor, client_key))
            row = cur.fetchone()
            if row is None:                                  # idempotent replay → the original expense
                cur.execute("SELECT expense_id FROM core_expenses WHERE org_id=%s AND client_key=%s",
                            (org_id, client_key))
                return cur.fetchone()["expense_id"]
            eid = row["expense_id"]
            audit.write(org_id, actor, "expense.add", "expense", str(eid),
                        {"amount": str(amount), "supplier": supplier, "category": category}, cur=cur)
            return eid


def list_expenses(org_id, limit=50) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT expense_id, supplier, category, amount, note, spent_at FROM core_expenses "
                        "WHERE org_id=%s ORDER BY spent_at DESC LIMIT %s", (org_id, int(limit)))
            return [dict(r) for r in cur.fetchall()]


def expense_summary(org_id, days: int = 30, tz: str = "Asia/Phnom_Penh") -> dict:
    """Spend over the last `days` days (read-only): {total, count, by_category:[{category,total,count}]}."""
    since = (datetime.now(ZoneInfo(tz)) - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(category,'(uncategorised)') cat, COUNT(*) n, COALESCE(SUM(amount),0) tot "
                        "FROM core_expenses WHERE org_id=%s AND spent_at >= %s GROUP BY category ORDER BY tot DESC",
                        (org_id, since))
            rows = cur.fetchall()
    by_cat = [{"category": r["cat"], "total": float(r["tot"]), "count": r["n"]} for r in rows]
    return {"total": sum(c["total"] for c in by_cat), "count": sum(c["count"] for c in by_cat), "by_category": by_cat}
