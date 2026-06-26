"""core.ask — "Ask your business": a natural-language question → a real answer over the tenant's OWN live data.

Fin-inspired, but grounded in *operational* data (today's check-ins, real sales, stock variance) rather than
support docs — and LEAN. The COMPUTER tier is a keyword intent-router straight to the reports/insights functions
we already built (no API cost). If nothing matches AND the tenant's AI-power is ai/mixed, it escalates to the
model (the AI tier, via shared.ai_client.ask_business) with a compact, grounded data snapshot.
"""
from core.tenant_config import get_config


def _has(q, *words):
    return any(w in q for w in words)


def ask(org_id, question) -> dict:
    """Answer a question over the tenant's data. Returns {tier, answer, source}; tier ∈ computer | ai | none."""
    q = (question or "").lower().strip()
    if not q:
        return {"tier": "none", "answer": "Ask me something — e.g. 'how many late this week?'", "source": ""}

    from core import reports, pos, stock, expenses, insights, attendance, payroll, investigate

    if _has(q, "attention", "wrong", "problem", "issue", "alert", "anything off", "needs"):
        feed = insights.attention_feed(org_id)
        ans = "\n".join("• " + a["msg"] for a in feed) if feed else "Nothing needs attention right now. 👍"
        return {"tier": "computer", "answer": ans, "source": "needs-attention feed"}

    if _has(q, "shrink", "missing", "theft", "variance") or ("short" in q and _has(q, "stock", "item")):
        v = stock.stock_variance(org_id)
        ans = ("\n".join("• %s short by %g (book %g, counted %g) @ %s"
                         % (x["item"], -x["variance"], x["book"], x["counted"], x["when"]) for x in v)
               if v else "No stock shortfalls at the last count. 👍")
        return {"tier": "computer", "answer": ans, "source": "stock variance"}

    if _has(q, "low stock", "reorder", "run out", "par", "restock", "running low"):
        low = stock.low_stock_items(org_id)
        ans = ("%d item(s) at/below par: %s"
               % (len(low), ", ".join("%s (%g)" % (l["name"], float(l["on_hand"] or 0)) for l in low))
               if low else "Nothing below par. 👍")
        return {"tier": "computer", "answer": ans, "source": "stock par levels"}

    if _has(q, "stock", "inventory"):
        s = stock.stock_summary(org_id)
        return {"tier": "computer", "answer": "%d items, %d low, $%g on-hand value."
                % (s["item_count"], s["low_count"], s["total_value"]), "source": "stock summary"}

    if _has(q, "late", "lateness", "on time", "on-time", "punctual", "tardy"):
        rep = reports.attendance_report(org_id, 7)
        return {"tier": "computer", "answer": "Last 7 days: %d check-ins, %d late, %d%% on-time."
                % (rep["total"], rep["late"], rep["on_time_rate"]), "source": "attendance (7d)"}

    if _has(q, "working", "on shift", "present", "clocked", "who is", "who's", "whos", "in today", "here today"):
        ts = attendance.today_summary(org_id)
        ans = "%d staff checked in today, %d late." % (ts["in"], ts["late"])
        if "who" in q:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("Asia/Phnom_Penh")).strftime("%Y-%m-%d")
            ppl = investigate.who_present_on(org_id, today)
            if ppl:
                ans += " — " + ", ".join(p["name"] for p in ppl)
        return {"tier": "computer", "answer": ans, "source": "attendance today"}

    if _has(q, "sale", "sales", "revenue", "sold", "takings", "earned"):
        ps = pos.sales_summary(org_id, 30)
        return {"tier": "computer", "answer": "Last 30 days: $%g revenue, %d sales, %g units."
                % (ps["revenue"], ps["count"], ps["units"]), "source": "POS sales (30d)"}

    if _has(q, "spend", "spent", "expense", "expenses", "cost", "bought", "outgoing"):
        es = expenses.expense_summary(org_id, 30)
        cats = ", ".join("%s $%g" % (c["category"], c["total"]) for c in es["by_category"][:4])
        return {"tier": "computer", "answer": "Last 30 days: $%g spent over %d expenses. Top: %s"
                % (es["total"], es["count"], cats or "—"), "source": "expenses (30d)"}

    if _has(q, "payroll", "pay run", "salary", "salaries", "payslip", "wages", "wage bill"):
        lr = payroll.latest_run(org_id)
        ans = "Last pay run: $%g (%s)." % (float(lr["total"]), lr["period"]) if lr else "No pay runs yet."
        return {"tier": "computer", "answer": ans, "source": "payroll"}

    # Nothing matched → AI tier (only when the tenant's AI-power allows it; otherwise guide them).
    if get_config(org_id).get("ai_power", "computer") in ("ai", "mixed"):
        return _ai_answer(org_id, question)
    return {"tier": "none",
            "answer": "I can answer about lateness, who's on shift, sales, expenses, stock (low · value · "
                      "shrinkage), payroll, and what needs attention. For free-form questions, switch AI power to "
                      "'AI' on the AI-assist card.", "source": ""}


def _ai_answer(org_id, question) -> dict:
    """AI tier — hand the question + a grounded data snapshot to the model. Only reached when AI power = ai/mixed."""
    try:
        import asyncio
        from shared import ai_client
        from core import insights, pos, stock, expenses
        snap = []
        feed = insights.attention_feed(org_id)
        snap.append("Needs attention: " + ("; ".join(a["msg"] for a in feed) if feed else "nothing"))
        ss = stock.stock_summary(org_id)
        snap.append("Stock: %d items, %d low, $%g value" % (ss["item_count"], ss["low_count"], ss["total_value"]))
        snap.append("Sales 30d: $%g" % pos.sales_summary(org_id, 30)["revenue"])
        snap.append("Spend 30d: $%g" % expenses.expense_summary(org_id, 30)["total"])
        ans = asyncio.run(ai_client.ask_business(question, "\n".join(snap)))
        return {"tier": "ai", "answer": ans, "source": "AI (model, grounded)"}
    except Exception as exc:
        return {"tier": "ai", "answer": "AI tier is on but unavailable (%s)." % type(exc).__name__, "source": ""}
