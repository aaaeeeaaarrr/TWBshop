"""P1 capture tests — pure card/math logic (no DB) + the acc_receipts lifecycle (staging).
conftest.py forces TWBSHOP_ENV=staging so DB tests never touch prod."""
import pytest

from accountant import capture


# ─────────────────────────── pure logic (no DB) ───────────────────────────
def test_fmt_money():
    assert capture.fmt_money(13860) == "$138.60"
    assert capture.fmt_money(None) == "?"
    assert capture.fmt_money(100000) == "$1,000.00"


def test_math_check_within_tolerance_is_silent():
    ok, msg = capture.math_check(13800, 13860)  # ~0.4% under (tax/rounding)
    assert ok and msg == ""


def test_math_check_flags_real_gap():
    ok, msg = capture.math_check(10000, 13860)
    assert not ok and "check the paper" in msg


def test_math_check_unknown_never_cries_wolf():
    assert capture.math_check(None, 13860)[0] is True
    assert capture.math_check(13860, None)[0] is True


def test_parse_amount_usd_total():
    assert capture.parse_amount_cents("Total: $138.60, items 2x $12.00") == (13860, "USD", 138.60)


def test_parse_amount_prefers_total_over_received_change():
    # cash receipt: Grand Total $2.40, Received $20.00, Change $17.60 — must pick the TOTAL
    cents, cur, _ = capture.parse_amount_cents(
        "Grand Total(USD): $2.40 Received(USD): $20.00 Change(USD): $17.60")
    assert (cents, cur) == (240, "USD")


def test_parse_amount_dual_currency_prefers_usd():
    # supplier prints both; their Riel rate may differ from 4000/1 → trust the USD figure
    cents, cur, _ = capture.parse_amount_cents("Grand Total(Riel): ៛9,800 Grand Total(USD): $2.40")
    assert (cents, cur) == (240, "USD")


def test_parse_amount_riel_only_converts_at_4000():
    cents, cur, orig = capture.parse_amount_cents("Total: 92000 (Khmer Riel)")
    assert (cents, cur, orig) == (2300, "KHR", 92000.0)   # 92000 / 4000 = $23.00


def test_parse_amount_none():
    assert capture.parse_amount_cents("no numbers here") == (None, None, None)
    assert capture.parse_amount_cents("") == (None, None, None)


def test_route():
    assert capture.route({"is_receipt": True, "doc_type": "receipt"}) == "receipt"
    assert capture.route({"is_receipt": False, "doc_type": "pos_screen"}) == "pos_screen"
    assert capture.route({"is_receipt": False, "doc_type": "other"}) == "other"


def test_render_card_draft_shows_key_facts():
    txt = capture.render_card({"id": 14, "vendor_name": "Indoguna", "amount_cents": 13860,
                               "status": "captured", "items_text": "cheese"})
    assert "#14" in txt and "Indoguna" in txt and "$138.60" in txt


def test_render_card_missing_amount_warns():
    txt = capture.render_card({"id": 9, "amount_cents": None, "status": "captured"})
    assert "amount not read" in txt


def test_render_card_flags_suspected_duplicate():
    txt = capture.render_card({"id": 20, "vendor_name": "Atlas", "amount_cents": 6800,
                               "status": "captured", "dup_suspect_of": 14})
    assert "possible duplicate of #14" in txt


def test_render_card_tentative_translation_shows_original_and_question():
    # handwritten Khmer read → fresh, unconfirmed translation = a GUESS: show the as-written
    # original + a ? so staff verify it (not a confident invented English word).
    txt = capture.render_card({"id": 50, "vendor_name": "Mrk", "amount_cents": 13530,
                               "status": "captured",
                               "lines": [{"raw_name": "Chicken", "orig_name": "សាច់មាន់",
                                          "qty": 4, "line_total_cents": 7680}]})
    assert "សាច់មាន់ → Chicken?" in txt
    assert "×4" in txt and "$76.80" in txt          # the stable numbers still show plainly


