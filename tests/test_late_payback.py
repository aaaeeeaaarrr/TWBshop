"""Late + payback pure logic."""
from datetime import date

from gm_bot import late, payback


# ── late ──
def test_late_offsets_day_shift():
    offs = late.late_offsets(360, 1080)  # 6am-6pm (12h=720), cap 600
    assert offs[:10] == [5, 10, 15, 20, 30, 45, 60, 75, 90, 120]
    assert offs[-1] == 600 and all(o <= 600 for o in offs)


def test_late_offsets_short_shift_caps():
    offs = late.late_offsets(540, 840)  # 9am-2pm (5h=300), cap 180
    assert offs[-1] == 180 and 210 not in offs


def test_declared_minutes_late_overnight():
    # 9pm shift, declared 9:30pm
    assert late.declared_minutes_late(1290, 1260) == 30


# ── payback ──
def test_working_days_skips_dayoff_and_leave():
    days = payback.working_days_ahead("Wed", {"2026-06-09"}, date(2026, 6, 8), 10, 3)
    isos = [d.isoformat() for d in days]
    # 8 Mon ok · 9 Tue leave(skip) · 10 Wed dayoff(skip) · 11 Thu ok · 12 Fri ok
    assert isos == ["2026-06-08", "2026-06-11", "2026-06-12"]


def test_slot_windows_before_after():
    w = dict((lbl, (s, e)) for lbl, s, e in payback.slot_windows(540, 1020, 90))  # 9am-5pm, 90min
    assert w["before"] == (450, 540)     # 7:30-9:00
    assert w["after"] == (1020, 1110)    # 5:00-6:30


def test_slot_windows_overnight_wrap():
    w = dict((lbl, (s, e)) for lbl, s, e in payback.slot_windows(1260, 360, 60))  # 9pm-6am, 60min
    assert w["before"] == (1200, 1260)   # 8-9pm
    assert w["after"] == (360, 420)      # 6-7am


def test_apply_payback_partial_and_cap():
    assert payback.apply_payback(90, 60) == (60, 30)
    assert payback.apply_payback(30, 50) == (30, 0)   # over-work caps at balance


def test_ignore_stage():
    assert payback.ignore_stage(0) == "daily"
    assert payback.ignore_stage(2) == "daily"
    assert payback.ignore_stage(3) == "warn"
    assert payback.ignore_stage(4) == "autobook"
    assert payback.ignore_stage(9) == "autobook"


def test_day_ext_cap_15h():
    # 10h normal shift: cap = 15-10 = 5h = 300min
    assert payback.day_ext_cap(600) == 300
    # 14h shift: cap = 1h
    assert payback.day_ext_cap(840) == 60
    # 15h+ shift: cap = 0 (no room)
    assert payback.day_ext_cap(900) == 0
    assert payback.day_ext_cap(960) == 0


def test_unbooked_remaining():
    # 2h debt, 0 booked → full balance left
    assert payback.unbooked(120, 0) == 120
    # 2h debt, 1h already covered → 1h left
    assert payback.unbooked(120, 60) == 60
    # fully covered → 0 (never negative)
    assert payback.unbooked(120, 120) == 0
    assert payback.unbooked(120, 180) == 0


def test_slot_keyboard_caps_at_15h(monkeypatch):
    """A 10h shift with 11h15m debt: the picker slots must be capped at 5h (300min),
    not 11h15m — the owner's 15h-total-day rule (Jun 11 find)."""
    from gm_bot import bot
    from datetime import date

    monkeypatch.setattr(bot, "al_leave_days_set", lambda sid: set())
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [])
    monkeypatch.setattr(bot, "_sc_taken_dates", lambda sid: set())
    monkeypatch.setattr(bot, "_today_pp", lambda: date(2026, 6, 16))

    staff = {"id": 1, "work_start": "07:00", "work_end": "17:00",  # 10h shift
             "day_off": "Tue", "expertise": []}
    kb = bot._payback_slot_keyboard(staff, 675)  # 11h15m debt
    assert kb is not None
    # working-day before/after slots must use the capped size (≤300min)
    for row in kb.inline_keyboard:
        for btn in row:
            if btn.callback_data.startswith("att:pb:book:") and ("🌅" in btn.text or "🌙" in btn.text):
                mins = int(btn.callback_data.split(":")[-1])
                assert mins <= 300, "working-day slot %d > 300min cap" % mins


def test_slot_keyboard_returns_none_when_fully_booked(monkeypatch):
    """remaining=0 → None so callers show the 'already fully booked' line."""
    from gm_bot import bot
    kb = bot._payback_slot_keyboard({"id": 1, "work_start": "07:00", "work_end": "17:00",
                                     "day_off": "Tue", "expertise": []}, 0)
    assert kb is None


def test_who_kh_maps_relation_to_bare_khmer():
    """The stored `who` is an English key — the Khmer half must show a Khmer noun, never the raw
    English word (the 'សង្ឃឹមថា child របស់ប្អូន' bug). Unknown/empty falls back safely."""
    from gm_bot import bot
    assert bot._who_kh("child") == "កូន"
    assert bot._who_kh("spouse") == "ប្តី/ប្រពន្ធ"
    assert bot._who_kh("parent") == "ឪពុក/ម្តាយ"
    assert bot._who_kh("family") == "សមាជិកគ្រួសារ"
    assert bot._who_kh("CHILD ") == "កូន"          # case/space-insensitive
    assert bot._who_kh("sibling") == "sibling"      # unknown → unchanged, never crashes
    assert bot._who_kh(None) == "" and bot._who_kh("") == ""
