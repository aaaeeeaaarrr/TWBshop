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


# The day ('mid') report lands ~4pm; a give at/after this hour counts toward the COMING night report.
# Configurable — the ~16:00 split is my reading of the owner's "~4pm"; confirm before go-live.
DAY_FOOD_END_HOUR = 16


def food_period_for(now):
    """Which report a food-money give counts toward (owner: 'given before a report → the coming report').
    Returns (business_day, period): period 'day' = the ~4pm mid report, 'night' = the ~5am dawn final.
    business_day reuses finance's 06:00→06:00 anchor, so an overnight give (e.g. given 23:00 or 03:00)
    files under the SAME business day as its dawn 'night' report — no split, no gap."""
    from gm_bot.finance import business_day_for
    period = "day" if 6 <= now.hour < DAY_FOOD_END_HOUR else "night"
    return business_day_for(now), period


def render_food_list(period, biz_date, rows) -> str:
    """The 'Day/Night staff food' sheet, mirroring the handwritten one: title + date + numbered
    name · amount + total. `rows` = [(name, cents), ...] in give order. Pure."""
    title = "Night staff food" if period == "night" else "Day staff food"
    date_str = biz_date.strftime("%d/%m/%y") if hasattr(biz_date, "strftime") else str(biz_date)
    lines = [f"🍚 {title}   {date_str}"]
    total = 0
    for i, (name, cents) in enumerate(rows, 1):
        total += cents
        lines.append(f"{i}. {name} · ${cents / 100:.2f}")
    lines.append(f"— total = ${total / 100:.2f}")
    return "\n".join(lines)
