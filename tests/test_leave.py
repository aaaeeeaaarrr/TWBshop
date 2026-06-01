"""Tests for gm_bot/bot.py _leave_questions — which clarifications a leave needs.
Pure, no DB/AI/Telegram."""

from gm_bot import bot


def test_off_without_al_and_no_date_asks_both():
    qs = bot._leave_questions(said_al=False, leave_type="off", dates=None)
    assert len(qs) == 2
    assert any("annual leave" in q for q in qs)
    assert any("day(s)" in q for q in qs)


def test_off_without_al_with_date_asks_only_type():
    qs = bot._leave_questions(said_al=False, leave_type="off", dates="tomorrow")
    assert qs == ["is this annual leave (AL) or another kind of off"]


def test_said_al_with_date_needs_nothing():
    assert bot._leave_questions(said_al=True, leave_type="al", dates="5th") == []


def test_said_al_without_date_asks_date_only():
    qs = bot._leave_questions(said_al=True, leave_type="al", dates=None)
    assert qs == ["which day(s)"]


def test_sick_with_date_needs_nothing():
    # Sick leave is a known type; with a date it's complete (no AL-or-not question).
    assert bot._leave_questions(said_al=False, leave_type="sick", dates="today") == []


def test_unspecified_no_date_asks_both():
    qs = bot._leave_questions(said_al=False, leave_type="unspecified", dates=None)
    assert len(qs) == 2


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
