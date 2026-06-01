"""
Daily stock-order brain — pure logic, no DB/AI/Telegram.

From a stock-sheet reading (each item's minimum + current count, and — once learned —
its daily usage rate), decide what to order and how much, and format the 7am group
message. Also the no-sheet escalation decision.

The order-quantity formula here is a FIRST-PASS default (order back to min + a buffer,
or enough to cover lead-time usage when known). The owner will tune it on real output.
"""
from __future__ import annotations

import math

DEFAULT_BUFFER_FRAC = 0.5     # restock target = min * 1.5 by default
LEAD_DAYS = 2                 # days of cover to add when usage rate is known
NO_SHEET_ESCALATE_DAYS = 2    # 2 consecutive days with no sheet -> ask the group


def is_low(min_n, current_n) -> bool:
    """True when the current count is below the item's minimum."""
    if min_n is None or current_n is None:
        return False
    return current_n < min_n


def suggest_order_qty(min_n, current_n, usage_per_day=None,
                      lead_days: int = LEAD_DAYS,
                      buffer_frac: float = DEFAULT_BUFFER_FRAC):
    """How much to order to get comfortably back above minimum. 0 if not low.
    Target = max(min*(1+buffer), min + usage*lead_days) so fast-movers get more.
    Rounds up to a whole unit when the gap is >= 1, else keeps 2dp (fractional units)."""
    if min_n is None or current_n is None or current_n >= min_n:
        return 0
    target = min_n * (1 + buffer_frac)
    if usage_per_day:
        target = max(target, min_n + usage_per_day * lead_days)
    gap = target - current_n
    if gap <= 0:
        return 0
    return math.ceil(gap) if gap >= 1 else round(gap, 2)


def build_order_list(items: list[dict]) -> list[dict]:
    """From sheet items -> the order rows. items: [{item, unit, min_n, current_n,
    usage_per_day?}]. Returns [{item, unit, qty}] for everything below minimum,
    highest shortfall first."""
    rows = []
    for it in items:
        if not is_low(it.get("min_n"), it.get("current_n")):
            continue
        qty = suggest_order_qty(it.get("min_n"), it.get("current_n"), it.get("usage_per_day"))
        if qty and qty > 0:
            rows.append({"item": it["item"], "unit": it.get("unit") or "", "qty": qty,
                         "shortfall": it["min_n"] - it["current_n"]})
    rows.sort(key=lambda r: -r["shortfall"])
    for r in rows:
        r.pop("shortfall", None)
    return rows


def format_order_message(rows: list[dict]) -> str | None:
    """The 7am group message. None if nothing needs ordering."""
    if not rows:
        return None
    lines = ["Check if we need to order:"]
    for r in rows:
        qty = r["qty"]
        qty_str = ("%g" % qty)
        unit = (r.get("unit") or "").strip()
        prefix = ("%s %s" % (qty_str, unit)).strip()
        lines.append("- %s  %s" % (prefix, r["item"]))
    return "\n".join(lines)


def no_sheet_decision(days_missing: int) -> str:
    """'reuse' the last sheet for a 1-day gap; 'escalate' to the group at 2+ days."""
    return "escalate" if days_missing >= NO_SHEET_ESCALATE_DAYS else "reuse"


def usage_trend(recent_avg: float | None, older_avg: float | None,
                drop_frac: float = 0.3) -> str:
    """Idea: 'declining' if recent usage is >=30% below the older baseline (candidate
    off-menu / slowing item to flag to the owner), 'rising' if up a lot, else 'steady'.
    Returns 'unknown' when there isn't enough history."""
    if not recent_avg or not older_avg or older_avg <= 0:
        return "unknown"
    change = (recent_avg - older_avg) / older_avg
    if change <= -drop_frac:
        return "declining"
    if change >= drop_frac:
        return "rising"
    return "steady"
