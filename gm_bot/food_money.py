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
