"""Food-money calc (the confirmed core) — pure, no DB. Model: 500៛/standard hour, /4000, HALF-UP.
Plus the report-period split, the 'Day/Night staff food' renderer, and the idempotent gives record."""
import datetime as dt

import pytest

from gm_bot.food_money import food_money_cents, food_period_for, render_food_list


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


# ─────────────── report-period split + the staff-food sheet (pure) ───────────────
def test_food_period_day_vs_night_boundary():
    assert food_period_for(dt.datetime(2026, 6, 21, 10, 0))[1] == "day"    # morning → coming day report
    assert food_period_for(dt.datetime(2026, 6, 21, 16, 0))[1] == "night"  # ~4pm on → coming night
    assert food_period_for(dt.datetime(2026, 6, 22, 3, 0))[1] == "night"   # pre-dawn → still night


def test_overnight_gives_share_one_business_day():
    # a give at 16:00 on the 21st and one at 03:00 on the 22nd belong to the SAME night report
    d1, p1 = food_period_for(dt.datetime(2026, 6, 21, 16, 0))
    d2, p2 = food_period_for(dt.datetime(2026, 6, 22, 3, 0))
    assert (p1, p2) == ("night", "night") and d1 == d2


def test_render_food_list_mirrors_the_handwritten_sheet():
    # the exact list from the owner's photo (21/06/26) → must total $11.92
    rows = [("Heng", 138), ("Pisey", 113), ("Vin", 113), ("Meng", 113), ("Chantrea", 113),
            ("Nak", 113), ("Chanda", 150), ("Tra", 113), ("Long", 113), ("Davy", 113)]
    out = render_food_list("night", dt.date(2026, 6, 21), rows)
    assert "Night staff food" in out and "21/06/26" in out
    assert "total = $11.92" in out


# ─────────────── gives record — idempotent, no double-count (staging) ───────────────
@pytest.fixture
def food_db():
    try:
        from gm_bot.food_money_db import init_food_money_db
        from shared.database import _db
        init_food_money_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    bday = dt.date(2099, 1, 1)   # far-future test day — never collides with real data
    yield bday
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM food_money_gives WHERE business_day=%s", (bday,))


def test_record_is_idempotent_no_double_give(food_db):
    from gm_bot.food_money_db import record_food_money_give, food_money_given_ids
    assert record_food_money_give(9001, "Heng", food_db, "night", 138, is_test=True) is True
    assert record_food_money_give(9001, "Heng", food_db, "night", 138, is_test=True) is False  # no double
    assert 9001 in food_money_given_ids(food_db, "night", is_test=True)


def test_food_money_list_in_give_order(food_db):
    from gm_bot.food_money_db import record_food_money_give, food_money_list
    record_food_money_give(9002, "Chanda", food_db, "day", 150, is_test=True)
    record_food_money_give(9003, "Vin", food_db, "day", 113, is_test=True)
    assert food_money_list(food_db, "day", is_test=True) == [("Chanda", 150), ("Vin", 113)]
