"""core.stock — a real, minimal inventory domain (org-scoped, channel-free): item catalog · par levels · stock
counts · low-stock reorder list. Shadow-style — its OWN tables (core_stock_items / core_stock_counts), NOT
TWB's live stock (gm_bot/stock.py). No model calls. Tables created by core.db.init_core_db."""
from shared.database import _db


def add_item(org_id, name, unit="unit", category=None, par_level=0, unit_cost=0) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_stock_items (org_id, name, unit, category, par_level, unit_cost) "
                        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING item_id",
                        (org_id, name.strip(), unit.strip() or "unit", (category or None),
                         par_level or 0, unit_cost or 0))
            return cur.fetchone()["item_id"]


def list_items(org_id, active_only=True) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT item_id, name, unit, category, par_level, on_hand, unit_cost, active "
                        "FROM core_stock_items WHERE org_id=%s" + (" AND active" if active_only else "") +
                        " ORDER BY name", (org_id,))
            return [dict(r) for r in cur.fetchall()]


def stock_summary(org_id) -> dict:
    """Headline stock numbers (read-only): item_count · low_count · total_value (Σ on_hand × unit_cost)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n, COALESCE(SUM(on_hand * unit_cost), 0) val "
                        "FROM core_stock_items WHERE org_id=%s AND active", (org_id,))
            r = cur.fetchone()
    return {"item_count": r["n"], "total_value": float(r["val"] or 0), "low_count": len(low_stock_items(org_id))}


def add_price(org_id, item_id, supplier, price) -> int:
    """Record a supplier's price for an item (append-only history)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_stock_prices (org_id, item_id, supplier, price) "
                        "VALUES (%s,%s,%s,%s) RETURNING price_id", (org_id, item_id, supplier.strip(), price))
            return cur.fetchone()["price_id"]


def item_prices(org_id, item_id) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT supplier, price, seen_at FROM core_stock_prices "
                        "WHERE org_id=%s AND item_id=%s ORDER BY price ASC", (org_id, item_id))
            return [dict(r) for r in cur.fetchall()]


def cheapest_overview(org_id) -> dict:
    """item_id → {supplier, price} for the cheapest recorded price per item (the 'buy from the cheapest' goal)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ON (item_id) item_id, supplier, price FROM core_stock_prices "
                        "WHERE org_id=%s ORDER BY item_id, price ASC, seen_at DESC", (org_id,))
            return {r["item_id"]: {"supplier": r["supplier"], "price": float(r["price"])} for r in cur.fetchall()}


def set_par(org_id, item_id, par_level) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_stock_items SET par_level=%s WHERE org_id=%s AND item_id=%s",
                        (par_level or 0, org_id, item_id))


def deactivate_item(org_id, item_id) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_stock_items SET active=FALSE WHERE org_id=%s AND item_id=%s",
                        (org_id, item_id))


def record_count(org_id, item_id, qty, note=None) -> int:
    """Record a stock count: append a count row (history) AND set the item's on_hand — one transaction."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_stock_counts (org_id, item_id, qty, note) VALUES (%s,%s,%s,%s) "
                        "RETURNING count_id", (org_id, item_id, qty, note))
            cid = cur.fetchone()["count_id"]
            cur.execute("UPDATE core_stock_items SET on_hand=%s WHERE org_id=%s AND item_id=%s",
                        (qty, org_id, item_id))
            return cid


def low_stock_items(org_id) -> list:
    """Active items at/below their par level (the reorder list)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT item_id, name, unit, par_level, on_hand FROM core_stock_items "
                        "WHERE org_id=%s AND active AND par_level > 0 AND on_hand <= par_level ORDER BY name",
                        (org_id,))
            return [dict(r) for r in cur.fetchall()]
