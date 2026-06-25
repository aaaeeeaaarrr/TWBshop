"""core.expenses — a real, minimal expense log (the Accountant domain on the platform): record expenses by
supplier/category + spend summaries. Org-scoped, channel-free, its OWN table (core_expenses). NOT TWB's live
accountant lane (receipt OCR etc.). No model calls. Table created by core.db.init_core_db."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db


def add_expense(org_id, amount, supplier=None, category=None, note=None, actor=None) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_expenses (org_id, supplier, category, amount, note, actor) "
                        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING expense_id",
                        (org_id, (supplier or None), (category or None), amount, (note or None), actor))
            return cur.fetchone()["expense_id"]


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
