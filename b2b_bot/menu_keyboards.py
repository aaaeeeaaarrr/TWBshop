"""B2B menu — in-memory cart state, category/item data, and keyboard builders."""

import calendar
import time
from datetime import date, datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters as _filters

from b2b_bot.menu import B2B_MENU, _BUN_PRICE_BY_GRAMS, MINI_ITEMS
from b2b_bot.cake_menu import B2B_CAKE_MENU
from b2b_bot.pricing import item_price, order_total, FREE_DELIVERY_THRESHOLD
from shared.database import get_b2b_customer

# ── In-memory state ───────────────────────────────────────────────────────────
_cart: dict[int, dict[str, int]] = {}         # {chat_id: {item_key: qty}}
_qty_pending: dict[int, dict] = {}            # {chat_id: state dict}
_menu_msg: dict[int, int] = {}                # {chat_id: message_id of active menu}
_editing_session: dict[int, str] = {}         # {chat_id: session_key being replaced}
_cart_time: dict[int, str] = {}               # {chat_id: delivery time  e.g. "8:00am"}
_cart_date: dict[int, str] = {}               # {chat_id: delivery date  e.g. "2026-05-25"}
_cart_method: dict[int, str] = {}             # {chat_id: "pickup" | "delivery"}
_last_menu_prompt: dict[int, float] = {}      # {chat_id: monotonic time of last nudge}
_confirm_flow_mode: dict[int, bool] = {}      # {chat_id: True = after method pick, call _do_confirm}
_recurring_days: dict[int, set] = {}          # {chat_id: set of selected day abbrevs}
_recurring_pending: dict[int, dict] = {}      # {chat_id: pending recurring order config}

# 10:10pm Phnom Penh = 15:10 UTC — orders locked after this time
_LOCK_HOUR_UTC    = 15
_LOCK_MINUTE_UTC  = 10

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
    now = datetime.now(timezone.utc)
    return now.hour > _LOCK_HOUR_UTC or (now.hour == _LOCK_HOUR_UTC and now.minute >= _LOCK_MINUTE_UTC)


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
        "items": ["French Baguette", "Multigrain Baguette", "Focaccia", "Multigrain Loaf", "Bagel", "Croutons", "Rusk"],
    },
    "pastries": {
        "emoji": "🥐", "label": "Pastries",
        "items": ["Croissant", "Pain Au Chocolat"],
    },
    "minis": {
        "emoji": "🥐", "label": "Mini Pastries",
        "items": ["Mini Croissant", "Mini Chocolatin", "Mini Almond Croissant", "Mini Almond Chocolatin", "Mini Ham Cheese Croissant"],
        "note": [("⚠️", "Min. 100pc"), ("⚠️", "48h Advance Order")],
    },
    "cakes": {
        "emoji": "🎂", "label": "Full Cakes",
        "items": [k for k, v in B2B_CAKE_MENU.items() if v["cake_category"] == "A"],
    },
    "desserts": {
        "emoji": "🍮", "label": "Desserts / Cake Slices",
        "items": [k for k, v in B2B_CAKE_MENU.items()],
    },
}

_ALL_ITEMS = {item for cat in _CATEGORIES.values() for item in cat["items"]}
_SLUG      = {name: name.replace(" ", "_") for name in _ALL_ITEMS}
_NAME      = {v: k for k, v in _SLUG.items()}

# ── Bun / roll config ─────────────────────────────────────────────────────────
_BUNS: dict[str, dict] = {
    "burger": {
        "emoji": "🍔", "label": "Burger Buns",
        "item": "Burger Bun",
        "sizes": [
            {"grams": 70, "label": "70g — Standard"},
            {"grams": 40, "label": "40g — Slider"},
        ],
    },
    "roll": {
        "emoji": "🥖", "label": "Soft Rolls",
        "item": "Hotdog Roll",
        "sizes": [
            {"grams": 55, "label": "55g — Small"},
            {"grams": 75, "label": "75g — Large"},
        ],
    },
}

def _bun_price(grams: int) -> float:
    return _BUN_PRICE_BY_GRAMS.get(grams, round(grams * 0.004, 2))


_SESAME_OPTIONS: list[tuple[str, str]] = [
    ("no",    "No Sesame"),
    ("mix",   "Mix Sesame"),
    ("black", "Black Sesame"),
    ("white", "White Sesame"),
]
_SESAME_CODE_LABEL: dict[str, str] = {code: label for code, label in _SESAME_OPTIONS}
_SESAME_LABEL_CODE: dict[str, str] = {label: code for code, label in _SESAME_OPTIONS}


# ── Display helpers ───────────────────────────────────────────────────────────

