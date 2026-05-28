"""Unit tests for hire_bot/intake.py — pure functions only, no DB, no bot context."""

import sys
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Minimal config stub so intake.py can be imported without secrets.py
import types
_cfg = types.ModuleType("config")
_cfg.BAKERY_LAT = 11.5387774
_cfg.BAKERY_LNG = 104.9147998
_cfg.HIRE_ARRIVAL_STAFF_ID = 1271537077
sys.modules.setdefault("config", _cfg)

from hire_bot.intake import (
    PP_TZ, SLOT_HOURS,
    _today_available, _slot_label, _slot_dt,
    is_job_intent, _is_khmer, _implies_cant_english, _is_salary_schedule,
    kb_appointment, kb_day_slots, kb_pick_day,
    ACTIVE_STATUSES, S_LANGUAGE_CHECK, S_CV_PENDING, S_FULLTIME_GATE,
    S_APPOINTMENT, S_APPT_SET, S_BLOCKED, S_TEST_UNLOCKED,
)


# ── _slot_label ────────────────────────────────────────────────────────────────

def test_slot_label_noon():
    assert _slot_label(12) == "12:00pm"

def test_slot_label_morning():
    assert _slot_label(8) == "8:00am"
    assert _slot_label(10) == "10:00am"

def test_slot_label_afternoon():
    assert _slot_label(14) == "2:00pm"
    assert _slot_label(16) == "4:00pm"


# ── _today_available ──────────────────────────────────────────────────────────

def _pp(h: int, m: int = 0) -> datetime:
    """Construct a PP datetime for today at the given hour and minute."""
    return datetime.now(PP_TZ).replace(hour=h, minute=m, second=0, microsecond=0)

def test_all_slots_available_early_morning():
    # At 6:00am: cutoff is 7am → all SLOT_HOURS (8,10,12,14,16) are available
    available = _today_available(_pp(6, 0))
    assert available == SLOT_HOURS

def test_8am_hidden_after_7am():
    # At 7:30am: cutoff is 8:30am → 8am slot is past cutoff
    available = _today_available(_pp(7, 30))
    assert 8 not in available
    assert 10 in available

def test_8am_and_10am_hidden_at_9():
    # At 9:30am: cutoff is 10:30am → 8 and 10 are gone
    available = _today_available(_pp(9, 30))
    assert 8 not in available
    assert 10 not in available
    assert 12 in available

def test_no_slots_evening():
    # At 17:00 (5pm): cutoff is 18:00 → all slots are in the past
    available = _today_available(_pp(17, 0))
    assert available == []

def test_slot_exactly_one_hour_away_hidden():
    # At 11:00 exactly: cutoff = 12:00; slot 12:00 is NOT > 12:00
    available = _today_available(_pp(11, 0))
    assert 12 not in available

def test_slot_just_over_one_hour_away_shown():
    # At 10:59: cutoff = 11:59; slot at 12:00 IS > 11:59
    available = _today_available(_pp(10, 59))
    assert 12 in available


# ── kb_appointment ────────────────────────────────────────────────────────────

def test_kb_appointment_has_tomorrow_and_pickday():
    kb = kb_appointment()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Tomorrow" in t for t in texts)
    assert any("Another day" in t for t in texts)

def test_kb_appointment_callback_patterns():
    kb = kb_appointment()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    # At least Tomorrow and pickday are always present
    assert any(c.startswith("intake:day:") for c in callbacks)
    assert "intake:pickday" in callbacks

def test_kb_day_slots_all_five_slots():
    d = date(2026, 6, 1)
    kb = kb_day_slots(d)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    for h in SLOT_HOURS:
        expected = f"intake:slot:2026-06-01T{h:02d}:00"
        assert expected in callbacks

