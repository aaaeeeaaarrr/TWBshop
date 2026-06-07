"""Special-leave pure logic (marriage/death/birth)."""
from gm_bot import special as sp


def test_marriage_days():
    assert sp.marriage_days("own") == 3
    assert sp.marriage_days("child") == 1
    assert sp.marriage_days("unknown") == 1


def test_death_tier():
    assert sp.death_tier("parent") == "law"
    assert sp.death_tier("spouse") == "law"
    assert sp.death_tier("sibling") == "compassion"
    assert sp.death_tier("grandparent") == "compassion"
    assert sp.death_tier("cousin") == "other"


def test_death_default_days():
    assert sp.death_default_days("parent") == 3       # law tier
    assert sp.death_default_days("sibling") == 1      # compassion → 1, owner upgrades


def test_death_day_options():
    assert sp.death_day_options() == [3, 4, 5, 6, 7]


def test_birth_days():
    assert sp.BIRTH_DAYS == 2