def _price_label(name: str, in_desserts: bool = False) -> str:
    if name in B2B_MENU:
        d = B2B_MENU[name]
        return f"${d['price']:.2f}/{d['unit']}" if d.get("unit") else f"${d['price']:.2f}"
    d = B2B_CAKE_MENU[name]
    if d["cake_category"] == "A":
        return f"${d['price_slice']:.2f}/slice" if in_desserts else f"${d['price_full']:.2f}"
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
            parts     = key.split("|")
            item_name = parts[0]
            grams     = int(parts[1])
            sesame_code  = parts[2] if len(parts) > 2 else None
            sesame_label = _SESAME_CODE_LABEL.get(sesame_code, "") if sesame_code else ""
            sesame_disp  = f" · {sesame_label}" if sesame_label else ""
            it = {"item": item_name, "qty": qty, "grams": grams, "notes": sesame_label or None}
            bread.append(it)
            lines.append(f"  {qty}× {item_name} {grams}g{sesame_disp} — ${_bun_price(grams) * qty:.2f}")
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
        rows.append([
            InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"),
            InlineKeyboardButton("🗑 Empty Cart",    callback_data="bm_empty_cart"),
        ])
    return InlineKeyboardMarkup(rows)


def _item_keyboard(cat_key: str, chat_id: int) -> InlineKeyboardMarkup:
    cart = _cart.get(chat_id, {})
    rows = []
    in_desserts = (cat_key == "desserts")
    for name in _CATEGORIES[cat_key]["items"]:
        qty    = cart.get(name, 0)
        slug   = _SLUG[name]
        suffix = f"  ✓ ×{qty}" if qty else ""
        label  = f"{name}{suffix}\n{_price_label(name, in_desserts=in_desserts)}"
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
        prefix = f"{bun['item']}|{size['grams']}"
        qty    = sum(q for k, q in cart.items() if k == prefix or k.startswith(f"{prefix}|"))
        price  = _bun_price(size["grams"])
        suffix = f" ✓×{qty}" if qty else ""
        label  = f"{size['label']}\n${price:.2f}{suffix}"
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
        prefix = f"{bun['item']}|{grams}"
        qty    = sum(q for k, q in cart.items() if k == prefix or k.startswith(f"{prefix}|"))
        label  = f"{grams}g\n${price:.2f}" + (f" ✓×{qty}" if qty else "")
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


