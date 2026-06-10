"""Payroll pure logic (session 28). No DB/Telegram.

Slips named by MONTH OF WORK (May#1 paid Jun 1, May#2 paid Jun 15). Pay cuts come from the
FIRST pay. No-show = 1 day's pay cut + bonus not earned. Bonus language = earned/not-earned only.
Owner reviews ONE table, edits, approves & sends. (This module = the math; UI in bot.py.)
"""
from __future__ import annotations

DAYS_IN_MONTH = 30   # day-pay basis — OWNER RULE (Jun 2026): ALWAYS 30, even in 31-day months.
                     # Proration for a mid-month joiner = salary × (30 − days missed)/30, missed
                     # days counted from the 1st. 1st pay = 80% of (prorated) salary rounded UP
                     # to the next 5/0; 2nd = remainder; bonus rides the 2nd, not prorated.


def day_pay(salary: float) -> float:
    return round((salary or 0) / DAYS_IN_MONTH, 2)


def compute_slip(salary: float, bonus: float, first_pay: float, second_pay: float,
                 no_show_count: int, bonus_voided: bool = False) -> dict:
    """Compute a staff payslip for a work-month.
    - deductions = no_show_count × day_pay, taken from the FIRST pay.
    - bonus earned only if no no-shows AND not otherwise voided.
    Returns {salary, bonus_earned, bonus_amount, deduction, pay1, pay2, reasons}."""
    dp = day_pay(salary)
    deduction = round(no_show_count * dp, 2)
    bonus_earned = (no_show_count == 0) and not bonus_voided
    bonus_amount = round(bonus, 2) if bonus_earned else 0.0
    pay1 = round((first_pay or 0) - deduction, 2)
    # second pay carries the bonus (the surprise reveal); if bonus not earned it's just the base
    base2 = round((second_pay or 0) - (bonus or 0), 2)   # strip the bonus that was baked into pay2
    pay2 = round(base2 + bonus_amount, 2)
    reasons = []
    if no_show_count:
        reasons.append("%d no-show day(s) → −$%.2f" % (no_show_count, deduction))
    if not bonus_earned:
        reasons.append("bonus not earned this time")
    return {"salary": salary, "bonus_earned": bonus_earned, "bonus_amount": bonus_amount,
            "deduction": deduction, "pay1": pay1, "pay2": pay2, "reasons": reasons}


def slip_line(name: str, slip: dict) -> str:
    b = ("✓$%.2f" % slip["bonus_amount"]) if slip["bonus_earned"] else "not earned"
    tail = (" — " + "; ".join(slip["reasons"])) if slip["reasons"] else ""
    return "%-14s pay1 $%.2f · pay2 $%.2f · bonus %s%s" % (name[:14], slip["pay1"], slip["pay2"], b, tail)
