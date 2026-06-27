"""core.optimize — the "what the system handled for you" outcome view (Fin-inspired, lean + HONEST).

Read-only: it counts the work the platform did AUTOMATICALLY over a period, per area, from the tenant's own
data — so a client can SEE the value ("the system handled N things you'd otherwise do by hand"). No vanity
maths: every number traces to a real query. Areas appear only when their domain is on / has data.
"""
from core.tenant_config import get_config

_REQUEST_KINDS = ["al", "sick", "ot", "swap", "special_leave", "dayoff_move"]


def automation_summary(org_id, days: int = 30) -> list:
    """Per-area automation outcomes: [{area, auto, of, label}] — `auto`/`of` give a fraction where one is
    meaningful (else auto==of). Pulls only from functions we already have; each area is gated on its domain."""
    cfg = get_config(org_id)
    cats = cfg.get("categories", {})
    out = []

    # Attendance — every check-in is auto-classified on-time/late/early with no manual timekeeping.
    from core import reports
    rep = reports.attendance_report(org_id, days)
    if rep["total"]:
        out.append({"area": "Attendance", "auto": rep["total"], "of": rep["total"],
                    "label": "%d check-ins auto-classified — no manual timekeeping" % rep["total"]})

    # Approvals — how many request types the bot decides automatically (vs a human).
    appr = cats.get("attendance", {}).get("approvals", {}) or {}
    if appr:
        bot_kinds = [k for k in _REQUEST_KINDS if (appr.get(k) or {}).get("by") == "bot"]
        out.append({"area": "Approvals", "auto": len(bot_kinds), "of": len(_REQUEST_KINDS),
                    "label": "%d of %d request types decided automatically by the bot"
                             % (len(bot_kinds), len(_REQUEST_KINDS))})

    # Monitoring — issues auto-surfaced across all on domains (the attention feed).
    from core import insights
    feed = insights.attention_feed(org_id)
    out.append({"area": "Monitoring", "auto": len(feed), "of": len(feed),
                "label": "%d issue(s) auto-surfaced across your domains" % len(feed)})

    # Stock — low-stock reorder nudges auto-generated.
    if cats.get("stock", {}).get("enabled"):
        from core import stock
        low = stock.low_stock_items(org_id)
        out.append({"area": "Stock", "auto": len(low), "of": len(low),
                    "label": "%d low-stock item(s) auto-flagged for reorder" % len(low)})

    # Automations — alerts auto-dispatched in the period (if any custom/recipe automations are live).
    try:
        from core import automations
        if hasattr(automations, "dispatch_count"):
            n = automations.dispatch_count(org_id, days)
            if n:
                out.append({"area": "Automations", "auto": n, "of": n,
                            "label": "%d alert(s) auto-sent by your automations" % n})
    except Exception:
        pass

    return out


def headline(org_id, days: int = 30) -> str:
    """One-line summary for the dashboard: the total count of auto-handled items this period."""
    total = sum(a["auto"] for a in automation_summary(org_id, days))
    return "The system handled %d thing(s) automatically in the last %d days." % (total, days)
