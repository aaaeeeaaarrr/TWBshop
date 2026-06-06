"""Level-1 finance reconciliation — pure logic, no DB/AI/Telegram.

Validated by hand on 5 real business days (session 28): staff post a (Cash)+(ABA)
expense sheet at midday and SambaPOS screenshots at dawn; those photo totals must
equal the typed report fields. Photo -> fields happens in ai_client (the same
single Haiku call that already checks receipt clarity); the joins happen here.

Checks:
  - cash sheet "Day Cash Expense"        == mid report cash_expense
  - cash sheet day+night (when present)  == final report cash_expense
  - sheet "ABA Expense"                  == report aba_expense
  - POS Work Period GRAND TOTAL          == final report total_sales
"""
from __future__ import annotations

TOL = 0.015  # cent-rounding tolerance


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def pick_docs(docs: list[dict]) -> tuple[dict, dict]:
    """From the day's stored docs (arrival order), choose the authoritative expense
    sheet and POS screen. Latest usable wins; Work Period screens beat Summary ones."""
    sheet: dict = {}
    pos: dict = {}
    for d in docs:
        f = d.get("fields") or {}
        if d.get("doc_type") == "expense_sheet":
            if _num(f.get("aba_expense")) is not None or _num(f.get("day_cash_expense")) is not None:
                sheet = f
        elif d.get("doc_type") == "pos_screen" and _num(f.get("grand_total")) is not None:
            if f.get("pos_kind") == "work_period" or not pos:
                pos = f
    return sheet, pos


def _check(name: str, doc_val: float | None, rep_val: float | None) -> dict:
    if doc_val is None or rep_val is None:
        return {"name": name, "doc": doc_val, "report": rep_val, "status": "missing"}
    ok = abs(doc_val - rep_val) <= TOL
    return {"name": name, "doc": doc_val, "report": rep_val,
            "status": "ok" if ok else "mismatch"}


def checks_for_day(mid_row: dict | None, final_row: dict | None,
                   docs: list[dict]) -> list[dict]:
    sheet, pos = pick_docs(docs)
    day_c = _num(sheet.get("day_cash_expense"))
    night_c = _num(sheet.get("night_cash_expense"))
    aba = _num(sheet.get("aba_expense"))
    grand = _num(pos.get("grand_total"))

    out = []
    if mid_row:
        out.append(_check("Cash sheet vs mid report", day_c, _num(mid_row.get("cash_expense"))))
    rep_for_aba = final_row or mid_row or {}
    out.append(_check("ABA sheet vs report", aba, _num(rep_for_aba.get("aba_expense"))))
    if final_row:
        if day_c is not None and night_c is not None:
            out.append(_check("Cash sheet (day+night) vs final",
                              round(day_c + night_c, 2), _num(final_row.get("cash_expense"))))
        out.append(_check("POS total vs final sales", grand, _num(final_row.get("total_sales"))))
    return out


def _fmt(v: float | None) -> str:
    return "?" if v is None else ("{:,.2f}".format(v))


def format_summary(business_day: str, checks: list[dict]) -> str:
    icons = {"ok": "✓", "mismatch": "❌", "missing": "—"}
    bad = sum(1 for c in checks if c["status"] == "mismatch")
    head = "📋 Reconciliation — %s" % business_day
    if bad:
        head += "  ⚠️ %d mismatch%s" % (bad, "es" if bad > 1 else "")
    lines = [head]
    for c in checks:
        if c["status"] == "missing":
            lines.append("— %s: no data (photo %s / report %s)"
                         % (c["name"], _fmt(c["doc"]), _fmt(c["report"])))
        else:
            lines.append("%s %s: photo %s vs report %s"
                         % (icons[c["status"]], c["name"], _fmt(c["doc"]), _fmt(c["report"])))
    return "\n".join(lines)
