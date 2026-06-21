"""§G read-priors foundation: the vendor item/price history + priors (read-side) and the pure Fix-flow
'did you mean?' price ranking. conftest forces staging; DB tests skip if it's unavailable."""
import pytest

from accountant.capture import did_you_mean


# ─────────────────────────── did_you_mean (pure) ───────────────────────────
def test_did_you_mean_ranks_by_price_proximity():
    hist = [{"name": "Potato", "price_cents": 120}, {"name": "Onion", "price_cents": 110},
            {"name": "Beef", "price_cents": 500}]
    assert did_you_mean(115, hist, limit=2) == ["Potato", "Onion"]   # the two nearest $1.15
    assert did_you_mean(115, hist, band_cents=10) == ["Potato", "Onion"]  # Beef out of band
    assert did_you_mean(None, hist) == []                            # no line price → no suggestion
    assert "Beef" in did_you_mean(490, hist, limit=1)               # nearest $4.90 → Beef


def test_did_you_mean_dedupes_names():
    hist = [{"name": "Potato", "price_cents": 120}, {"name": "Potato", "price_cents": 121}]
    assert did_you_mean(120, hist) == ["Potato"]


# ─────────────────────────── priors-into-read block (pure) ───────────────────────────
def test_vendor_priors_block_is_a_soft_hint_or_empty():
    from shared.ai_client import _vendor_priors_block
    assert _vendor_priors_block(None) == ""
    assert _vendor_priors_block({"items": [], "aliases": []}) == ""
    block = _vendor_priors_block({"vendor_name": "Atlas",
                                  "aliases": [{"orig": "ដំឡូង", "english": "potato"}],
                                  "items": [{"name": "Onion", "price_cents": 110}]})
    assert "Atlas" in block and "potato" in block and "Onion" in block
    assert "READ WHAT IS ACTUALLY WRITTEN" in block          # the anti-anchor guard must be present


# ─────────────────────────── Fix-flow did-you-mean rows (pure) ───────────────────────────
def test_dym_rows_only_low_confidence_priced_lines():
    from accountant.capture import dym_rows
    lines = [
        {"id": 11, "raw_name": "Chicken", "orig_name": "សាច់", "unit_price_cents": 115, "confident": False},
        {"id": 12, "raw_name": "Cheese", "orig_name": "Cheese", "unit_price_cents": 500, "confident": True},
        {"id": 13, "raw_name": "X", "orig_name": "", "unit_price_cents": 110, "confident": False},
    ]
    hist = [{"name": "Potato", "price_cents": 120}, {"name": "Onion", "price_cents": 110}]
    rows = dym_rows(7, lines, hist)
    assert len(rows) == 1                                     # only line 11 (low-confidence + has orig + price)
    labels = [lbl for (lbl, _) in rows[0]]
    data = [d for (_, d) in rows[0]]
    assert labels[0].startswith("#1 ")                       # labelled by the card's line position
    assert all(s.startswith("acc:dym:7_11_") for s in data)  # callback carries rid_lineid_idx (re-derived on apply)


# ─────────────────────────── vendor history + priors (staging) ───────────────────────────
@pytest.fixture
def priors_vendor():
    try:
        from accountant.db import init_accounting_db, vendor_link
        from shared.database import _db
        init_accounting_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    vid = vendor_link("ZZ Priors Vendor")
    yield vid
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_receipt_lines WHERE receipt_id IN "
                        "(SELECT id FROM acc_receipts WHERE vendor_id=%s)", (vid,))
            cur.execute("DELETE FROM acc_receipts WHERE vendor_id=%s", (vid,))
            cur.execute("DELETE FROM acc_vendors WHERE id=%s", (vid,))


def test_vendor_item_history_and_priors(priors_vendor):
    from accountant.db import add_receipt, save_receipt_lines, vendor_item_history, vendor_priors_for
    vid = priors_vendor
    rid = add_receipt(vendor_id=vid, amount_cents=350, photo_sha="zz_priors_1", is_test=True)
    save_receipt_lines(rid, [{"name": "Potato", "name_orig": "ដំឡូង", "unit_price": 1.20,
                              "line_total": 2.40, "qty": 2},
                             {"name": "Onion", "unit_price": 1.10, "line_total": 1.10, "qty": 1}],
                       "USD", vendor_id=vid)
    hist = {h["name"]: h["price_cents"] for h in vendor_item_history(vid)}
    assert hist.get("Potato") == 120 and hist.get("Onion") == 110     # latest unit prices, in cents
    priors = vendor_priors_for(vid)
    assert priors["vendor_name"] == "ZZ Priors Vendor"
    assert {i["name"] for i in priors["items"]} >= {"Potato", "Onion"}
