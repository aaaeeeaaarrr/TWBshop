"""Payroll pure logic."""
from gm_bot import payroll as pr


def test_day_pay():
    assert pr.day_pay(300) == 10.0
    assert pr.day_pay(0) == 0.0


def test_clean_month_bonus_earned():
    # salary 250, bonus 20, pay1 200, pay2 70 (incl 20 bonus); 0 no-shows
    s = pr.compute_slip(250, 20, 200, 70, 0)
    assert s["bonus_earned"] is True
    assert s["bonus_amount"] == 20.0
    assert s["deduction"] == 0.0
    assert s["pay1"] == 200.0
    assert s["pay2"] == 70.0          # base2 (70-20=50) + bonus 20


def test_no_show_cuts_pay1_and_voids_bonus():
    s = pr.compute_slip(300, 30, 240, 90, 1)   # day pay = 10
    assert s["bonus_earned"] is False
    assert s["bonus_amount"] == 0.0
    assert s["deduction"] == 10.0
    assert s["pay1"] == 230.0                  # 240 - 10
    assert s["pay2"] == 60.0                   # base2 (90-30=60) + 0 bonus
    assert any("no-show" in r for r in s["reasons"])


def test_bonus_voided_flag():
    s = pr.compute_slip(250, 20, 200, 70, 0, bonus_voided=True)
    assert s["bonus_earned"] is False and s["pay2"] == 50.0


def test_slip_line_renders():
    line = pr.slip_line("Davy", pr.compute_slip(250, 20, 200, 70, 0))
    assert "Davy" in line and "pay1" in line
