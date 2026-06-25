"""core.investigate — the Investigation / loss-prevention card: forensic queries that pinpoint WHEN something
happened and WHO was around, so the owner can jump straight to the camera footage. Cross-domain (attendance +
stock + sales + expenses) — our edge over single-domain video-POS tools (Solink/Envysion/DTT). Read-only."""
from datetime import timedelta

from shared.database import _db


def _g(x):
    return ("%g" % float(x)) if x is not None else ""


def who_present_on(org_id, date_str, tz: str = "Asia/Phnom_Penh") -> list:
    """Who had attendance on a given date (YYYY-MM-DD): [{staff_id, name, events:[{type, at}]}] — who was around
    and when (the camera-check anchor: 'these 3 were on shift then')."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT e.staff_id sid, COALESCE(s.call_name, s.name, 'Staff #' || e.staff_id) nm, "
                        "e.type, to_char(e.at AT TIME ZONE %s, 'HH24:MI') t "
                        "FROM attendance_events e "
                        "LEFT JOIN core_staff s ON s.org_id=e.org_id AND s.staff_id=e.staff_id "
                        "WHERE e.org_id=%s AND (e.at AT TIME ZONE %s)::date = %s ORDER BY e.at",
                        (tz, org_id, tz, date_str))
            rows = cur.fetchall()
    by_staff = {}
    for r in rows:
        d = by_staff.setdefault(r["sid"], {"staff_id": r["sid"], "name": r["nm"], "events": []})
        d["events"].append({"type": r["type"], "at": r["t"]})
    return list(by_staff.values())


def who_in_window(org_id, from_at, to_at) -> list:
    """Staff who checked in within [from_at, to_at] — the 'suspects' for a shrinkage window. Names only."""
    if not from_at or not to_at:
        return []
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT COALESCE(s.call_name, s.name, 'Staff #' || e.staff_id) nm "
                        "FROM attendance_events e "
                        "LEFT JOIN core_staff s ON s.org_id=e.org_id AND s.staff_id=e.staff_id "
                        "WHERE e.org_id=%s AND e.type='checked_in' AND e.at >= %s AND e.at <= %s ORDER BY nm",
                        (org_id, from_at, to_at))
            return [r["nm"] for r in cur.fetchall()]


def unattended_activity(org_id, days: int = 14, limit: int = 100) -> list:
    """Sales/counts recorded when NO staff was clocked in around that time (~16h before → 2h after) — after-hours
    / unattended actions to review: [{when, what, by}]. A staffer working a shift would have checked in."""
    out = []
    win = "(%s::text || ' days')::interval"
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sold_at at, 'sale' kind, item_name nm, qty, actor FROM core_sales "
                        "WHERE org_id=%s AND sold_at >= NOW() - " + win + " "
                        "UNION ALL "
                        "SELECT counted_at at, 'count' kind, NULL nm, qty, actor FROM core_stock_counts "
                        "WHERE org_id=%s AND counted_at >= NOW() - " + win + " "
                        "ORDER BY at DESC LIMIT %s", (org_id, days, org_id, days, int(limit)))
            rows = cur.fetchall()
    for r in rows:
        at = r["at"]
        if not who_in_window(org_id, at - timedelta(hours=16), at + timedelta(hours=2)):
            what = ("🛒 sold %s x%s" % (r["nm"] or "?", _g(r["qty"]))) if r["kind"] == "sale" \
                else ("📦 stock count → %s" % _g(r["qty"]))
            out.append({"when": str(at)[:16], "what": what, "by": r["actor"] or "—"})
    return out


def repeat_offenders(org_id) -> list:
    """Across ALL stock shortfalls (every count that came up short of book), tally who was on shift in each
    window → [{name, count}] ranked. The correlation: who keeps being around when stock goes missing."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT c.qty, c.book_before, c.counted_at, "
                        "(SELECT MAX(c2.counted_at) FROM core_stock_counts c2 WHERE c2.org_id=c.org_id "
                        " AND c2.item_id=c.item_id AND c2.counted_at < c.counted_at) prev_at "
                        "FROM core_stock_counts c WHERE c.org_id=%s AND c.book_before IS NOT NULL "
                        "AND c.qty < c.book_before", (org_id,))
            shorts = cur.fetchall()
    tally = {}
    for s in shorts:
        for nm in who_in_window(org_id, s["prev_at"], s["counted_at"]):
            tally[nm] = tally.get(nm, 0) + 1
    return sorted([{"name": k, "count": v} for k, v in tally.items()], key=lambda x: -x["count"])


