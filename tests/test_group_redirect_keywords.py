"""Supervisors-group redirect: the keyword set that decides when the GM nudges
'DM me, the group doesn't count'. Owner Jun 16: payback / schedule-change / swap / OT added."""
from gm_bot.bot import _REDIRECT_KEYWORDS


def _hits(text: str) -> bool:
    return any(k in text.lower() for k in _REDIRECT_KEYWORDS)


def test_new_topics_trigger_redirect():
    assert _hits("Seth can payback his hour Thursday")
    assert _hits("let's pay back the time tomorrow")
    assert _hits("can we swap Dara and Por's day off")
    assert _hits("change his shift to start later")
    assert _hits("update the schedule for next week")
    assert _hits("give him some overtime")
    assert _hits("តើអាចប្តូរវេនបានទេ")   # "can we change/swap shift"


def test_existing_topics_still_trigger():
    assert _hits("he is late today")
    assert _hits("she wants a day off")
    assert _hits("taking AL next week")
    assert _hits("he is sick")


def test_no_false_positive_from_ot_abbreviation():
    # "ot" is intentionally NOT a keyword (it collides with not/got/lot); plain chatter stays silent.
    assert not _hits("I did not see another note got lost")
    assert not _hits("good morning everyone")
