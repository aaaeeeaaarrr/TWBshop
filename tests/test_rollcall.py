"""Roll-call name matching + greeting — pure logic, no DB/Telegram."""
from gm_bot.rollcall import greeting_text, match_staff_name

ROSTER = [
    {"id": 1, "canonical_name": "An Davy", "call_name": "Davy", "aliases": ["An Davy"],
     "status": "active"},
    {"id": 2, "canonical_name": "Khon Visalpisey", "call_name": "Sey", "aliases": ["Pisey"],
     "status": "active"},
    {"id": 3, "canonical_name": "Chuch Pisey", "call_name": "Pisey", "aliases": [],
     "status": "active"},
    {"id": 4, "canonical_name": "Doeun Rothanak", "call_name": "Nak", "aliases": ["Nakk"],
     "status": "active"},
    {"id": 5, "canonical_name": "Sot Somnang", "call_name": "Nang", "aliases": ["Bad boy Somnang"],
     "status": "ex_staff"},
    {"id": 6, "canonical_name": "Tengmarim Chaktopor", "call_name": "Por",
     "aliases": ["por Khmer Bruce PP"], "status": "active"},
]


def _ids(matches):
    return [m["id"] for m in matches]


def test_exact_full_name():
    assert _ids(match_staff_name("hello, I am An Davy", ROSTER)) == [1]


def test_reversed_khmer_order():
    # given name first (right token), surname second
    assert 1 in _ids(match_staff_name("hi this is Davy An", ROSTER))


def test_call_name_only():
    assert 4 in _ids(match_staff_name("hello GM, Nak here", ROSTER))


def test_given_name_right_token():
    assert 4 in _ids(match_staff_name("im Rothanak", ROSTER))


def test_alias_match():
    assert 4 in _ids(match_staff_name("Nakk says hello", ROSTER))


def test_typo_difflib():
    assert 1 in _ids(match_staff_name("hello im An Davyy", ROSTER))


def test_ambiguous_pisey_returns_both():
    got = _ids(match_staff_name("hello I'm Pisey", ROSTER))
    assert 2 in got and 3 in got


def test_ex_staff_never_matches():
    assert 5 not in _ids(match_staff_name("hello it's Somnang", ROSTER))


def test_no_match_returns_empty():
    assert match_staff_name("hello what time do you open?", ROSTER) == []
    assert match_staff_name("", ROSTER) == []


def test_short_words_dont_false_match():
    # 'por' is only 3 chars — a random 'for' shouldn't bind to Chaktopor
    assert 6 not in _ids(match_staff_name("waiting for you", ROSTER))


def test_greeting_uses_call_name_bilingual():
    g = greeting_text(ROSTER[0])
    assert "Davy" in g and "សួស្តី" in g


def test_greeting_falls_back_to_right_token():
    g = greeting_text({"canonical_name": "New Person", "call_name": None})
    assert "Person" in g