def test_render_card_confirmed_alias_drops_the_question():
    # once a translation is a learned/confirmed alias, trust it: clean English name, no original, no ?
    txt = capture.render_card({"id": 51, "status": "captured",
                               "lines": [{"raw_name": "Potato", "orig_name": "ដំឡូង",
                                          "confident": True, "qty": 3, "line_total_cents": 5850}]})
    assert "Potato" in txt and "ដំឡូង" not in txt and "Potato?" not in txt


def test_render_card_printed_name_no_question():
    # printed Latin name (orig == name, nothing translated) → plain line, no "→ ...?" guess marker
    txt = capture.render_card({"id": 52, "status": "captured",
                               "lines": [{"raw_name": "Cheese", "orig_name": "Cheese",
                                          "qty": 2, "line_total_cents": 2400}]})
    assert "1. Cheese ×2" in txt                     # name shown directly, no original, no guess
    assert "Cheese?" not in txt and "→" not in txt


def test_card_buttons_fix_is_always_present():
    for status in ("captured", "confirmed", "paid"):
        rows = capture.card_buttons({"id": 1, "status": status})
        data = [d for row in rows for (_, d) in row]
        assert "acc:fix:1" in data


def test_card_buttons_draft_offers_confirm_and_both_pay_methods():
    data = [d for row in capture.card_buttons({"id": 1, "status": "captured"}) for (_, d) in row]
    assert {"acc:ok:1", "acc:cash:1", "acc:aba:1"} <= set(data)


# ─────────────────────────── DB lifecycle (staging) ───────────────────────────
@pytest.fixture
def vendor():
    try:
        from accountant.db import init_accounting_db, vendor_link
        from shared.database import _db
        init_accounting_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    vid = vendor_link("ZZ Test Vendor", -999000001, "test")
    yield vid
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_receipts WHERE vendor_id=%s", (vid,))
            cur.execute("DELETE FROM acc_vendors WHERE id=%s", (vid,))


def test_add_receipt_and_photo_dedup(vendor):
    from accountant.db import add_receipt, get_receipt
    rid = add_receipt(vendor_id=vendor, amount_cents=13860, items_text="cheese",
                      photo_sha="zz_sha_1", is_test=True)
    again = add_receipt(vendor_id=vendor, amount_cents=999, photo_sha="zz_sha_1", is_test=True)
    assert rid == again  # same photo → one row (S2 dedup)
    r = get_receipt(rid)
    assert r["status"] == "captured" and r["amount_cents"] == 13860


def test_cash_payment_is_idempotent(vendor):
    from accountant.db import add_receipt, set_payment, get_receipt
    rid = add_receipt(vendor_id=vendor, amount_cents=240, photo_sha="zz_sha_cash", is_test=True)
    assert set_payment(rid, "cash") is True
    assert set_payment(rid, "cash") is False          # already paid → no double-anything
    assert get_receipt(rid)["status"] == "paid"


def test_aba_stays_open_and_lists(vendor):
    from accountant.db import add_receipt, confirm_receipt, set_payment, get_receipt, list_open_receipts
    rid = add_receipt(vendor_id=vendor, amount_cents=13860, photo_sha="zz_sha_aba", is_test=True)
    confirm_receipt(rid)
    set_payment(rid, "aba")
    r = get_receipt(rid)
    assert r["pay_method"] == "aba" and r["status"] == "confirmed"
    assert any(x["id"] == rid for x in list_open_receipts(is_test=True))


def test_edit_fills_missing_amount(vendor):
    from accountant.db import add_receipt, edit_receipt, get_receipt
    rid = add_receipt(vendor_id=vendor, amount_cents=None, photo_sha="zz_sha_edit", is_test=True)
    edit_receipt(rid, amount_cents=5000)
    assert get_receipt(rid)["amount_cents"] == 5000
