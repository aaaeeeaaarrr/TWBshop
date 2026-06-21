"""Overnight-tail + return-announcement display clarity (owner, Jun 21)."""
from datetime import date

import gm_bot.bot as bot

# Chenda: shift 18:00-06:00; Long: 21:00-06:00
CHENDA = {"call_name": "Chenda", "work_start": "18:00", "work_end": "06:00"}
LONG = {"call_name": "Long", "work_start": "21:00", "work_end": "06:00"}


def test_overnight_tail_shows_next_day():
    # 6:00-6:59am on the Sat 20/06 shift is really SUNDAY morning
    label = bot._slot_when_label(CHENDA, "2026-06-20", 360, 419)
    assert "shift" in label and "Sun" in label and "6am-6:59am" in label
    assert label.startswith("Sat 20/06")


def test_same_day_slot_stays_plain():
    # an 8-9pm come-late tail on the same evening — no "shift →" wrapper
    label = bot._slot_when_label(CHENDA, "2026-06-20", 1200, 1260)
    assert "→" not in label and label == "Sat 20/06 8pm-9pm"


def test_return_label_has_dow_date_time():
    when = bot._return_when_label(LONG, when=date(2026, 6, 21))
    assert when == "Sun 21/06, 9pm"
