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


def test_propose_then_confirm_vendor(vendors):
    # decision A: staff create immediately (needs_review=TRUE, usable now) → owner one-tap clears it
    from accountant.db import propose_vendor, get_vendor, list_unconfirmed_vendors, confirm_vendor
    from shared.database import _db
    vid = propose_vendor("ZZ Brand New Supplier", created_by=42)
    try:
        v = get_vendor(vid)
        assert v["needs_review"] is True and v["created_by"] == 42
        assert any(x["id"] == vid for x in list_unconfirmed_vendors())   # shows in the confirm-list
        confirm_vendor(vid)
        assert get_vendor(vid)["needs_review"] is False
        assert all(x["id"] != vid for x in list_unconfirmed_vendors())   # cleared after confirm
    finally:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM acc_vendors WHERE id=%s", (vid,))


def test_rank_channels_orders_by_title_match_and_drops_unrelated():
    from accountant.db import _rank_channels                          # pure — no DB
    chans = [{"chat_id": -1, "title": "Atlas Beer Orders"},
             {"chat_id": -2, "title": "Random Unrelated Chat"},
             {"chat_id": -3, "title": "ATLAS 🍺"}]
    titles = [c["title"] for c in _rank_channels("Atlas", chans)]
    assert "Random Unrelated Chat" not in titles                     # below cutoff → dropped
    assert titles[0] in ("Atlas Beer Orders", "ATLAS 🍺")            # a strong title match leads


def test_listener_channels_matching_is_defensive(vendors):
    from accountant.db import listener_channels_matching
    assert isinstance(listener_channels_matching("Atlas"), list)     # never raises (ops_messages or not)


def test_set_vendor_kind_and_attach_channel(vendors):
    from accountant.db import set_vendor_kind, attach_vendor_channel, get_vendor, vendor_by_group
    atlas = vendors[0]
    set_vendor_kind(atlas, "oneoff")
    assert get_vendor(atlas)["kind"] == "oneoff"
    set_vendor_kind(atlas, "bogus")                                  # unknown kind ignored
    assert get_vendor(atlas)["kind"] == "oneoff"
    attach_vendor_channel(atlas, -1009990001)                       # group (negative id)
    v = get_vendor(atlas)
    assert v["tg_group_id"] == -1009990001 and v["channel_kind"] == "group"
    assert vendor_by_group(-1009990001)["id"] == atlas              # now resolves from that chat
    attach_vendor_channel(atlas, 42420001)                          # DM (positive id) → relink
    assert get_vendor(atlas)["channel_kind"] == "dm"


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
