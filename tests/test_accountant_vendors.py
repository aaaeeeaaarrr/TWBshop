"""Vendor-identity matching (design §G7): alias-aware, deterministic auto-resolve (vendor_by_name)
+ the fuzzy human-confirmed 'did you mean' dedup gate (find_similar_vendors) + self-healing aliases.
conftest forces TWBSHOP_ENV=staging so these never touch prod; skips if staging DB is unavailable."""
import json

import pytest


@pytest.fixture
def vendors():
    try:
        from accountant.db import init_accounting_db, vendor_link
        from shared.database import _db
        init_accounting_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    ids = [vendor_link("ZZ Atlas Beer Co"), vendor_link("ZZ Indoguna Foods")]
    yield ids
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_vendors WHERE id = ANY(%s)", (ids,))


def test_vendor_by_name_substring(vendors):
    from accountant.db import vendor_by_name
    v = vendor_by_name("ZZ ATLAS BEER")            # printed differently-cased, shorter than the name
    assert v and v["name"] == "ZZ Atlas Beer Co"


def test_vendor_by_name_matches_saved_alias(vendors):
    # a corrected wrong spelling becomes an alias → the variant now auto-resolves (self-healing)
    from accountant.db import add_vendor_alias, vendor_by_name
    atlas = vendors[0]
    add_vendor_alias(atlas, "Atlass")
    v = vendor_by_name("paid Atlass today")
    assert v and v["id"] == atlas


def test_vendor_by_name_no_false_match(vendors):
    from accountant.db import vendor_by_name
    assert vendor_by_name("Zzqwx Unrelatedxyz Brandnewthing") is None   # auto-resolve never guesses


def test_find_similar_vendors_catches_typo(vendors):
    # transposition 'Altas' — a SUBSTRING match misses it; the fuzzy dedup gate must still surface Atlas
    from accountant.db import find_similar_vendors
    hits = find_similar_vendors("ZZ Altas Beer")
    assert hits and hits[0]["name"] == "ZZ Atlas Beer Co"


def test_find_similar_vendors_empty_when_nothing_close(vendors):
    from accountant.db import find_similar_vendors
    assert find_similar_vendors("Qwerty Zxcvb Nomatch") == []


def test_add_vendor_alias_dedups_case_insensitively(vendors):
    from accountant.db import add_vendor_alias
    from shared.database import _db
    atlas = vendors[0]
    add_vendor_alias(atlas, "Atlas BC")
    add_vendor_alias(atlas, "atlas bc")            # same spelling, different case → no duplicate
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT aliases FROM acc_vendors WHERE id=%s", (atlas,))
            aliases = json.loads(cur.fetchone()["aliases"])
    assert sum(1 for a in aliases if a.lower() == "atlas bc") == 1
