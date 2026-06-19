"""Tests for stock/sync.py (staging; the Postgres side + the AppSheet client contract).

Proves: a count appends the delta as a movement (on-hand reconciliation), a matching re-count is a
no-op, and the unwired AppSheet client fails loudly / is skipped by run_sync. Self-cleaning."""
import uuid
from datetime import date

import pytest

from shared.database import _db
from shared import stock_shared as ss
from stock import sync
from stock import db as stockdb


@pytest.fixture
def zz_item():
    ss.init_stock_shared_db()
    stockdb.init_stock_db()
    iid = ss.upsert_item("ZZTEST_sync_" + uuid.uuid4().hex[:8], unit="kg", min_qty=5)
    yield iid
    with _db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM stock_count_events WHERE item_id=%s", (iid,))
        cur.execute("DELETE FROM stock_movements WHERE item_id=%s", (iid,))
        cur.execute("DELETE FROM acc_items WHERE id=%s", (iid,))


def test_apply_count_appends_delta_then_noop_on_match(zz_item):
    iid = zz_item
    r1 = sync.apply_count(iid, 10, is_test=True)         # 0 -> 10
    assert r1["before"] == 0.0 and r1["delta"] == 10.0 and r1["movement_id"] is not None
    assert r1["event_id"] is not None                    # the count event is always recorded
    assert ss.on_hand(iid, is_test=True) == 10.0

    r2 = sync.apply_count(iid, 10, is_test=True)         # same count -> no movement, event upserts
    assert r2["delta"] == 0.0 and r2["movement_id"] is None
    assert r2["event_id"] == r1["event_id"]              # same item+day -> same event row
    assert ss.on_hand(iid, is_test=True) == 10.0

    r3 = sync.apply_count(iid, 7, is_test=True)          # down to 7 -> delta -3
    assert r3["delta"] == -3.0
    assert ss.on_hand(iid, is_test=True) == 7.0
    # on-hand and the recorded count agree (S4: the shown number == the true number)
    assert stockdb.counts_on(r3["count_date"], is_test=True)[iid] == 7.0


def test_apply_count_is_test_isolated(zz_item):
    iid = zz_item
    sync.apply_count(iid, 8, is_test=True)
    assert ss.on_hand(iid, is_test=False) == 0.0         # real side untouched


def test_apply_counts_batch(zz_item):
    iid = zz_item
    out = sync.apply_counts([{"item_id": iid, "counted_qty": 5}], is_test=True)
    assert len(out) == 1 and ss.on_hand(iid, is_test=True) == 5.0


def test_apply_count_reconciles_inline(zz_item):
    iid = zz_item
    sync.apply_count(iid, 6, is_test=True)
    assert stockdb.pending_counts(is_test=True) == []     # nothing left for the worker to reconcile


def test_reconcile_direct_count_into_ledger(zz_item):
    iid = zz_item
    # simulate an AppSheet direct write: a count row with no movement, reconciled=False
    stockdb.record_count_event(iid, 9, date(2026, 6, 19), source="appsheet", is_test=True)
    assert ss.on_hand(iid, is_test=True) == 0.0           # not in the ledger yet
    assert any(e["item_id"] == iid for e in stockdb.pending_counts(is_test=True))

    res = sync.reconcile_counts(is_test=True)
    assert res["changed"] >= 1
    assert ss.on_hand(iid, is_test=True) == 9.0           # now reflected
    assert stockdb.pending_counts(is_test=True) == []     # idempotent: nothing pending after
    assert sync.reconcile_counts(is_test=True)["changed"] == 0   # second pass is a no-op


def test_recount_rearms_reconcile(zz_item):
    iid = zz_item
    d = date(2026, 6, 19)                                  # one date for both -> same-day upsert
    sync.apply_count(iid, 10, count_date=d, is_test=True)  # reconciled inline -> on-hand 10
    stockdb.record_count_event(iid, 4, d, source="appsheet", is_test=True)   # fresh direct re-count
    assert any(e["item_id"] == iid for e in stockdb.pending_counts(is_test=True))
    sync.reconcile_counts(is_test=True)
    assert ss.on_hand(iid, is_test=True) == 4.0           # corrected down to the new count


def test_appsheet_client_unwired_contract():
    c = sync.AppSheetClient()
    assert c.configured is False
    with pytest.raises(NotImplementedError):
        c.fetch_counts()
    with pytest.raises(NotImplementedError):
        c.push_overview([])


def test_run_sync_skips_when_unconfigured():
    res = sync.run_sync(sync.AppSheetClient())
    assert res["synced"] is False
