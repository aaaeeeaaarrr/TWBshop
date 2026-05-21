"""Price calculation for B2B orders (breads + cakes)."""

from b2b_bot.menu import B2B_MENU
from b2b_bot.cake_menu import B2B_CAKE_MENU

FREE_DELIVERY_THRESHOLD = 10.00


def item_price(it: dict) -> float:
    """Return total price for one order line item."""
    item_def = B2B_MENU.get(it["item"]) or B2B_CAKE_MENU.get(it["item"], {})
    qty = it.get("qty", 1)
    order_type = it.get("order_type")

    # Cake: full or sliced whole cake
    if order_type in ("full", "sliced"):
        return round(qty * item_def.get("price_full", 0), 2)

    # Cake: full brownie tray
    if order_type == "tray":
        return round(qty * item_def.get("price_tray", 0), 2)

    # Cake: individual pieces or brownie pieces
    if order_type == "piece":
        return round(qty * item_def.get("price_piece", 0), 2)

    # Bread: gram-based pricing (burger bun, slider bun, hotdog roll)
    grams = it.get("grams")
    price_table = item_def.get("price_by_grams", {})
    if grams and price_table:
        unit_price = price_table.get(grams, item_def.get("price", 0))
        return round(qty * unit_price, 2)

    # Bread: standard price per unit
    return round(qty * item_def.get("price", 0), 2)


def order_total(bread_items: list[dict], cake_items: list[dict]) -> float:
    return round(sum(item_price(it) for it in bread_items + cake_items), 2)


def price_summary(total: float) -> str:
    """Return the price block shown at the bottom of every confirmation."""
    if total >= FREE_DELIVERY_THRESHOLD:
        delivery_line = "Delivery: Free"
        total_line    = f"Total: ${total:.2f}"
    else:
        delivery_line = "Delivery: Fee applies (order under $10)"
        total_line    = f"Total: ${total:.2f} + delivery fee"

    return f"Subtotal: ${total:.2f}\n{delivery_line}\n{total_line}"
