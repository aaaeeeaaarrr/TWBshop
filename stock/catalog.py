"""Stock catalog operations — seed `acc_items` and expose the read model.

Thin layer over `shared.stock_shared` (the catalog table + the one on-hand resolver). The `overview`
read model — every active item with its current on-hand + a low-stock flag — is the surface AppSheet
binds/syncs to (`stock.sync`) and the input to the reorder brain.
"""
from __future__ import annotations

from shared import stock_shared as ss
from stock import order_brain
from stock.catalog_data import CATALOG_ITEMS, CATEGORY_ORDER


def seed_catalog() -> int:
    """Upsert the canonical catalog into `acc_items` (idempotent — `upsert_item` COALESCEs so a
    re-seed never blanks owner edits). Ensures the shared schema first. Returns rows processed."""
    ss.init_stock_shared_db()
    for it in CATALOG_ITEMS:
        ss.upsert_item(it["name"], category=it.get("category"), unit=it.get("unit"),
                       min_qty=it.get("min_qty"), reorder_qty=it.get("reorder_qty"))
    return len(CATALOG_ITEMS)


def _num(v):
    return float(v) if v is not None else None


def overview(is_test: bool = False) -> list[dict]:
    """Every active catalog item with current on-hand + low flag, sorted by category display order
    then name. on-hand from the ONE resolver (SUM of stock_movements, is_test-scoped). This is the
    AppSheet-facing read model and the reorder input."""
    items = ss.list_items(active_only=True)
    oh = ss.on_hand_all(is_test=is_test)
    cat_rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    rows = []
    for it in items:
        on = oh.get(it["id"], 0.0)
        min_q = _num(it["min_qty"])
        rows.append({
            "id": it["id"],
            "name": it["name"],
            "category": it["category"],
            "unit": it["unit"],
            "min_qty": min_q,
            "reorder_qty": _num(it["reorder_qty"]),
            "on_hand": on,
            "low": (min_q is not None and on < min_q),
        })
    rows.sort(key=lambda r: (cat_rank.get(r["category"], len(CATEGORY_ORDER)),
                             (r["category"] or ""), r["name"]))
    return rows


def low_stock(is_test: bool = False) -> list[dict]:
    """Catalog items currently below their minimum (on_hand < min_qty)."""
    return [r for r in overview(is_test=is_test) if r["low"]]


def reorder_list(is_test: bool = False) -> list[dict]:
    """What to order now, via the order brain: [{item, unit, qty}], biggest shortfall first."""
    items = [{"item": r["name"], "unit": r["unit"], "min_n": r["min_qty"],
              "current_n": r["on_hand"]}
             for r in overview(is_test=is_test) if r["min_qty"] is not None]
    return order_brain.build_order_list(items)
