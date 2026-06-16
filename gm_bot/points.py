"""Points pure logic (session 28). No DB/Telegram.

Design (owner): RECORD raw events now (cause + quantity + timestamp); DERIVE points later from
an editable rules table so changing a value re-scores history fairly. Nothing is connected to
the bonus yet. The leaderboard resets when the owner confirms each month's 2nd pay.

points = sum over events of rule.value * quantity, counting only ACTIVE rules in the period.
"""
from __future__ import annotations

# The catalogue — ACTIVATED with these values by the owner 2026-06-11 (was seeded inactive).
# cause: (value, per-what)
CATALOGUE = {
    "early_arrival":     (10,  "per event  — arrived >5 min early (shift or payback slot)"),
    "late_informed":     (-1,  "per minute — late, told us before shift start"),
    "late_uninformed":   (-2,  "per minute — late, did not tell us before"),
    "no_show":           (-2,  "per shift minute — never arrived"),
    "return_after_doctor": (15, "per event — came in after papers (no pressure)"),
    "ot_no_show":        (-30, "per event — accepted OT then didn't do it"),
    "short_notice_al":   (-0.1, "per affected minute — AL day requested within 7 days "
                                "(quantity = window-min × short-notice days)"),
    "late_sick_inform":  (-15, "per event — told us sick within 30 min of shift start / after it "
                               "(Late Informing; own-sick only; papers do NOT wipe it)"),
}


def split_late(late_min: int, declare_offset_min: int | None) -> tuple[int, int]:
    """OWNER RULE (Jun 11): the declaration time SPLITS the late minutes — minutes already
    elapsed before they declared stay at the uninformed rate (−2), minutes after the
    declaration earn the informed rate (−1). Declared before shift start → all informed.
    declare_offset_min = minutes AFTER shift start when they declared (≤0 = before start;
    None = never declared). Returns (uninformed_min, informed_min)."""
    late_min = max(0, int(late_min))
    if declare_offset_min is None:
        return late_min, 0
    un = max(0, min(late_min, int(declare_offset_min)))
    return un, late_min - un


def event_points(cause: str, quantity: int, rules: dict) -> float:
    """Points for one event given the rules map {cause: {'value', 'active'}}."""
    r = rules.get(cause)
    if not r or not r.get("active"):
        return 0.0
    return r["value"] * quantity


def total_points(events: list[dict], rules: dict) -> float:
    """events = [{cause, quantity}]; rules = {cause: {value, active}}."""
    return round(sum(event_points(e["cause"], e.get("quantity", 1), rules) for e in events), 2)
