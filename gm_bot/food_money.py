"""Staff meal allowance ('food money') — PURE calculation (no DB, no Telegram).

Confirmed model (owner, 2026-06-21):
  500 riel per STANDARD work hour, converted at the fixed books rate 4000៛ = $1, rounded HALF-UP to
  the cent. Standard hours = the day's SCHEDULED shift length (work_start->work_end, via
  attendance_ui.shift_len_min) — OT / payback are NOT counted; a no-show gets $0 for the day.
  Worked example: a 9-hour shift = 9 × 500 = 4,500៛ = $1.125 -> $1.13.

This module is the CONFIRMED core only. Where a give is recorded, which report it lands on, the
cash-expense tie-in, and the menu are the INTEGRATION — pending owner decisions; see
docs/ROADMAP.md "Food money". Nothing imports this yet (inert).
"""
from decimal import ROUND_HALF_UP, Decimal

RIEL_PER_HOUR = 500
KHR_PER_USD = 4000   # the fixed books rate used across accountant + finance


def food_money_cents(standard_minutes) -> int:
    """USD cents for one staffer's daily meal allowance, from their STANDARD shift length in MINUTES
    (use attendance_ui.shift_len_min(work_start, work_end)). None / <= 0 -> 0 (no-show or no shift gets
    nothing). 500៛/hour ÷ 4000, HALF-UP to the cent — 540 min (9h) -> 113¢ ($1.13). Fractional hours
    are prorated by the minute (rare; most shifts are whole hours — confirmable)."""
    if not standard_minutes or standard_minutes <= 0:
        return 0
    riel = Decimal(standard_minutes) * RIEL_PER_HOUR / 60          # standard hours × 500៛
    cents = (riel / KHR_PER_USD * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(cents)


# Report assignment is EVENT-DRIVEN, not a clock (owner: "better when report is done, not an exact time").
# A give is recorded OPEN and attaches to the next daily report STORED (gm_daily_reports). See food_money_db.


def next_report_kind(last_kind):
    """The report a fresh give will land on = the one AFTER the last stored report (they alternate). The
    gm vocabulary: 'final' = the ~5am dawn/NIGHT close, 'mid' = the ~4pm daytime/DAY report.
    'final' → 'mid' · 'mid' → 'final' · unknown → None (caller uses a generic message)."""
    if last_kind == "final":
        return "mid"
    if last_kind == "mid":
        return "final"
    return None


def food_menu_rows(arrived, given_ids):
    """The Food-allowance menu rows. `arrived` = staff who have ACTUALLY CHECKED IN (the caller passes
    only checked-in sessions) — a staffer scheduled but NOT YET ARRIVED simply isn't in `arrived`, so can
    never appear on the menu (owner's rule, 2026-06-21). Then drop anyone already given this period
    (`given_ids` → the name 'disappears'), and a staffer with no valid standard shift. Each remaining one
    gets their STANDARD-shift amount. `arrived` items: {staff_id, name, work_start, work_end}.
    Returns [(staff_id, name, amount_cents)]."""
    from gm_bot.attendance_ui import shift_len_min
    rows = []
    for a in (arrived or []):
        sid = a.get("staff_id")
        if sid in given_ids:
            continue
        cents = food_money_cents(shift_len_min(a.get("work_start"), a.get("work_end")))
        if cents <= 0:
            continue                       # no valid standard shift → not payable, not shown
        rows.append((sid, a.get("name"), cents))
    return rows


def food_list_title(report_kind) -> str:
    """'final' (dawn close) → 'Night staff food'; anything else (the daytime mid) → 'Day staff food'."""
    return "Night staff food" if report_kind == "final" else "Day staff food"


def render_food_list(report_kind, biz_date, rows) -> str:
    """The staff-food sheet, mirroring the handwritten one: title + date + numbered name · amount + total.
    `report_kind` is gm's 'mid'|'final'; `rows` = [(name, cents), ...] in give order. Pure."""
    date_str = biz_date.strftime("%d/%m/%y") if hasattr(biz_date, "strftime") else str(biz_date)
    lines = [f"🍚 {food_list_title(report_kind)}   {date_str}"]
    total = 0
    for i, (name, cents) in enumerate(rows, 1):
        total += cents
        lines.append(f"{i}. {name} · ${cents / 100:.2f}")
    lines.append(f"— total = ${total / 100:.2f}")
    return "\n".join(lines)
