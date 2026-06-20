"""Food-money calc (the confirmed core) — pure, no DB. Model: 500៛/standard hour, /4000, HALF-UP."""
from gm_bot.food_money import food_money_cents


def test_nine_hours_is_owner_worked_example():
    # 9h × 500៛ = 4,500៛ = $1.125 -> $1.13  (the owner's exact example)
    assert food_money_cents(540) == 113


def test_rounding_is_half_up_not_bankers():
    # 112.5¢ must round to 113 (half-up), NOT 112 (Python's default banker's rounding)
    assert food_money_cents(540) == 113


def test_eight_hours_is_a_clean_dollar():
    assert food_money_cents(480) == 100        # 8h × 500 = 4,000៛ = $1.00


def test_twelve_hours():
    assert food_money_cents(720) == 150        # 12h -> $1.50


def test_fractional_hours_prorate_by_minute():
    assert food_money_cents(510) == 106        # 8.5h = 4,250៛ = $1.0625 -> $1.06


def test_no_show_or_no_shift_gets_nothing():
    assert food_money_cents(0) == 0
    assert food_money_cents(None) == 0
    assert food_money_cents(-30) == 0