def _qty_button_keyboard(name: str, slug: str, cat_key: str, current_qty: int) -> InlineKeyboardMarkup:
    rows = []
    if name in MINI_ITEMS:
        vals = [100, 200, 300, 400, 500]
        row = []
        for v in vals:
            mark = " ✓" if current_qty == v else ""
            row.append(InlineKeyboardButton(f"{v}{mark}", callback_data=f"bm_qtyval_{slug}_{cat_key}_{v}"))
            if len(row) == 3:
                rows.append(row); row = []
        if row:
            rows.append(row)
        other_mark = " ✓" if current_qty > 0 and current_qty not in vals else ""
        nav = [InlineKeyboardButton(f"Other{other_mark}", callback_data=f"bm_qtytext_{slug}_{cat_key}")]
        if current_qty > 0:
            nav.append(InlineKeyboardButton("✕ Remove", callback_data=f"bm_qtyval_{slug}_{cat_key}_0"))
        nav.append(InlineKeyboardButton("← Menu", callback_data=f"bm_cat_{cat_key}"))
        rows.append(nav)
    else:
        row = []
        for v in range(1, 10):
            mark = " ✓" if current_qty == v else ""
            row.append(InlineKeyboardButton(f"{v}{mark}", callback_data=f"bm_qtyval_{slug}_{cat_key}_{v}"))
            if len(row) == 3:
                rows.append(row); row = []
        if row:
            rows.append(row)
        plus_mark = " ✓" if current_qty >= 10 else ""
        nav = [InlineKeyboardButton(f"10+{plus_mark}", callback_data=f"bm_qtytext_{slug}_{cat_key}")]
        if current_qty > 0:
            nav.append(InlineKeyboardButton("✕ Remove", callback_data=f"bm_qtyval_{slug}_{cat_key}_0"))
        nav.append(InlineKeyboardButton("← Menu", callback_data=f"bm_cat_{cat_key}"))
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _bun_sesame_keyboard(bun_key: str, grams: int, chat_id: int) -> InlineKeyboardMarkup:
    bun  = _BUNS[bun_key]
    cart = _cart.get(chat_id, {})
    rows = []
    for code, label in _SESAME_OPTIONS:
        cart_key = f"{bun['item']}|{grams}|{code}"
        qty      = cart.get(cart_key, 0)
        suffix   = f"  ✓×{qty}" if qty else ""
        rows.append([InlineKeyboardButton(
            f"{label}{suffix}",
            callback_data=f"bm_bunsesame_{bun_key}_{grams}_{code}",
        )])
    nav = [InlineKeyboardButton("← Menu", callback_data=f"bm_bun_{bun_key}")]
    if cart:
        nav.append(InlineKeyboardButton("🟡 Confirm Order", callback_data="bm_confirm"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _bun_qty_keyboard(bun_key: str, grams: int, sesame_code: str | None, current_qty: int) -> InlineKeyboardMarkup:
    rows = []
    row  = []
    sfx  = f"_{sesame_code}" if sesame_code else ""
    for v in range(1, 10):
        mark = " ✓" if current_qty == v else ""
        row.append(InlineKeyboardButton(
            f"{v}{mark}",
            callback_data=f"bm_bunqtyval_{bun_key}_{grams}{sfx}_{v}",
        ))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    plus_mark = " ✓" if current_qty >= 10 else ""
    nav = [InlineKeyboardButton(f"10+{plus_mark}", callback_data=f"bm_bunqtytext_{bun_key}_{grams}{sfx}")]
    if current_qty > 0:
        nav.append(InlineKeyboardButton("✕ Remove", callback_data=f"bm_bunqtyval_{bun_key}_{grams}{sfx}_0"))
    back_cb = f"bm_bun_size_{bun_key}_{grams}" if sesame_code else f"bm_bun_{bun_key}"
    nav.append(InlineKeyboardButton("← Menu", callback_data=back_cb))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _date_picker_keyboard(back_cb: str = "bm_back") -> InlineKeyboardMarkup:
    today      = date.today()
    tomorrow   = today + timedelta(days=1)
    curr_month = today.replace(day=1)
    next_month = (curr_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    locked = _orders_locked()
    tmrw_label = f"{'🔒 ' if locked else ''}Tomorrow ({tomorrow.strftime('%a %d %b')})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tmrw_label, callback_data="bm_date_tmrw")],
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
        [InlineKeyboardButton("← Back", callback_data=back_cb)],
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


def _time_picker_keyboard(cb_prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    rows = []
    row  = []
    for code in _DELIVERY_TIME_CODES:
        row.append(InlineKeyboardButton(
            _format_time(code),
            callback_data=f"{cb_prefix}{code}",
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def _method_picker_keyboard(cb_prefix: str, back_cb: str, total: float = 0) -> InlineKeyboardMarkup:
    free = total >= FREE_DELIVERY_THRESHOLD
    delivery_label = "🚛 Delivery (free)" if free else f"🚛 Delivery (fee on orders under ${FREE_DELIVERY_THRESHOLD:.0f})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏪 Pickup (free)", callback_data=f"{cb_prefix}pickup")],
        [InlineKeyboardButton(delivery_label,      callback_data=f"{cb_prefix}delivery")],
        [InlineKeyboardButton("← Back",            callback_data=back_cb)],
    ])


def _confirm_screen_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Confirm screen — quick-confirm default, change options, or set up recurring."""
    rows = []
    method = _get_cart_method(chat_id)
    if method:
        time_str   = _get_cart_time(chat_id)
        date_label = _delivery_date_label(_get_cart_date(chat_id))
        emoji      = "🚛" if method == "delivery" else "🏪"
        method_lbl = "Delivery" if method == "delivery" else "Pickup"
        rows.append([InlineKeyboardButton(
            f"✅ {method_lbl} · {date_label} at {time_str}",
            callback_data="bm_cs_default",
        )])
    rows += [
        [InlineKeyboardButton("🚛🏪 Change Delivery/Pickup", callback_data="bm_cs_delivery")],
        [InlineKeyboardButton("📅 Change Date+Time",         callback_data="bm_cs_datetime")],
        [InlineKeyboardButton("🔄 Daily/Weekly Orders",      callback_data="bm_cs_recurring")],
        [InlineKeyboardButton("← Back to Menu",             callback_data="bm_back")],
    ]
    return InlineKeyboardMarkup(rows)


_REC_DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_REC_DAY_LABEL = {"mon": "Mon", "tue": "Tue", "wed": "Wed",
                  "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}


def _recurring_day_keyboard(selected: set) -> InlineKeyboardMarkup:
    """Multi-select weekday picker for recurring order setup."""
    rows = []
    row  = []
    for day in _REC_DAY_ORDER:
        mark  = "✅ " if day in selected else ""
        label = f"{mark}{_REC_DAY_LABEL[day]}"
        row.append(InlineKeyboardButton(label, callback_data=f"bm_rd_{day}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if selected:
        nav.append(InlineKeyboardButton("✅ Done", callback_data="bm_rd_done"))
    nav.append(InlineKeyboardButton("← Back", callback_data="bm_cs_show"))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _existing_orders_keyboard(
    sessions: list[dict],
    locked: bool,
    recurring_orders: list[dict] | None = None,
) -> InlineKeyboardMarkup:
    from b2b_bot.recurring import days_label
    import json
    rows = [[InlineKeyboardButton("➕ New Order", callback_data="bm_new_order")]]
    if not locked:
        for i, s in enumerate(sessions):
            rows.append([InlineKeyboardButton(
                f"✏️ Edit Order #{i + 1}",
                callback_data=f"bm_edit_session_{i}",
            )])
    # Group by (sorted days, time) so identical schedules share one button
    groups: dict[tuple, list] = {}
    for rec in (recurring_orders or []):
        days = tuple(sorted(json.loads(rec["days_of_week"])))
        key  = (days, rec["delivery_time"])
        groups.setdefault(key, []).append(rec)
    for (days, time), recs in groups.items():
        label = f"{days_label(list(days))} {time}"
        if len(recs) == 1:
            cb = f"bm_edit_rec_{recs[0]['id']}"
        else:
            cb = "bm_edit_recs_" + "_".join(str(r["id"]) for r in recs)
        rows.append([InlineKeyboardButton(f"🔄 Edit {label}", callback_data=cb)])
    return InlineKeyboardMarkup(rows)