def test_slot_callback_colon_split():
    # callback_data "intake:slot:2026-06-04T10:00" splits by ":" into 4 parts;
    # parts[2:] must be rejoined to get the full "2026-06-04T10:00" string
    callback = "intake:slot:2026-06-04T10:00"
    parts = callback.split(":")
    assert parts == ["intake", "slot", "2026-06-04T10", "00"]
    slot_str = ":".join(parts[2:])
    assert slot_str == "2026-06-04T10:00"
    from datetime import datetime
    from zoneinfo import ZoneInfo
    dt = datetime.strptime(slot_str, "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo("Asia/Phnom_Penh"))
    assert dt.hour == 10

def test_kb_day_slots_has_back():
    d = date(2026, 6, 1)
    kb = kb_day_slots(d)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "intake:appt_back" in callbacks

def test_kb_pick_day_seven_days():
    kb = kb_pick_day()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    day_callbacks = [c for c in callbacks if c.startswith("intake:day:")]
    assert len(day_callbacks) == 7

def test_kb_pick_day_no_today():
    today = datetime.now(PP_TZ).date()
    kb = kb_pick_day()
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert f"intake:day:{today.isoformat()}" not in callbacks


# ── is_job_intent ─────────────────────────────────────────────────────────────

def test_intent_english_job():
    assert is_job_intent("I'm looking for a job") is True

def test_intent_english_apply():
    assert is_job_intent("I would like to apply") is True

def test_intent_english_cv():
    assert is_job_intent("I want to send my CV") is True

def test_intent_khmer_job():
    assert is_job_intent("ខ្ញុំចង់ស្វែងរកការងារ") is True

def test_intent_khmer_staff():
    assert is_job_intent("ចង់ជាបុគ្គលិក") is True

def test_no_intent_random():
    assert is_job_intent("Hello how are you") is False

def test_no_intent_empty():
    assert is_job_intent("") is False


# ── _is_khmer ─────────────────────────────────────────────────────────────────

def test_is_khmer_pure():
    assert _is_khmer("ខ្ញុំចង់ធ្វើការ") is True

def test_is_khmer_mixed_but_heavy():
    assert _is_khmer("hello ខ្ញុំ ចង់") is True

def test_is_khmer_english_only():
    assert _is_khmer("Hello, I want a job") is False

def test_is_khmer_empty():
    assert _is_khmer("") is False

def test_is_khmer_few_chars():
    # 1 Khmer char in a long English sentence: count=1 (not >2), ratio <20%
    assert _is_khmer("hello world how are you ក") is False


# ── _implies_cant_english ─────────────────────────────────────────────────────

def test_cant_english_explicit():
    assert _implies_cant_english("I can't speak english") is True

def test_cant_english_short():
    assert _implies_cant_english("no english") is True

def test_cant_english_khmer_phrase():
    assert _implies_cant_english("ot cheh angkles") is True

def test_cant_english_false():
    assert _implies_cant_english("I want a job") is False


# ── _is_salary_schedule ────────────────────────────────────────────────────────

def test_salary_keyword():
    assert _is_salary_schedule("How much is the salary?") is True

def test_schedule_keyword():
    assert _is_salary_schedule("What is the shift schedule?") is True

def test_morning_keyword():
    assert _is_salary_schedule("Do you have morning shift?") is True

def test_khmer_salary():
    assert _is_salary_schedule("ប្រាក់ខែ ប៉ុន្មាន?") is True

def test_no_salary_cv_text():
    assert _is_salary_schedule("I worked at a bakery for 2 years as a cashier") is False


# ── ACTIVE_STATUSES ───────────────────────────────────────────────────────────

def test_active_statuses_include_all_pretest():
    assert S_LANGUAGE_CHECK in ACTIVE_STATUSES
    assert S_CV_PENDING in ACTIVE_STATUSES
    assert S_FULLTIME_GATE in ACTIVE_STATUSES
    assert S_APPOINTMENT in ACTIVE_STATUSES
    assert S_APPT_SET in ACTIVE_STATUSES

def test_blocked_not_active():
    assert S_BLOCKED not in ACTIVE_STATUSES

def test_test_unlocked_not_active():
    assert S_TEST_UNLOCKED not in ACTIVE_STATUSES
