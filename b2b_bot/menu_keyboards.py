"""B2B menu — in-memory cart state, category/item data, and keyboard builders."""

import calendar
import time
from datetime import date, datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters as _filters

from b2b_bot.menu import B2B_MENU, _BUN_PRICE_BY_GRAMS
from b2b_bot.cake_menu import B2B_CAKE_MENU
from b2b_bot.pricing import item_price, order_total, FREE_DELIVERY_THRESHOLD
from shared.database import get_b2b_customer

# ── In-memory state ───────────────────────────────────────────────────────────
_cart: dict[int, dict[str, int]] = {}     # {chat_id: {item_key: qty}}
_qty_pending: dict[int, dict] = {}        # {chat_id: state dict}
_menu_msg: dict[int, int] = {}            # {chat_id: message_id of active menu}
_editing_session: dict[int, str] = {}     # {chat_id: session_key being replaced}
_cart_time: dict[int, str] = {}           # {chat_id: delivery time  e.g. "8:00am"}
_cart_date: dict[int, str] = {}           # {chat_id: delivery date  e.g. "2026-05-25"}
_cart_method: dict[int, str] = {}         # {chat_id: "pickup" | "delivery"}
_last_menu_prompt: dict[int, float] = {}  # {chat_id: monotonic time of last nudge}

# 9pm Phnom Penh = 14:00 UTC — orders locked after this hour
_LOCK_HOUR_UTC = 14

# How long (seconds) before the menu nudge fires again for the same chat
_MENU_PROMPT_COOLDOWN_SEC = 6 * 3600

# 6:00am–6:00pm in 15-minute steps, stored as "HHMM" for compact callback data
_DELIVERY_TIME_CODES: list[str] = [
    f"{h:02d}{m:02d}"
    for h in range(6, 19)
    for m in (0, 15, 30, 45)
    if not (h == 18 and m > 0)
]


def _format_time(hhmm: str) -> str:
    """Convert "HHMM" (24h) → "H:MMam/pm" display label."""
    h, m = int(hhmm[:2]), int(hhmm[2:])
    if h < 12:
        return f"{h}:{m:02d}am"
    if h == 12:
        return f"12:{m:02d}pm"
    return f"{h - 12}:{m:02d}pm"


def _orders_locked() -> bool:
    return datetime.now(timezone.utc).hour >= _LOCK_HOUR_UTC


# ── Cart accessors ────────────────────────────────────────────────────────────

def _get_cart_time(chat_id: int) -> str:
    t = _cart_time.get(chat_id)
    if t:
        return t
    customer = get_b2b_customer(chat_id)
    if customer and customer.get("delivery_time"):
        return customer["delivery_time"]
    return "8:00am"


def _get_cart_date(chat_id: int) -> str:
    d = _cart_date.get(chat_id)
    if d:
        return d
    return (date.today() + timedelta(days=1)).isoformat()


def _get_cart_method(chat_id: int) -> str | None:
    m = _cart_method.get(chat_id)
    if m:
        return m
    customer = get_b2b_customer(chat_id)
    if customer and customer.get("delivery_method"):
        return customer["delivery_method"]
    return None


def _delivery_date_label(iso_date: str) -> str:
    d = date.fromisoformat(iso_date)
    if d == date.today() + timedelta(days=1):
        return "Tomorrow"
    return d.strftime("%a %d %b")


# ── Filter ────────────────────────────────────────────────────────────────────
class _QtyPendingFilter(_filters.MessageFilter):
    def filter(self, message):
        return bool(message.chat and message.chat.id in _qty_pending)

qty_pending_filter = _QtyPendingFilter()


# ── Category layout ───────────────────────────────────────────────────────────
_CATEGORIES: dict[str, dict] = {
    "breads": {
        "emoji": "🍞", "label": "Breads & Loaves",
        "items": ["french baguette", "multigrain baguette", "focaccia", "multigrain loaf", "bagel", "croutons", "rusk"],
    },
    "pastries": {
        "emoji": "🥐", "label": "Pastries",
        "items": ["croissant", "pain au chocolat"],
    },
    "minis": {
        "emoji": "🥐", "label": "Mini Pastries",
        "items": ["mini croissant", "mini chocolatin", "mini almond croissant", "mini almond chocolatin", "mini ham cheese croissant"],
        "note": "Min. 100pc · 48h advance order",
    },
    "cakes": {
        "emoji": "🎂", "label": "Full Cakes",
        "items": [k for k, v in B2B_CAKE_MENU.items() if v["cake_category"] == "A"],
    },
    "desserts": {
        "emoji": "🍮", "label": "Desserts / Cake Slices",
        "items": [k for k, v in B2B_CAKE_MENU.items() if v["cake_category"] in ("B", "C")],
    },
}

_ALL_ITEMS = {item for cat in _CATEGORIES.values() for item in cat["items"]}
_SLUG      = {name: name.replace(" ", "_") for name in _ALL_ITEMS}
_NAME      = {v: k for k, v in _SLUG.items()}

