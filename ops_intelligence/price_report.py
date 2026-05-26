"""
Supplier price comparison report.
Run interactively: python -c "from ops_intelligence.price_report import *; report()"
Or query: compare('cream cheese'), compare('salmon'), summary()
"""
import sys
sys.path.insert(0, '/root/TWBshop')
from shared.database import query_supplier_prices, _db


def compare(keyword: str) -> None:
    """Print price comparison for all suppliers stocking a product keyword."""
    rows = query_supplier_prices(keyword=keyword)
    if not rows:
        print(f"No price data found for: {keyword}")
        return
    print(f"\n=== '{keyword}' — {len(rows)} match(es) ===")
    print(f"{'Supplier':<28} {'Product':<45} {'Price':>8} {'Unit':<12} {'Date':<12} Notes")
    print("-" * 115)
    for r in rows:
        price_str = f"${r['price']:.2f}" if r['price'] else "—"
        print(
            f"{str(r['supplier_name']):<28} "
            f"{str(r['product_name'])[:44]:<45} "
            f"{price_str:>8} "
            f"{str(r['unit'] or ''):<12} "
            f"{str(r['price_date'] or ''):<12} "
            f"{str(r['price_notes'] or '')[:40]}"
        )


def summary() -> None:
    """Print a summary of the price database."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT supplier_name, COUNT(*) as items,
                       MAX(price_date) as latest_date,
                       COUNT(CASE WHEN price IS NOT NULL THEN 1 END) as priced
                FROM supplier_price_items
                GROUP BY supplier_name
                ORDER BY items DESC
            """)
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) as n FROM supplier_price_items")
            total = cur.fetchone()['n']

    print(f"\n=== Supplier Price Database — {total} total items ===")
    print(f"{'Supplier':<30} {'Items':>6} {'Priced':>7} {'Latest date'}")
    print("-" * 60)
    for r in rows:
        print(
            f"{r['supplier_name']:<30} "
            f"{r['items']:>6} "
            f"{r['priced']:>7} "
            f"{str(r['latest_date'] or '—')}"
        )


def cheapest(product_keyword: str, top_n: int = 5) -> None:
    """Show the cheapest suppliers for a product keyword, ranked by price."""
    rows = [r for r in query_supplier_prices(keyword=product_keyword) if r['price']]
    rows.sort(key=lambda r: r['price'])
    if not rows:
        print(f"No priced data for: {product_keyword}")
        return
    print(f"\nCheapest '{product_keyword}' (top {min(top_n, len(rows))})")
    for i, r in enumerate(rows[:top_n], 1):
        print(f"  {i}. {r['supplier_name']}: ${r['price']:.2f}/{r['unit'] or '?'}  — {r['product_name']}")


def report() -> None:
    """Print a quick overview of key products across all suppliers."""
    summary()
    for keyword in ["cream cheese", "salmon", "chocolate", "flour", "chicken", "wine", "beef"]:
        rows = query_supplier_prices(keyword=keyword)
        if rows:
            priced = [r for r in rows if r['price']]
            if priced:
                cheapest_r = min(priced, key=lambda r: r['price'])
                print(f"  {keyword}: cheapest = {cheapest_r['supplier_name']} ${cheapest_r['price']:.2f}/{cheapest_r['unit'] or '?'} ({len(rows)} matches)")
