"""Regression guard for the Chenda/Fang overnight payback OFFER-label off-by-one (session 58, 2026-06-28).

An overnight worker's AFTER slot (the post-shift morning tail) must show its TRUE next-calendar morning,
not the shift-start date — otherwise 'pay back tomorrow (Sun 28) morning' shows as 'Sat 27' and staff
think the 28th 'doesn't record'. BEFORE / day-worker / day-off labels must stay the plain shift-date
label (no spurious wrap). The slot still BINDS to the shift date (settle math unchanged); this is label
only. Note 2026-06-27 = Saturday, 2026-06-28 = Sunday (matches the reported case)."""
from gm_bot.bot import _pb_offer_label


def test_overnight_after_slot_shows_next_morning():
    staff = {"work_start": "21:00", "work_end": "06:00"}                  # 21:00 -> 06:00 overnight
    lbl = _pb_offer_label(staff, "after", "2026-06-27", 6 * 60, 6 * 60 + 30, 0)  # 06:00-06:30 tail
    assert "Sat 27/06" in lbl              # still anchored to the shift date (binding unchanged)
    assert "→" in lbl and "Sun" in lbl     # disambiguated to the real next calendar morning


def test_overnight_before_slot_stays_same_evening():
    staff = {"work_start": "21:00", "work_end": "06:00"}
    lbl = _pb_offer_label(staff, "before", "2026-06-27", 20 * 60 + 30, 21 * 60, 0)  # 20:30-21:00
    assert "Sat 27/06" in lbl and "→" not in lbl   # before-shift is the same evening — must NOT wrap


def test_day_worker_after_slot_no_wrap():
    staff = {"work_start": "08:00", "work_end": "17:00"}
    lbl = _pb_offer_label(staff, "after", "2026-06-27", 17 * 60, 17 * 60 + 30, 0)  # 17:00-17:30
    assert "Sat 27/06" in lbl and "→" not in lbl   # a day worker's after-slot is the same day


def test_dayoff_label_unchanged():
    staff = {"work_start": "21:00", "work_end": "06:00"}
    lbl = _pb_offer_label(staff, "dayoff", "2026-06-28", 22 * 60, 23 * 60, 0)
    assert "day off" in lbl and "Sun 28/06" in lbl   # day-off wording preserved