# ── Bun / roll config ─────────────────────────────────────────────────────────
_BUNS: dict[str, dict] = {
    "burger": {
        "emoji": "🍔", "label": "Burger Buns",
        "item": "burger bun",
        "sizes": [
            {"grams": 70, "label": "70g — Standard"},
            {"grams": 40, "label": "40g — Slider"},
        ],
    },
    "roll": {
        "emoji": "🥖", "label": "Soft Rolls",
        "item": "hotdog roll",
        "sizes": [
            {"grams": 55, "label": "55g — Small"},
            {"grams": 75, "label": "75g — Large"},
        ],
    },
}

def _bun_price(grams: int) -> float:
    return _BUN_PRICE_BY_GRAMS.get(grams, round(grams * 0.004, 2))


# ── Display helpers ───────────────────────────────────────────────────────────

def _price_label(name: str) -> str:
    if name in B2B_MENU:
        d = B2B_MENU[name]
        return f"${d['price']:.2f}/{d['unit']}" if d.get("unit") else f"${d['price']:.2f}"
    d = B2B_CAKE_MENU[name]
    if d["cake_category"] == "A":
        return f"${d['price_full']:.2f}/cake"
    if d["cake_category"] == "B":
        return f"${d['price_piece']:.2f}/pc or ${d['price_tray']:.2f}/tray"
    return f"${d['price_piece']:.2f}/pc"


def _cart_block(chat_id: int) -> str:
    cart = _cart.get(chat_id, {})
    if not cart:
        return "🛒 Cart empty"
    lines = []
    bread, cake = [], []
    for key, qty in cart.items():
        if "|" in key:
            item_name, grams_str = key.split("|", 1)
            grams = int(grams_str)
            it = {"item": item_name, "qty": qty, "grams": grams, "notes": None}
            bread.append(it)
            lines.append(f"  {qty}× {item_name} {grams}g — ${_bun_price(grams) * qty:.2f}")
        elif key in B2B_MENU:
            it = {"item": key, "qty": qty, "grams": B2B_MENU[key].get("standard_grams"), "notes": None}
            bread.append(it)
            lines.append(f"  {qty}× {key} — ${item_price(it):.2f}")
        else:
            d = B2B_CAKE_MENU[key]
            ot = "piece" if d["cake_category"] in ("B", "C") else "full"
            it = {"item": key, "qty": qty, "order_type": ot}
            cake.append(it)
            lines.append(f"  {qty}× {key} — ${item_price(it):.2f}")
    total      = order_total(bread, cake)
    time_str   = _get_cart_time(chat_id)
    date_label = _delivery_date_label(_get_cart_date(chat_id))
    method     = _get_cart_method(chat_id)
    method_label = "Delivery" if method == "delivery" else "Pickup" if method == "pickup" else "?"
    return "🛒 Cart:\n" + "\n".join(lines) + f"\n  Total: ${total:.2f}\n  🕐 {method_label} · {date_label} at {time_str}"


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _category_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    cart = _cart.get(chat_id, {})
    rows = []
    for key, cat in _CATEGORIES.items():
        count = sum(cart.get(n, 0) for n in cat["items"])
        badge = f" ({count})" if count else ""
        rows.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['label']}{badge}",
            callback_data=f"bm_cat_{key}",
        )])
    bun_count = sum(qty for k, qty in cart.items() if "|" in k)
    bun_badge = f" ({bun_count}pc)" if bun_count else ""
    rows.append([InlineKeyboardButton(
        f"🍔 Buns & Rolls{bun_badge}",
        callback_data="bm_buns",
    )])
    if cart:
        time_str     = _get_cart_time(chat_id)
        date_label   = _delivery_date_label(_get_cart_date(chat_id))
        method       = _get_cart_method(chat_id)
        method_label = "Delivery" if method == "delivery" else "Pickup" if method == "pickup" else "Set delivery"
        rows.append([InlineKeyboardButton(
            f"🟡 {method_label} · {date_label} at {time_str}",
            callback_data="bm_time_select",
        )])
        rows.append([
            InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"),
            InlineKeyboardButton("🗑 Empty Cart",    callback_data="bm_empty_cart"),
        ])
    return InlineKeyboardMarkup(rows)


