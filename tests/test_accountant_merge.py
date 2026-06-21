"""Vendor V4 (§G7): rename (self-healing alias) + the ATOMIC merge (moves financial history) + undo.
Staging only (conftest); before/after proof on real rows. Skips if the staging DB is unavailable."""
import pytest


@pytest.fixture
def two_vendors():
    try:
        from accountant.db import init_accounting_db, vendor_link
        from shared.database import _db
        init_accounting_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    dup = vendor_link("ZZ Dup Vendor")
    canon = vendor_link("ZZ Canonical Vendor")
    yield dup, canon
    ids = [dup, canon]
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_vendor_merges WHERE dup_id = ANY(%s) OR canonical_id = ANY(%s)",
                        (ids, ids))
            cur.execute("DELETE FROM acc_item_aliases WHERE vendor_key = ANY(%s)", (ids,))
            cur.execute("DELETE FROM acc_receipt_lines WHERE receipt_id IN "
                        "(SELECT id FROM acc_receipts WHERE vendor_id = ANY(%s))", (ids,))
            cur.execute("DELETE FROM acc_receipts WHERE vendor_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM acc_vendors WHERE id = ANY(%s)", (ids,))


def test_rename_keeps_old_name_as_alias(two_vendors):
    from accountant.db import get_vendor, rename_vendor, vendor_by_name
    dup, _ = two_vendors
    assert rename_vendor(dup, "ZZ Dup Renamed") is True
    assert get_vendor(dup)["name"] == "ZZ Dup Renamed"
    assert vendor_by_name("ZZ Dup Vendor")["id"] == dup     # the OLD name still resolves (now an alias)


def test_merge_moves_receipts_and_deactivates_dup(two_vendors):
    from accountant.db import add_receipt, get_receipt, get_vendor, merge_vendors, vendor_by_name
    dup, canon = two_vendors
    rid = add_receipt(vendor_id=dup, amount_cents=500, photo_sha="zz_merge_1", is_test=True)
    res = merge_vendors(dup, canon, by=42)
    assert res["ok"] and res["receipts"] == 1
    assert get_receipt(rid)["vendor_id"] == canon           # receipt repointed dup → canonical
    assert get_vendor(dup)["active"] is False               # dup deactivated
    assert vendor_by_name("ZZ Dup Vendor")["id"] == canon   # the dup's name now folds to the canonical


def test_merge_same_vendor_is_rejected(two_vendors):
    from accountant.db import merge_vendors
    dup, _ = two_vendors
    assert merge_vendors(dup, dup)["ok"] is False


def test_merge_then_undo_restores_and_is_idempotent(two_vendors):
    from accountant.db import add_receipt, get_receipt, get_vendor, merge_vendors, undo_vendor_merge
    dup, canon = two_vendors
    rid = add_receipt(vendor_id=dup, amount_cents=700, photo_sha="zz_merge_2", is_test=True)
    res = merge_vendors(dup, canon, by=42)
    undo = undo_vendor_merge(res["merge_id"])
    assert undo["ok"] and get_receipt(rid)["vendor_id"] == dup    # receipt back on the dup
    assert get_vendor(dup)["active"] is True                      # dup reactivated
    assert undo_vendor_merge(res["merge_id"])["ok"] is False      # idempotent — no double-undo
