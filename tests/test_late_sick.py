"""Late sick-informing (owner, Jun 16): own-sick told within 30 min of shift (or after) → −15 "Late
Informing" 🔻; family-sick within 10 min → a soft note (no points). The callout text is pure on the
minutes-to-shift, so we test it directly; the −15 value lives in the points catalogue."""
from gm_bot import attendance_ui as ui
from gm_bot.points import CATALOGUE


def test_own_sick_callout_fires_only_when_late():
    assert ui._late_sick_callout(None) == ""          # no shift today → nothing
    assert ui._late_sick_callout(45) == ""            # 45 min before (≥30) → not late
    assert ui._late_sick_callout(30) == ""            # exactly the window → not late
    near = ui._late_sick_callout(20)
    assert near and "20 minutes" in near and "very late" in near
    started = ui._late_sick_callout(-5)
    assert started and "already started" in started


def test_family_sick_note_fires_only_when_very_late_and_has_no_points():
    assert ui._late_famsick_note(None) == ""
    assert ui._late_famsick_note(20) == ""            # 20 min (≥10) → no note
    note = ui._late_famsick_note(5)
    assert note and "sudden" in note
    # family note must NOT mention points/penalty (it's a soft note only)
    assert "−15" not in note and "points" not in note.lower()


def test_late_inform_is_a_minus_15_catalogue_cause():
    assert "late_sick_inform" in CATALOGUE
    value, _desc = CATALOGUE["late_sick_inform"]
    assert value == -15


def test_windows_are_the_owner_values():
    assert ui.LATE_SICK_OWN_MIN == 30 and ui.LATE_SICK_FAM_MIN == 10
