"""core.insights — a cross-domain 'needs attention' feed (read-only): one place that scans every ON domain for
notable conditions (lateness spike · stock at/below par · spend spike · sales drop). Pure statistics over the
platform's own data, NO model call — the intelligence layer on top of the 5 real domains."""
from core.tenant_config import get_config
from core import reports, stock, expenses, pos


def attention_feed(org_id) -> list:
    """[{domain, msg}] across all ON domains — what needs attention right now."""
    cats = get_config(org_id).get("categories", {})
    out = []
    for a in reports.attendance_anomalies(org_id):                      # attendance: lateness spike / low turnout
        out.append({"domain": "attendance", "msg": a})
    if cats.get("stock", {}).get("enabled"):                           # stock: items at/below par
        low = stock.low_stock_items(org_id)
        if low:
            names = ", ".join(l["name"] for l in low[:5])
            out.append({"domain": "stock", "msg": "📦 %d item(s) at/below par — reorder: %s" % (len(low), names)})
        from core import investigate
        for v in stock.stock_variance(org_id):                         # stock: shrinkage (counted < book)
            who = investigate.who_in_window(org_id, v.get("since"), v.get("at"))
            suspects = (" · on shift: " + ", ".join(who)) if who else ""
            out.append({"domain": "stock",
                        "msg": "⚠️ %s SHORT by %g (book %g, counted %g) — possible shrinkage @ %s%s"
                        % (v["item"], -v["variance"], v["book"], v["counted"], v["when"], suspects)})
    if cats.get("accountant", {}).get("enabled"):                      # expenses: spend spike (last 7d vs prior 7d)
        e7 = expenses.expense_summary(org_id, 7)["total"]
        prior = expenses.expense_summary(org_id, 14)["total"] - e7
        if prior >= 1 and e7 > prior * 1.5:
            out.append({"domain": "expenses", "msg": "🍚 Spend up: $%g in the last 7 days vs $%g the prior 7." % (e7, prior)})
    if cats.get("pos", {}).get("enabled"):                             # sales: drop (last 7d vs prior 7d)
        s7 = pos.sales_summary(org_id, 7)["revenue"]
        prior = pos.sales_summary(org_id, 14)["revenue"] - s7
        if prior >= 1 and s7 < prior * 0.6:
            out.append({"domain": "sales", "msg": "🛒 Sales down: $%g in the last 7 days vs $%g the prior 7." % (s7, prior)})
    return out
