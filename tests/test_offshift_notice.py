"""Off-shift check-in feedback — pure tests (no DB / no Telegram).

When a live-location share doesn't bind to a scheduled shift, the bot used to go SILENT (which staff
read as "the bot is broken", and which hid a genuinely wrong schedule — the Jun 19 false alarm). It
now replies. Covers the classifier (checkin.offshift_reason) and the bilingual builder
(attendance_ui.offshift_notice_text).
"""
from gm_bot import checkin as ci
from gm_bot import attendance_ui as ui


def _day(working=True, start=540, end=1020):
    return {"working": working, "start_min": start, "end_min": end}


# ---- classifier: offshift_reason -------------------------------------------------

def test_not_working_is_off():
    assert ci.offshift_reason(540, _day(working=False, start=None, end=None)) == "off"


def test_empty_decision_is_off():
    assert ci.offshift_reason(540, {}) == "off"
    assert ci.offshift_reason(540, None) == "off"


def test_working_but_no_times_is_off():
    # working today but shift times unset -> can't compute a window -> treat as off (don't crash)
    assert ci.offshift_reason(540, _day(start=None, end=1020)) == "off"
    assert ci.offshift_reason(540, _day(start=540, end=None)) == "off"


def test_day_worker_too_early():
    # 09:00 shift, sharing at 06:40 (400) -> before the 60-min window (opens 08:00) -> too_early
    assert ci.offshift_reason(400, _day(start=540, end=1020)) == "too_early"


def test_day_worker_just_before_window_is_too_early():
    # window opens at 08:00 (480); 07:59 (479) is still too early
    assert ci.offshift_reason(479, _day(start=540, end=1020)) == "too_early"


def test_day_worker_after_window_is_over():
    # 09:00-17:00 shift; window closes 17:00+120 = 19:00 (1140). Sharing at 20:00 (1200) -> over
    assert ci.offshift_reason(1200, _day(start=540, end=1020)) == "over"


def test_night_worker_afternoon_is_too_early():
    # 21:00->06:00 overnight; sharing at 19:00 (1140), before the 20:00 window -> too_early
    assert ci.offshift_reason(1140, _day(start=1260, end=360)) == "too_early"


# ---- builder: offshift_notice_text ----------------------------------------------

def test_off_message_is_bilingual_and_actionable():
    t = ui.offshift_notice_text("off")
    assert "OFF today" in t                 # English: clearly states the system view
    assert "supervisor" in t                # tells them how to fix it
    assert "ឈប់" in t                        # Khmer present


def test_too_early_shows_the_start_time_both_languages():
    t = ui.offshift_notice_text("too_early", 1260)
    assert t.count("21:00") == 2            # English + Khmer halves both name the start
    assert "early" in t
    assert "វេន" in t                        # Khmer present


def test_too_early_formats_morning_time():
    assert "08:00" in ui.offshift_notice_text("too_early", 480)


def test_too_early_without_time_falls_back_to_generic():
    # defensive: no start time -> don't show a bogus time, fall through to the generic 'not on a shift'
    t = ui.offshift_notice_text("too_early", None)
    assert "not on a shift right now" in t


def test_over_message_is_generic_and_bilingual():
    t = ui.offshift_notice_text("over")
    assert "not on a shift right now" in t
    assert "supervisor" in t
    assert "វេន" in t


def test_three_codes_give_three_distinct_messages():
    off = ui.offshift_notice_text("off")
    early = ui.offshift_notice_text("too_early", 1260)
    over = ui.offshift_notice_text("over")
    assert len({off, early, over}) == 3
