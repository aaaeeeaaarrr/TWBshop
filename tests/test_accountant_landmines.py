"""Bedrock-audit accountant landmines F5/F6 (INERT accountant; staging). F6: propose_vendor can't mint a
duplicate active name (atomic claim-by-UNIQUE). F5: merge refuses an already-merged/inactive vendor, and
undo won't reactivate into a name-collision. conftest forces staging; skips if unavailable."""
import pytest


@pytest.fixture
def acc():
    try:
        from accountant.db import init_accounting_db
        from shared.database import _db
        init_accounting_db()
    except Exception as e:
        pytest.skip(f"staging DB unavailable: {e}")
    made: list[int] = []
    yield made
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_vendor_merges WHERE dup_id = ANY(%s) OR canonical_id = ANY(%s)",
                        (made, made))
            cur.execute("DELETE FROM acc_vendors WHERE id = ANY(%s)", (made,))


def test_propose_vendor_never_duplicates_active_name(acc):
    from accountant.db import propose_vendor
    a = propose_vendor("ZZ Landmine Dupe Co")
    b = propose_vendor("zz landmine dupe co")        # same name, different case → resolves to the same row
    acc += [a, b]
    assert a > 0 and a == b                           # F6: no second active vendor minted


def test_merge_refuses_already_merged_vendor(acc):
    from accountant.db import propose_vendor, merge_vendors
    a, b = propose_vendor("ZZ LM MergeA"), propose_vendor("ZZ LM MergeB")
    acc += [a, b]
    assert merge_vendors(a, b)["ok"] is True          # first merge: a → b, a deactivated
    r2 = merge_vendors(a, b)                            # F5: re-merging the now-inactive a is refused
    assert r2["ok"] is False and "inactive" in r2["reason"]


def test_undo_reactivates_and_is_idempotent(acc):
    """Normal merge of DIFFERENT-named vendors → undo reactivates the dup cleanly (no name collision, since
    F6 forbids same-name actives) and is idempotent (a second undo is a no-op)."""
    from accountant.db import propose_vendor, merge_vendors, undo_vendor_merge
    a, b = propose_vendor("ZZ LM UndoA"), propose_vendor("ZZ LM UndoB")
    acc += [a, b]
    mid = merge_vendors(a, b)["merge_id"]                 # a deactivated
    res = undo_vendor_merge(mid)
    assert res["ok"] is True and res["reactivated"] is True
    assert undo_vendor_merge(mid)["ok"] is False          # already undone → no-op (idempotent)
