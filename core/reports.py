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


def staff_attendance_report(org_id, days: int = 14, tz: str = "Asia/Phnom_Penh") -> list:
    """Per-staff punctuality over the last `days` days (read-only): [{staff_id, name, total, late, on_time_rate}],
    worst-punctuality first. Names from core_staff where present, else a '#id' fallback."""
    since = (datetime.now(ZoneInfo(tz)) - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT e.staff_id sid, COALESCE(s.call_name, s.name, 'Staff #' || e.staff_id) nm, "
                "COUNT(*) total, COUNT(*) FILTER (WHERE e.detail->>'state' = 'late') late "
                "FROM attendance_events e "
                "LEFT JOIN core_staff s ON s.org_id = e.org_id AND s.staff_id = e.staff_id "
                "WHERE e.org_id = %s AND e.type = 'checked_in' AND e.at >= %s "
                "GROUP BY e.staff_id, s.call_name, s.name ORDER BY late DESC, total DESC",
                (org_id, since))
            rows = cur.fetchall()
    return [{"staff_id": r["sid"], "name": r["nm"], "total": r["total"], "late": r["late"],
             "on_time_rate": (100 * (r["total"] - r["late"]) // r["total"]) if r["total"] else 0} for r in rows]
