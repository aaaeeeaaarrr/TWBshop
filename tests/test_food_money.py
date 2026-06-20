"""Food-money calc (the confirmed core) — pure, no DB. Model: 500៛/standard hour, /4000, HALF-UP.
Plus the report-period split, the 'Day/Night staff food' renderer, and the idempotent gives record."""
import datetime as dt

import pytest

from gm_bot.food_money import food_menu_rows, food_money_cents, next_report_kind, render_food_list


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


# ─────────────── report assignment is event-driven (pure) ───────────────
def test_next_report_kind_alternates():
    assert next_report_kind("final") == "mid"      # after the night close, next is the day report
    assert next_report_kind("mid") == "final"      # after the day report, next is the night close
    assert next_report_kind(None) is None          # unknown → generic message


def test_render_food_list_mirrors_the_handwritten_sheet():
    # the exact list from the owner's photo (21/06/26), a 'final' (night) report → must total $11.92
    rows = [("Heng", 138), ("Pisey", 113), ("Vin", 113), ("Meng", 113), ("Chantrea", 113),
            ("Nak", 113), ("Chanda", 150), ("Tra", 113), ("Long", 113), ("Davy", 113)]
    out = render_food_list("final", dt.date(2026, 6, 21), rows)
    assert "Night staff food" in out and "21/06/26" in out
    assert "total = $11.92" in out


# ─────────────── menu: ARRIVED-only, exclude already-given, standard-shift amount (pure) ──────────────
def test_food_menu_amount_from_standard_shift():
    rows = food_menu_rows([{"staff_id": 1, "name": "Heng", "work_start": "19:00", "work_end": "06:00"},
                           {"staff_id": 2, "name": "Chanda", "work_start": "18:00", "work_end": "06:00"}],
                          given_ids=set())
    assert rows == [(1, "Heng", 138), (2, "Chanda", 150)]   # 11h→$1.38, 12h→$1.50


def test_food_menu_excludes_already_given_and_no_shift():
    arrived = [{"staff_id": 1, "name": "Heng", "work_start": "21:00", "work_end": "06:00"},
               {"staff_id": 2, "name": "Chanda", "work_start": "18:00", "work_end": "06:00"},
               {"staff_id": 3, "name": "NoShift", "work_start": None, "work_end": None}]
    rows = food_menu_rows(arrived, given_ids={2})
    assert rows == [(1, "Heng", 113)]                        # Chanda given → gone; NoShift no schedule → gone


def test_food_menu_only_arrived_can_appear():
    # the owner's rule: a scheduled-but-not-arrived staffer is never passed in `arrived`, so the menu
    # cannot show them — only Heng (who checked in) is here.
    rows = food_menu_rows([{"staff_id": 1, "name": "Heng", "work_start": "21:00", "work_end": "06:00"}], set())
    assert rows == [(1, "Heng", 113)]


# ─────────────── gives: open → idempotent → close-on-report → reopen (staging) ───────────────
@pytest.fixture
def food_db():
    try:
        from gm_bot.food_money_db import init_food_money_db
        from shared.database import _db
        init_food_money_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    ids = [9001, 9002, 9003]

    def _clean():
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM food_money_gives WHERE staff_id = ANY(%s)", (ids,))
    _clean()                       # clean before too, in case a prior run crashed mid-test
    yield ids
    _clean()


def test_open_give_is_idempotent_until_closed(food_db):
    from gm_bot.food_money_db import record_food_money_give, food_money_open_ids
    assert record_food_money_give(9001, "Heng", 138, is_test=True) is True
    assert record_food_money_give(9001, "Heng", 138, is_test=True) is False   # no double while open
    assert 9001 in food_money_open_ids(is_test=True)


def test_close_attaches_open_gives_then_reopens(food_db):
    from gm_bot.food_money_db import (close_food_period, food_money_list_for_report,
                                      food_money_open_ids, record_food_money_give)
    record_food_money_give(9002, "Chanda", 150, is_test=True)
    record_food_money_give(9003, "Vin", 113, is_test=True)
    # the night report (id 777) is stored → open gives attach to it, in give order
    closed = close_food_period(777, dt.date(2099, 1, 1), "final", is_test=True)
    assert closed == [("Chanda", 150), ("Vin", 113)]
    assert food_money_list_for_report(777) == [("Chanda", 150), ("Vin", 113)]
    assert food_money_open_ids(is_test=True) == set()                         # nothing open now
    # after close, the SAME staff can be given again for the NEXT report (not blocked)
    assert record_food_money_give(9002, "Chanda", 150, is_test=True) is True


def test_food_arrived_staff_is_readonly_and_listy(food_db):
    # read-only query of CHECKED-IN staff (joins attendance_sessions + staff_registry); never raises
    from gm_bot.food_money_db import food_arrived_staff
    assert isinstance(food_arrived_staff([dt.date(2099, 1, 1)], is_test=True), list)
