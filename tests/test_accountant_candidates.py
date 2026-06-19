"""'Received Yet?' candidate forward flow (design §E3) — pure card logic (no DB) + the
acc_receipt_candidates lifecycle (staging). conftest.py forces TWBSHOP_ENV=staging so DB tests
never touch prod; they skip gracefully where staging creds aren't synced (cross-machine)."""
import pytest

from accountant import capture


# ─────────────────────────── pure logic (no DB) ───────────────────────────
def test_candidate_card_open_shows_name_and_group():
    txt = capture.candidate_card({"id": 3, "vendor_name": "Song Heng Gas",
                                  "src_chat_title": "Song Heng group", "status": "open"})
    assert "Song Heng Gas" in txt and "Song Heng group" in txt and "Received yet?" in txt


def test_candidate_card_unmapped_group_is_graceful():
    txt = capture.candidate_card({"id": 1, "vendor_name": None, "src_chat_title": None, "status": "open"})
    assert "unmapped supplier" in txt and "supplier group" in txt


def test_candidate_card_terminal_states():
    base = {"id": 5, "vendor_name": "Atlas", "src_chat_title": "Atlas grp"}
    assert "#14" in capture.candidate_card({**base, "status": "promoted", "receipt_id": 14})
    assert "#14" in capture.candidate_card({**base, "status": "linked", "receipt_id": 14})
    assert "expected" in capture.candidate_card({**base, "status": "expected"})
    assert "Ignored" in capture.candidate_card({**base, "status": "ignored"})


def test_candidate_buttons_open_offers_all_forks():
    data = [d for row in capture.candidate_buttons({"id": 7, "status": "open"}) for (_, d) in row]
    assert set(data) == {"accand:new:7", "accand:link:7", "accand:exp:7", "accand:ig:7"}


def test_candidate_buttons_resolved_has_none():
    for status in ("promoted", "linked", "expected", "ignored", "promoting"):
        assert capture.candidate_buttons({"id": 7, "status": status}) == []


def test_lookalike_prompt_and_buttons_reference_the_receipt():
    look = {"id": 14, "vendor_name": "Song Heng Gas", "amount_cents": 6800}
    assert "#14" in capture.lookalike_prompt(look) and "$68.00" in capture.lookalike_prompt(look)
    data = [d for row in capture.lookalike_buttons(7, 14) for (_, d) in row]
    assert data == ["accand:pnew:7", "accand:psame:7"]


def test_receipt_pick_label():
    assert capture.receipt_pick_label({"id": 14, "amount_cents": 6800, "status": "paid"}) \
        == "#14 · $68.00 · paid"
    assert capture.receipt_pick_label({"id": 9, "amount_cents": None, "status": "confirmed"}) \
        == "#9 · ? · unpaid"


# ─────────────────────────── DB lifecycle (staging) ───────────────────────────
@pytest.fixture
def vendor():
    try:
        from accountant.db import init_accounting_db, vendor_link
        from shared.database import _db
        init_accounting_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    vid = vendor_link("ZZ Cand Vendor", -999000077, "test")
    yield vid
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_receipt_candidates WHERE vendor_id=%s", (vid,))
            cur.execute("DELETE FROM acc_receipt_lines WHERE receipt_id IN "
                        "(SELECT id FROM acc_receipts WHERE vendor_id=%s)", (vid,))
            cur.execute("DELETE FROM acc_receipts WHERE vendor_id=%s", (vid,))
            cur.execute("DELETE FROM acc_vendors WHERE id=%s", (vid,))


def test_add_candidate_dedup_on_sha(vendor):
    from accountant.db import add_candidate, get_candidate
    cid = add_candidate(vendor_id=vendor, photo_sha="zz_cand_1", src_chat_title="g", is_test=True)
    again = add_candidate(vendor_id=vendor, photo_sha="zz_cand_1", src_chat_title="g", is_test=True)
    assert cid == again                                   # same supplier photo → one candidate
    assert get_candidate(cid)["status"] == "open"


def test_resolve_candidate_is_atomic_one_shot(vendor):
    from accountant.db import add_candidate, resolve_candidate, get_candidate
    cid = add_candidate(vendor_id=vendor, photo_sha="zz_cand_exp", is_test=True)
    assert resolve_candidate(cid, "expected", 111) is True
    assert resolve_candidate(cid, "ignored", 111) is False   # already resolved → no re-resolve
    assert get_candidate(cid)["status"] == "expected"