def item_timeline(org_id, item_id, limit: int = 50) -> list:
    """A per-item forensic timeline (counts + sales), newest first: [{kind, when, detail, by}] — when an item was
    last counted/sold and by whom."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 'count' kind, counted_at at, qty, NULL::numeric price, actor FROM core_stock_counts "
                        "WHERE org_id=%s AND item_id=%s "
                        "UNION ALL "
                        "SELECT 'sale' kind, sold_at at, qty, unit_price price, actor FROM core_sales "
                        "WHERE org_id=%s AND item_id=%s "
                        "ORDER BY at DESC LIMIT %s", (org_id, item_id, org_id, item_id, int(limit)))
            rows = cur.fetchall()
    out = []
    for r in rows:
        detail = ("counted → %s" % _g(r["qty"])) if r["kind"] == "count" \
            else ("sold %s @ %s" % (_g(r["qty"]), _g(r["price"])))
        out.append({"kind": r["kind"], "when": str(r["at"])[:16], "detail": detail, "by": r["actor"] or "—"})
    return out


def activity_timeline(org_id, hours: int = 48) -> list:
    """A unified recent-events feed across domains (last `hours`), newest first: [{when, what, by}] — 'what
    happened around then' for a camera sweep."""
    out = []
    win = "(%s::text || ' hours')::interval"
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT e.at, e.type, COALESCE(s.call_name, s.name, 'Staff #' || e.staff_id) nm "
                        "FROM attendance_events e "
                        "LEFT JOIN core_staff s ON s.org_id=e.org_id AND s.staff_id=e.staff_id "
                        "WHERE e.org_id=%s AND e.at >= NOW() - " + win, (org_id, hours))
            for r in cur.fetchall():
                out.append((r["at"], "⏱️ %s %s" % (r["nm"], r["type"].replace("_", " ")), "—"))
            cur.execute("SELECT c.counted_at at, i.name nm, c.qty, c.actor FROM core_stock_counts c "
                        "LEFT JOIN core_stock_items i ON i.org_id=c.org_id AND i.item_id=c.item_id "
                        "WHERE c.org_id=%s AND c.counted_at >= NOW() - " + win, (org_id, hours))
            for r in cur.fetchall():
                out.append((r["at"], "📦 counted %s → %s" % (r["nm"] or "?", _g(r["qty"])), r["actor"] or "—"))
            cur.execute("SELECT sold_at at, item_name nm, qty, actor FROM core_sales "
                        "WHERE org_id=%s AND sold_at >= NOW() - " + win, (org_id, hours))
            for r in cur.fetchall():
                out.append((r["at"], "🛒 sold %s x%s" % (r["nm"] or "?", _g(r["qty"])), r["actor"] or "—"))
            cur.execute("SELECT spent_at at, supplier sup, amount, actor FROM core_expenses "
                        "WHERE org_id=%s AND spent_at >= NOW() - " + win, (org_id, hours))
            for r in cur.fetchall():
                out.append((r["at"], "🍚 expense $%s %s" % (_g(r["amount"]), r["sup"] or ""), r["actor"] or "—"))
    out.sort(key=lambda x: x[0], reverse=True)
    return [{"when": str(w)[:16], "what": what, "by": by} for w, what, by in out]
