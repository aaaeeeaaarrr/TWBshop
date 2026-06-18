"""Tests for stock/catalog.py + stock/catalog_data.py (staging; guards the catalog seed + read model).

Three guarantees:
  1. FIDELITY — the migrated catalog data still matches GM's `_STOCK_SEED` / `_STOCK_CATEGORIES`
     exactly (catches transcription drift before the integrator cutover removes the GM source).
  2. SEED — seed_catalog() populates acc_items and is idempotent (re-seed never duplicates/blanks).
  3. READ MODEL — overview/low_stock/reorder reflect on-hand via the ONE resolver, is_test-isolated.
Self-cleans its throwaway ZZTEST rows."""
import uuid

import pytest

from shared.database import _db, _STOCK_SEED, _STOCK_CATEGORIES
from shared import stock_shared as ss
from stock import catalog
from stock.catalog_data import CATALOG_ITEMS, CATEGORY_ORDER


# ── 1. fidelity to the GM source ────────────────────────────────────────────────

def test_catalog_matches_gm_seed_names_units_mins():
    gm = {name: (unit, float(min_n)) for (name, unit, min_n, _aliases) in _STOCK_SEED}
    mine = {it["name"]: (it["unit"], float(it["min_qty"])) for it in CATALOG_ITEMS}
    assert mine == gm   # same names, same unit + min_qty for every item


def test_catalog_categories_match_gm():
    gm_cat = {}
    for cat, names in _STOCK_CATEGORIES.items():
        for n in names:
            gm_cat[n] = cat
    for it in CATALOG_ITEMS:
        assert it["category"] == gm_cat.get(it["name"]), it["name"]


def test_category_order_covers_every_item():
    cats = {it["category"] for it in CATALOG_ITEMS}
    assert cats <= set(CATEGORY_ORDER)   # no item lands in an unordered category


# ── 2. seed is idempotent ───────────────────────────────────────────────────────

def test_seed_catalog_populates_and_is_idempotent():
    n = catalog.seed_catalog()
    assert n == len(CATALOG_ITEMS)
    sugar = ss.get_item_by_name("Sugar")
    assert sugar and sugar["category"] == "Baking & Dry" and sugar["unit"] == "kg"
    assert float(sugar["min_qty"]) == 5
    before = len(ss.list_items(active_only=False))
    catalog.seed_catalog()                       # re-seed
    after = len(ss.list_items(active_only=False))
    assert after == before                       # no duplicates (upsert on lower(name))


# ── 3. read model (is_test-isolated, self-cleaning) ─────────────────────────────

@pytest.fixture
def zz_item():
    ss.init_stock_shared_db()
    name = "ZZTEST_cat_" + uuid.uuid4().hex[:8]
    iid = ss.upsert_item(name, category="ZZTEST", unit="kg", min_qty=10)
    yield iid, name
    with _db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM stock_movements WHERE item_id=%s", (iid,))
        cur.execute("DELETE FROM acc_items WHERE id=%s", (iid,))


def _row(rows, iid):
    return next((r for r in rows if r["id"] == iid), None)


def test_overview_reflects_on_hand_and_low_flag(zz_item):
    iid, _ = zz_item
    ss.add_movement(iid, 4, "received", is_test=True)   # 4 < min 10 -> low
    r = _row(catalog.overview(is_test=True), iid)
    assert r and r["on_hand"] == 4.0 and r["low"] is True
    # real-side on-hand is isolated from the test movement
    assert _row(catalog.overview(is_test=False), iid)["on_hand"] == 0.0


def test_low_stock_and_reorder_use_the_brain(zz_item):
    iid, name = zz_item
    ss.add_movement(iid, 2, "received", is_test=True)    # on-hand 2, min 10 -> short 8
    assert any(r["id"] == iid for r in catalog.low_stock(is_test=True))
    order = catalog.reorder_list(is_test=True)
    mine = next((o for o in order if o["item"] == name), None)
    assert mine and mine["qty"] == 13                    # target 10*1.5=15, gap 15-2=13

    ss.add_movement(iid, 20, "received", is_test=True)   # on-hand 22 -> above min
    assert not any(r["id"] == iid for r in catalog.low_stock(is_test=True))