def test_link_candidate_points_at_a_receipt(vendor):
    from accountant.db import add_candidate, add_receipt, link_candidate, get_candidate
    rid = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_cand_rcpt", is_test=True)
    cid = add_candidate(vendor_id=vendor, photo_sha="zz_cand_link", is_test=True)
    assert link_candidate(cid, rid, 111) is True
    assert link_candidate(cid, rid, 111) is False            # already linked
    c = get_candidate(cid)
    assert c["status"] == "linked" and c["receipt_id"] == rid


def test_promote_claim_is_single_winner(vendor):
    from accountant.db import (add_candidate, add_receipt, claim_candidate, finalize_promote,
                               get_candidate)
    cid = add_candidate(vendor_id=vendor, photo_sha="zz_cand_promote", is_test=True)
    assert claim_candidate(cid) is True
    assert claim_candidate(cid) is False                     # a double-tap can't double-claim
    rid = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_cand_promoted_r", is_test=True)
    finalize_promote(cid, rid, 111)
    c = get_candidate(cid)
    assert c["status"] == "promoted" and c["receipt_id"] == rid


def test_unclaim_reverts_a_failed_promote(vendor):
    from accountant.db import add_candidate, claim_candidate, unclaim_candidate, get_candidate
    cid = add_candidate(vendor_id=vendor, photo_sha="zz_cand_unclaim", is_test=True)
    assert claim_candidate(cid) is True
    unclaim_candidate(cid)
    assert get_candidate(cid)["status"] == "open"            # back in the queue for a retry
    assert claim_candidate(cid) is True                      # claimable again


def test_find_lookalike_matches_vendor_amount_and_window(vendor):
    from accountant.db import add_receipt, find_lookalike_receipt
    from shared.database import _db
    rid = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_look_r", is_test=True)
    # same vendor + amount, fresh → a hit
    hit = find_lookalike_receipt(vendor, 6800, within_days=7, is_test=True)
    assert hit and hit["id"] == rid
    # different amount / no amount → no hit
    assert find_lookalike_receipt(vendor, 9999, within_days=7, is_test=True) is None
    assert find_lookalike_receipt(vendor, None, within_days=7, is_test=True) is None
    assert find_lookalike_receipt(None, 6800, within_days=7, is_test=True) is None
    # outside the window → no hit (backdate the row 30 days)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_receipts SET created_at = NOW() - INTERVAL '30 days' WHERE id=%s",
                        (rid,))
    assert find_lookalike_receipt(vendor, 6800, within_days=7, is_test=True) is None


def test_find_lookalike_excludes_self_and_finds_prior(vendor):
    from accountant.db import add_receipt, find_lookalike_receipt
    r1 = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_excl_1", is_test=True)
    # only r1 exists → excluding it finds nothing (the direct path ignores the row it just made)
    assert find_lookalike_receipt(vendor, 6800, exclude_id=r1, is_test=True) is None
    r2 = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_excl_2", is_test=True)
    # a second same-vendor+amount row → excluding r2 surfaces the PRIOR r1 (a real look-alike)
    hit = find_lookalike_receipt(vendor, 6800, exclude_id=r2, is_test=True)
    assert hit and hit["id"] == r1


def test_flag_dup_suspect_sets_the_hint(vendor):
    from accountant.db import add_receipt, flag_dup_suspect, get_receipt
    r1 = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_flag_1", is_test=True)
    r2 = add_receipt(vendor_id=vendor, amount_cents=6800, photo_sha="zz_flag_2", is_test=True)
    flag_dup_suspect(r2, r1)
    assert get_receipt(r2)["dup_suspect_of"] == r1
    assert get_receipt(r1)["dup_suspect_of"] is None      # the prior row is untouched


def test_recent_receipts_for_vendor_lists_newest_first(vendor):
    from accountant.db import add_receipt, recent_receipts_for_vendor
    r1 = add_receipt(vendor_id=vendor, amount_cents=100, photo_sha="zz_recent_1", is_test=True)
    r2 = add_receipt(vendor_id=vendor, amount_cents=200, photo_sha="zz_recent_2", is_test=True)
    ids = [r["id"] for r in recent_receipts_for_vendor(vendor, 8, is_test=True)]
    assert ids[:2] == [r2, r1]                               # newest first
    assert recent_receipts_for_vendor(None) == []