def _item_keyboard(cat_key: str, chat_id: int) -> InlineKeyboardMarkup:
    cart = _cart.get(chat_id, {})
    rows = []
    for name in _CATEGORIES[cat_key]["items"]:
        qty    = cart.get(name, 0)
        slug   = _SLUG[name]
        suffix = f"  ✓ ×{qty}" if qty else ""
        label  = f"{name}{suffix}\n{_price_label(name)}"
        rows.append([InlineKeyboardButton(
            label,
            callback_data=f"bm_qty_{slug}_{cat_key}",
        )])
    nav = [InlineKeyboardButton("← Back", callback_data="bm_back")]
    if cart:
        nav.append(InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _bun_page_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    cart = _cart.get(chat_id, {})
    rows = []
    for bun_key, bun in _BUNS.items():
        count = sum(qty for k, qty in cart.items() if k.startswith(f"{bun['item']}|"))
        badge = f" ({count}pc)" if count else ""
        rows.append([InlineKeyboardButton(
            f"{bun['emoji']} {bun['label']}{badge}",
            callback_data=f"bm_bun_{bun_key}",
        )])
    nav = [InlineKeyboardButton("← Back", callback_data="bm_back")]
    if cart:
        nav.append(InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _bun_size_keyboard(bun_key: str, chat_id: int) -> InlineKeyboardMarkup:
    bun  = _BUNS[bun_key]
    cart = _cart.get(chat_id, {})
    rows = []
    for size in bun["sizes"]:
        cart_key = f"{bun['item']}|{size['grams']}"
        qty      = cart.get(cart_key, 0)
        price    = _bun_price(size["grams"])
        suffix   = f" ✓×{qty}" if qty else ""
        label    = f"{size['label']}\n${price:.2f}{suffix}"
        rows.append([InlineKeyboardButton(
            label,
            callback_data=f"bm_bun_size_{bun_key}_{size['grams']}",
        )])
    rows.append([InlineKeyboardButton(
        "Other Grams",
        callback_data=f"bm_bun_other_{bun_key}",
    )])
    nav = [InlineKeyboardButton("← Buns", callback_data="bm_buns")]
    if cart:
        nav.append(InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _bun_gram_grid_keyboard(bun_key: str, chat_id: int) -> InlineKeyboardMarkup:
    bun  = _BUNS[bun_key]
    cart = _cart.get(chat_id, {})
    rows = []
    row  = []
    for grams, price in sorted(_BUN_PRICE_BY_GRAMS.items()):
        cart_key = f"{bun['item']}|{grams}"
        qty      = cart.get(cart_key, 0)
        label    = f"{grams}g\n${price:.2f}" + (f" ✓×{qty}" if qty else "")
        row.append(InlineKeyboardButton(
            label,
            callback_data=f"bm_bun_size_{bun_key}_{grams}",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = [InlineKeyboardButton(f"← {bun['label']}", callback_data=f"bm_bun_{bun_key}")]
    if cart:
        nav.append(InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _date_picker_keyboard() -> InlineKeyboardMarkup:
    today      = date.today()
    tomorrow   = today + timedelta(days=1)
    curr_month = today.replace(day=1)
    next_month = (curr_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"Tomorrow ({tomorrow.strftime('%a %d %b')})",
            callback_data="bm_date_tmrw",
        )],
        [
            InlineKeyboardButton(
                curr_month.strftime("%B"),
                callback_data=f"bm_date_m_{curr_month.strftime('%Y%m')}",
            ),
            InlineKeyboardButton(
                next_month.strftime("%B"),
                callback_data=f"bm_date_m_{next_month.strftime('%Y%m')}",
            ),
        ],
        [InlineKeyboardButton("← Back to Menu", callback_data="bm_back")],
    ])


def _day_picker_keyboard(yyyymm: str) -> InlineKeyboardMarkup:
    year, month = int(yyyymm[:4]), int(yyyymm[4:])
    tomorrow = date.today() + timedelta(days=1)
    _, days_in_month = calendar.monthrange(year, month)
    rows = []
    row  = []
    for d in range(1, days_in_month + 1):
        day_date = date(year, month, d)
        if day_date < tomorrow:
            continue
        row.append(InlineKeyboardButton(
            str(d),
            callback_data=f"bm_date_d_{day_date.strftime('%Y%m%d')}",
        ))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data="bm_time_select")])
    return InlineKeyboardMarkup(rows)


def _time_picker_keyboard(date_str: str) -> InlineKeyboardMarkup:
    rows = []
    row  = []
    for code in _DELIVERY_TIME_CODES:
        row.append(InlineKeyboardButton(
            _format_time(code),
            callback_data=f"bm_dt_{date_str}_{code}",
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
    back_cb = "bm_time_select" if date_str == tomorrow_str else f"bm_date_m_{date_str[:6]}"
    rows.append([InlineKeyboardButton("← Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _method_picker_keyboard(date_str: str, time_code: str, cart_total: float) -> InlineKeyboardMarkup:
    free = cart_total >= FREE_DELIVERY_THRESHOLD
    delivery_label = "🚛 Delivery (free)" if free else f"🚛 Delivery (fee on orders under ${FREE_DELIVERY_THRESHOLD:.0f})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏪 Pickup (free)", callback_data=f"bm_method_{date_str}_{time_code}_pickup")],
        [InlineKeyboardButton(delivery_label,      callback_data=f"bm_method_{date_str}_{time_code}_delivery")],
        [InlineKeyboardButton("← Back",            callback_data=f"bm_date_d_{date_str}")],
    ])


def _existing_orders_keyboard(sessions: list[dict], locked: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("➕ New Order", callback_data="bm_new_order")]]
    if not locked:
        for i, s in enumerate(sessions):
            rows.append([InlineKeyboardButton(
                f"✏️ Edit Order #{i + 1}",
                callback_data=f"bm_edit_session_{i}",
            )])
    return InlineKeyboardMarkup(rows)
