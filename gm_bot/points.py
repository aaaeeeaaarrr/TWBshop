"""Points pure logic (session 28). No DB/Telegram.

Design (owner): RECORD raw events now (cause + quantity + timestamp); DERIVE points later from
an editable rules table so changing a value re-scores history fairly. Nothing is connected to
the bonus yet. The leaderboard resets when the owner confirms each month's 2nd pay.

points = sum over events of rule.value * quantity, counting only ACTIVE rules in the period.
"""
from __future__ import annotations

# The catalogue (seeded inactive — owner sets values + flips active later).
# cause: (default value, per-what)
CATALOGUE = {
    "early_arrival":     (10,  "per event  — arrived >5 min early (shift or payback slot)"),
    "late_informed":     (-1,  "per minute — late, told us before shift start"),
    "late_uninformed":   (-2,  "per minute — late, did not tell us before"),
    "no_show":           (-2,  "per shift minute — never arrived"),
    "return_after_doctor": (15, "per event — came in after papers (no pressure)"),
    "ot_no_show":        (-30, "per event — accepted OT then didn't do it"),
}


def event_points(cause: str, quantity: int, rules: dict) -> float:
    """Points for one event given the rules map {cause: {'value', 'active'}}."""
    r = rules.get(cause)
    if not r or not r.get("active"):
        return 0.0
    return r["value"] * quantity


def total_points(events: list[dict], rules: dict) -> float:
    """events = [{cause, quantity}]; rules = {cause: {value, active}}."""
    return round(sum(event_points(e["cause"], e.get("quantity", 1), rules) for e in events), 2)
