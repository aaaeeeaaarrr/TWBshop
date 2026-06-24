"""core.reports — read-only trends/analytics over the platform's own data (the "Reports" frontier capability;
Salesforce Reports / ServiceNow Performance Analytics / QuickBooks reports lineage). Starts with attendance
(the data we have); expense/stock/sales reports slot in beside it as those domains record data. No writes."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db


def attendance_report(org_id, days: int = 14, tz: str = "Asia/Phnom_Penh") -> dict:
    """Daily attendance trend for the last `days` days (read-only): {daily:[{day,total,late,early,on_time}],
    total, late, on_time_rate}."""
    since = (datetime.now(ZoneInfo(tz)) - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT (at AT TIME ZONE %s)::date d, detail FROM attendance_events "
                        "WHERE org_id=%s AND type='checked_in' AND at >= %s ORDER BY d", (tz, org_id, since))
            rows = cur.fetchall()
    by_day = {}
    for r in rows:
        day = str(r["d"])
        rec = by_day.setdefault(day, {"day": day, "total": 0, "late": 0, "early": 0, "on_time": 0})
        rec["total"] += 1
        st = (r["detail"] or {}).get("state")
        if st in ("late", "early", "on_time"):
            rec[st] += 1
    daily = sorted(by_day.values(), key=lambda x: x["day"])
    total = sum(x["total"] for x in daily)
    late = sum(x["late"] for x in daily)
    return {"daily": daily, "total": total, "late": late,
            "on_time_rate": (100 * (total - late) // total) if total else 0}
