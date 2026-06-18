"""Shared stock tables — round-trip + is_test isolation (staging). Guards shared/stock_shared.py.

Proves the S5/S4 guarantees: on-hand has ONE resolver (= SUM of qty_delta) and is_test movements
never leak into real on-hand. Self-cleans (deletes its own rows) so staging stays tidy."""
import uuid

import pytest

from shared.database import _db
from shared import stock_shared as ss


@pytest.fixture
def item_id():
    ss.init_stock_shared_db()  # idempotent
    name = "ZZTEST_item_" + uuid.uuid4().hex[:8]
    iid = ss.upsert_item(name, category="ZZTEST", unit="kg", min_qty=5, reorder_qty=20)
    yield iid
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM stock_movements WHERE item_id=%s", (iid,))
            cur.execute("DELETE FROM acc_items WHERE id=%s", (iid,))


def test_upsert_is_idempotent_and_coalesces(item_id):
    it = ss.get_item(item_id)
    assert it["unit"] == "kg" and float(it["min_qty"]) == 5
    # re-upsert the same name with a partial update -> same id, existing fields preserved
    same = ss.upsert_item(it["name"], reorder_qty=30)
    assert same == item_id
    it2 = ss.get_item(item_id)
    assert it2["unit"] == "kg"                  # COALESCE kept it (no blanking)
    assert float(it2["reorder_qty"]) == 30      # updated


def test_on_hand_is_sum_of_movements(item_id):
    ss.add_movement(item_id, 10, "received", unit="kg", source="receipt")
    ss.add_movement(item_id, -3, "used", unit="kg", source="count")
    assert ss.on_hand(item_id) == 7.0
    assert ss.on_hand_all(is_test=False).get(item_id) == 7.0


def test_is_test_movements_are_isolated(item_id):
    ss.add_movement(item_id, 8, "received", is_test=False)
    ss.add_movement(item_id, 100, "counted", is_test=True)
    assert ss.on_hand(item_id, is_test=False) == 8.0     # test movement excluded
    assert ss.on_hand(item_id, is_test=True) == 100.0    # only the test movement
