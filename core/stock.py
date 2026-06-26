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


def receive_purchase(org_id, item_id, qty, total_cost, supplier=None, actor=None, client_key=None) -> int:
    """Receive a restock: add qty to on_hand AND log an expense for the cost — ONE transaction (the cross-domain
    stock↔accountant link that closes the reorder loop). Returns the expense_id. With a client_key the expense
    insert is the idempotency CLAIM: a replay re-applies NOTHING (no phantom restock + no phantom expense)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM core_stock_items WHERE org_id=%s AND item_id=%s", (org_id, item_id))
            r = cur.fetchone()
            name = r["name"] if r else None
            cur.execute("INSERT INTO core_expenses (org_id, supplier, category, amount, note, actor, client_key) "
                        "VALUES (%s,%s,'stock',%s,%s,%s,%s) "
                        "ON CONFLICT (org_id, client_key) WHERE client_key IS NOT NULL DO NOTHING RETURNING expense_id",
                        (org_id, supplier or None, total_cost, "restock %s x%s" % (name, qty), actor, client_key))
            row = cur.fetchone()
            if row is None:                                  # replay — the restock already happened; don't double it
                cur.execute("SELECT expense_id FROM core_expenses WHERE org_id=%s AND client_key=%s",
                            (org_id, client_key))
                return cur.fetchone()["expense_id"]
            cur.execute("UPDATE core_stock_items SET on_hand = on_hand + %s WHERE org_id=%s AND item_id=%s",
                        (qty, org_id, item_id))
            return row["expense_id"]


def stock_variance(org_id) -> list:
    """Items whose LATEST physical count came up SHORT of the book (shrinkage): [{item, counted, book, variance,
    when}], variance < 0. variance = counted - book_before; the book = last count + receives − sales. Skips the
    first (baseline) count of each item. The killer loss-prevention query."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ON (c.item_id) c.item_id, i.name nm, c.qty, c.book_before, c.counted_at, "
                        "(SELECT MAX(c2.counted_at) FROM core_stock_counts c2 WHERE c2.org_id=c.org_id "
                        " AND c2.item_id=c.item_id AND c2.counted_at < c.counted_at) prev_at "
                        "FROM core_stock_counts c "
                        "JOIN core_stock_items i ON i.org_id=c.org_id AND i.item_id=c.item_id "
                        "WHERE c.org_id=%s AND c.book_before IS NOT NULL "
                        "ORDER BY c.item_id, c.counted_at DESC", (org_id,))
            rows = cur.fetchall()
    out = []
    for r in rows:
        var = float(r["qty"]) - float(r["book_before"])
        if var < 0:                                            # came up short → possible theft / waste / error
            out.append({"item": r["nm"], "item_id": r["item_id"], "counted": float(r["qty"]),
                        "book": float(r["book_before"]), "variance": var, "when": str(r["counted_at"])[:16],
                        "since": r["prev_at"], "at": r["counted_at"]})    # raw window [since, at] for who-was-on-shift
    return out


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


def record_count(org_id, item_id, qty, note=None, actor=None, client_key=None) -> int:
    """Record a stock count: capture the book on-hand BEFORE (for variance), append a count row, set on_hand —
    one transaction. variance = counted - book_before (negative = came up short = shrinkage). With a client_key
    a replay re-applies NOTHING (the original count stands, on_hand untouched) — the offline-queue S2 cure."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT on_hand FROM core_stock_items WHERE org_id=%s AND item_id=%s", (org_id, item_id))
            r = cur.fetchone()
            book = r["on_hand"] if r else None
            cur.execute("INSERT INTO core_stock_counts (org_id, item_id, qty, note, actor, book_before, client_key) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (org_id, client_key) WHERE client_key IS NOT NULL DO NOTHING RETURNING count_id",
                        (org_id, item_id, qty, note, actor, book, client_key))
            row = cur.fetchone()
            if row is None:                                  # idempotent replay → the original count, on_hand untouched
                cur.execute("SELECT count_id FROM core_stock_counts WHERE org_id=%s AND client_key=%s",
                            (org_id, client_key))
                return cur.fetchone()["count_id"]
            cid = row["count_id"]
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
