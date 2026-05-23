"""Interactive /menu command and welcome flow for B2B groups."""

import calendar
import logging
import time
from datetime import date, datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters as _filters

import config
from b2b_bot.menu import B2B_MENU, _BUN_PRICE_BY_GRAMS
from b2b_bot.cake_menu import B2B_CAKE_MENU
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.pricing import item_price, order_total, FREE_DELIVERY_THRESHOLD
from shared.database import (
    get_menu_message_id, set_menu_message_id,
    get_qty_pending, set_qty_pending,
    get_b2b_order_sessions,
    get_b2b_customer,
)

logger = logging.getLogger(__name__)

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
        "emoji": "🎂", "label": "Cakes",
        "items": [k for k, v in B2B_CAKE_MENU.items() if v["cake_category"] == "A"],
    },
    "desserts": {
        "emoji": "🍮", "label": "Desserts & Pieces",
        "items": [k for k, v in B2B_CAKE_MENU.items() if v["cake_category"] in ("B", "C")],
    },
}

_ALL_ITEMS = {item for cat in _CATEGORIES.values() for item in cat["items"]}
_SLUG      = {name: name.replace(" ", "_") for name in _ALL_ITEMS}
_NAME      = {v: k for k, v in _SLUG.items()}

# ── Bun / roll config ─────────────────────────────────────────────────────────
# Cart key for buns: "{item_name}|{grams}"  e.g. "burger bun|70"
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


def _get_cart_time(chat_id: int) -> str:
    """Delivery time for the current cart: explicit pick → customer history → 8:00am default."""
    t = _cart_time.get(chat_id)
    if t:
        return t
    customer = get_b2b_customer(chat_id)
    if customer and customer.get("delivery_time"):
        return customer["delivery_time"]
    return "8:00am"


def _get_cart_date(chat_id: int) -> str:
    """Delivery date (ISO) for the current cart. Defaults to tomorrow."""
    d = _cart_date.get(chat_id)
    if d:
        return d
    return (date.today() + timedelta(days=1)).isoformat()


def _get_cart_method(chat_id: int) -> str | None:
    """Delivery method for the current cart: explicit pick → customer history → None."""
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


# ── Filter: only activate qty handler when a qty prompt is pending ─────────────
class _QtyPendingFilter(_filters.MessageFilter):
    def filter(self, message):
        return bool(message.chat and message.chat.id in _qty_pending)

qty_pending_filter = _QtyPendingFilter()


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
            # Bun item stored as "burger bun|70"
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
    # Buns badge: total pieces across all bun cart keys
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
            f"🕐 {method_label} · {date_label} at {time_str}",
            callback_data="bm_time_select",
        )])
        rows.append([
            InlineKeyboardButton("✓ Confirm Order", callback_data="bm_confirm"),
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
        nav.append(InlineKeyboardButton("✓ Confirm Order", callback_data="bm_confirm"))
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
        nav.append(InlineKeyboardButton("✓ Confirm Order", callback_data="bm_confirm"))
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
        nav.append(InlineKeyboardButton("✓ Confirm Order", callback_data="bm_confirm"))
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
        nav.append(InlineKeyboardButton("✓ Confirm Order", callback_data="bm_confirm"))
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


async def maybe_send_menu_prompt(chat_id: int, bot) -> None:
    """Send a one-button menu nudge if 6+ hours have passed since the last one."""
    now = time.monotonic()
    if now - _last_menu_prompt.get(chat_id, 0) < _MENU_PROMPT_COOLDOWN_SEC:
        return
    _last_menu_prompt[chat_id] = now
    await bot.send_message(
        chat_id,
        "Ready to order?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Open Menu", callback_data="bm_menu_prompt"),
        ]]),
    )


# ── Handlers ──────────────────────────────────────────────────────────────────

def _orders_locked() -> bool:
    return datetime.now(timezone.utc).hour >= _LOCK_HOUR_UTC


def _session_summary(session: dict) -> str:
    lines = []
    for it in session["bread"]:
        line = f"  • {it['qty']}× {it['item']}"
        if it.get("grams"):
            line += f" — {it['grams']}g"
        lines.append(line)
    for it in session["cake"]:
        line = f"  • {it['qty']}× {it['item']}"
        ot = it.get("order_type")
        if ot == "sliced":
            line += f" — sliced {it.get('slices','?')}pc"
        elif ot == "full":
            line += " — whole"
        lines.append(line)
    return "\n".join(lines)


def _existing_orders_keyboard(sessions: list[dict], locked: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("➕ New Order", callback_data="bm_new_order")]]
    if not locked:
        for i, s in enumerate(sessions):
            rows.append([InlineKeyboardButton(
                f"✏️ Edit Order #{i + 1}",
                callback_data=f"bm_edit_session_{i}",
            )])
    return InlineKeyboardMarkup(rows)


async def _delete_old_menu(chat_id: int, bot) -> None:
    msg_id = _menu_msg.pop(chat_id, None) or get_menu_message_id(chat_id)
    if msg_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    set_menu_message_id(chat_id, None)


async def handle_menu_command(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return
    _qty_pending.pop(chat_id, None)
    _editing_session.pop(chat_id, None)
    await _delete_old_menu(chat_id, context.bot)

    delivery_date = _get_cart_date(chat_id)
    sessions = get_b2b_order_sessions(chat_id, delivery_date)

    if sessions:
        locked = _orders_locked()
        n = len(sessions)
        lines = [f"You already have {n} confirmed order{'s' if n > 1 else ''} for tomorrow:\n"]
        for i, s in enumerate(sessions, 1):
            lines.append(f"Order #{i}:\n{_session_summary(s)}")
        if locked:
            lines.append("\n🔒 Orders are locked — bakery has been notified.")
            lines.append("For changes, please contact us directly.")
        else:
            lines.append("\nWhat would you like to do?")
        sent = await update.message.reply_text(
            "\n".join(lines),
            reply_markup=_existing_orders_keyboard(sessions, locked),
        )
    else:
        sent = await update.message.reply_text(
            f"📋 Select a category:\n\n{_cart_block(chat_id)}",
            reply_markup=_category_keyboard(chat_id),
        )
    _menu_msg[chat_id] = sent.message_id
    set_menu_message_id(chat_id, sent.message_id)


async def handle_welcome(update: Update, context) -> None:
    """Fires when the bot is added to a B2B group."""
    member = update.my_chat_member
    if not member:
        return
    chat_id = member.chat.id
    if not is_b2b_group(chat_id):
        return
    if member.new_chat_member.status not in ("member", "administrator"):
        return
    _qty_pending.pop(chat_id, None)
    await _delete_old_menu(chat_id, context.bot)
    business = get_business_name(chat_id)
    name_str = f" {business}" if business else ""
    sent = await context.bot.send_message(
        chat_id,
        f"👋 Hello{name_str}! I'm your TWB order bot.\n\n"
        "Type your order anytime, or browse the menu below:",
        reply_markup=_category_keyboard(chat_id),
    )
    _menu_msg[chat_id] = sent.message_id
    set_menu_message_id(chat_id, sent.message_id)


async def handle_qty_input(update: Update, context) -> None:
    """Intercepts typed input when a qty or grams prompt is pending."""
    chat_id = update.effective_chat.id
    state   = _qty_pending.get(chat_id) or get_qty_pending(chat_id)
    if not state:
        return
    text = update.message.text.strip()

    # ── Quantity input ─────────────────────────────────────────────────────────
    try:
        qty = int(text)
        if qty < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a whole number, e.g. 40  (or 0 to remove)")
        return

    _qty_pending.pop(chat_id, None)
    set_qty_pending(chat_id, None)
    cart = _cart.setdefault(chat_id, {})

    if "bun_key" in state:
        # Bun item
        cart_key = f"{state['item']}|{state['grams']}"
        if qty == 0:
            cart.pop(cart_key, None)
        else:
            cart[cart_key] = qty
        bun_key = state["bun_key"]
        bun     = _BUNS[bun_key]
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=state["message_id"],
                text=f"{bun['emoji']} {bun['label']}\n\n{_cart_block(chat_id)}",
                reply_markup=_bun_size_keyboard(bun_key, chat_id),
            )
        except Exception:
            pass
    else:
        # Regular category item
        if qty == 0:
            cart.pop(state["name"], None)
        else:
            cart[state["name"]] = qty
        cat_key   = state["cat_key"]
        cat       = _CATEGORIES[cat_key]
        note_line = f"\n⚠️ {cat['note']}" if cat.get("note") else ""
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=state["message_id"],
                text=f"{cat.get('emoji','')} {cat.get('label','')}{note_line}\n\n{_cart_block(chat_id)}",
                reply_markup=_item_keyboard(cat_key, chat_id),
            )
        except Exception:
            pass

    try:
        await update.message.delete()
    except Exception:
        pass


async def handle_menu_callback(update: Update, context) -> None:
    query   = update.callback_query
    chat_id = update.effective_chat.id
    data    = query.data

    await query.answer()

    if data == "bm_noop":
        return

    try:
        if data == "bm_back":
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            await query.edit_message_text(
                f"📋 Select a category:\n\n{_cart_block(chat_id)}",
                reply_markup=_category_keyboard(chat_id),
            )

        elif data == "bm_new_order":
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            _editing_session.pop(chat_id, None)
            _cart.pop(chat_id, None)
            _cart_time.pop(chat_id, None)
            _cart_date.pop(chat_id, None)
            _cart_method.pop(chat_id, None)
            await query.edit_message_text(
                f"📋 Select a category:\n\n{_cart_block(chat_id)}",
                reply_markup=_category_keyboard(chat_id),
            )

        elif data.startswith("bm_edit_session_"):
            if _orders_locked():
                await query.answer("Orders are locked after 9pm. Contact us directly.", show_alert=True)
                return
            idx = int(data[16:])
            delivery_date = (date.today() + timedelta(days=1)).isoformat()
            sessions = get_b2b_order_sessions(chat_id, delivery_date)
            if idx >= len(sessions):
                await query.answer("Order not found.", show_alert=True)
                return
            session = sessions[idx]
            # Load session items into cart
            cart = _cart.setdefault(chat_id, {})
            cart.clear()
            for it in session["bread"]:
                key = f"{it['item']}|{it['grams']}" if it.get("grams") else it["item"]
                cart[key] = it["qty"]
            for it in session["cake"]:
                cart[it["item"]] = it["qty"]
            # Remember which session we're replacing
            _editing_session[chat_id] = session["session_key"]
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            await query.edit_message_text(
                f"✏️ Editing Order #{idx + 1} — make your changes:\n\n{_cart_block(chat_id)}",
                reply_markup=_category_keyboard(chat_id),
            )

        elif data == "bm_empty_cart":
            _cart.pop(chat_id, None)
            _cart_time.pop(chat_id, None)
            _cart_date.pop(chat_id, None)
            _cart_method.pop(chat_id, None)
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            await query.edit_message_text(
                f"🗑 Cart cleared.\n\n📋 Select a category:\n\n{_cart_block(chat_id)}",
                reply_markup=_category_keyboard(chat_id),
            )

        elif data == "bm_time_select":
            time_str   = _get_cart_time(chat_id)
            date_label = _delivery_date_label(_get_cart_date(chat_id))
            await query.edit_message_text(
                f"🕐 Select delivery date & time\n\nCurrent: {date_label} at {time_str}",
                reply_markup=_date_picker_keyboard(),
            )

        elif data == "bm_date_tmrw":
            tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
            tomorrow_d   = date.today() + timedelta(days=1)
            await query.edit_message_text(
                f"🕐 Select time — tomorrow ({tomorrow_d.strftime('%a %d %b')}):",
                reply_markup=_time_picker_keyboard(tomorrow_str),
            )

        elif data.startswith("bm_date_m_"):
            yyyymm     = data[10:]
            year, month = int(yyyymm[:4]), int(yyyymm[4:])
            month_name = calendar.month_name[month]
            await query.edit_message_text(
                f"📅 Select day — {month_name} {year}:",
                reply_markup=_day_picker_keyboard(yyyymm),
            )

        elif data.startswith("bm_date_d_"):
            date_str = data[10:]
            d = datetime.strptime(date_str, "%Y%m%d").date()
            await query.edit_message_text(
                f"🕐 Select time — {d.strftime('%A %d %B')}:",
                reply_markup=_time_picker_keyboard(date_str),
            )

        elif data.startswith("bm_dt_"):
            # bm_dt_{YYYYMMDD}_{HHMM}
            rest      = data[6:]
            date_str  = rest[:8]
            time_code = rest[9:]
            cart = _cart.get(chat_id, {})
            bread_tmp, cake_tmp = [], []
            for k, q in cart.items():
                if "|" in k:
                    nm, gs = k.split("|", 1)
                    bread_tmp.append({"item": nm, "qty": q, "grams": int(gs), "notes": None})
                elif k in B2B_MENU:
                    bread_tmp.append({"item": k, "qty": q, "grams": None, "notes": None})
                else:
                    ck_def = B2B_CAKE_MENU[k]
                    ot = "piece" if ck_def["cake_category"] in ("B", "C") else "full"
                    cake_tmp.append({"item": k, "qty": q, "order_type": ot})
            total = order_total(bread_tmp, cake_tmp)
            d = datetime.strptime(date_str, "%Y%m%d").date()
            await query.edit_message_text(
                f"🚚 How will you receive your order?\n{d.strftime('%a %d %b')} at {_format_time(time_code)}",
                reply_markup=_method_picker_keyboard(date_str, time_code, total),
            )

        elif data.startswith("bm_method_"):
            # bm_method_{YYYYMMDD}_{HHMM}_{pickup|delivery}
            rest     = data[10:]
            date_str = rest[:8]
            rest2    = rest[9:]
            time_code, method = rest2.rsplit("_", 1)
            _cart_date[chat_id]   = datetime.strptime(date_str, "%Y%m%d").date().isoformat()
            _cart_time[chat_id]   = _format_time(time_code)
            _cart_method[chat_id] = method
            await query.edit_message_text(
                f"📋 Select a category:\n\n{_cart_block(chat_id)}",
                reply_markup=_category_keyboard(chat_id),
            )

        elif data == "bm_menu_prompt":
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            _editing_session.pop(chat_id, None)
            await _delete_old_menu(chat_id, context.bot)
            delivery_date = (date.today() + timedelta(days=1)).isoformat()
            sessions = get_b2b_order_sessions(chat_id, delivery_date)
            if sessions:
                locked = _orders_locked()
                n = len(sessions)
                lines = [f"You already have {n} confirmed order{'s' if n > 1 else ''} for tomorrow:\n"]
                for i, s in enumerate(sessions, 1):
                    lines.append(f"Order #{i}:\n{_session_summary(s)}")
                if locked:
                    lines.append("\n🔒 Orders are locked — bakery has been notified.")
                    lines.append("For changes, please contact us directly.")
                else:
                    lines.append("\nWhat would you like to do?")
                await query.edit_message_text(
                    "\n".join(lines),
                    reply_markup=_existing_orders_keyboard(sessions, locked),
                )
            else:
                await query.edit_message_text(
                    f"📋 Select a category:\n\n{_cart_block(chat_id)}",
                    reply_markup=_category_keyboard(chat_id),
                )
            _menu_msg[chat_id] = query.message.message_id
            set_menu_message_id(chat_id, query.message.message_id)

        elif data == "bm_buns":
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            await query.edit_message_text(
                f"🍔 Buns & Rolls\n\n{_cart_block(chat_id)}",
                reply_markup=_bun_page_keyboard(chat_id),
            )

        elif data.startswith("bm_bun_size_"):
            # e.g. bm_bun_size_burger_70
            rest    = data[12:]
            bun_key = next((k for k in _BUNS if rest.startswith(f"{k}_")), None)
            if not bun_key:
                return
            grams = int(rest[len(bun_key) + 1:])
            bun   = _BUNS[bun_key]
            state = {
                "bun_key": bun_key,
                "item": bun["item"],
                "grams": grams,
                "message_id": query.message.message_id,
            }
            _qty_pending[chat_id] = state
            set_qty_pending(chat_id, state)
            await query.edit_message_text(
                f"How many {grams}g {bun['label']}?\nType a number (0 to remove):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Cancel", callback_data=f"bm_bun_{bun_key}"),
                ]]),
            )

        elif data.startswith("bm_bun_other_"):
            bun_key = data[13:]
            if bun_key not in _BUNS:
                return
            bun = _BUNS[bun_key]
            await query.edit_message_text(
                f"{bun['emoji']} {bun['label']} — select grams:\n\n{_cart_block(chat_id)}",
                reply_markup=_bun_gram_grid_keyboard(bun_key, chat_id),
            )

        elif data.startswith("bm_bun_"):
            # e.g. bm_bun_burger  or  bm_bun_roll
            bun_key = data[7:]
            if bun_key not in _BUNS:
                return
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            bun = _BUNS[bun_key]
            await query.edit_message_text(
                f"{bun['emoji']} {bun['label']}\n\n{_cart_block(chat_id)}",
                reply_markup=_bun_size_keyboard(bun_key, chat_id),
            )

        elif data.startswith("bm_cat_"):
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            cat_key = data[7:]
            cat = _CATEGORIES.get(cat_key, {})
            note_line = f"\n⚠️ {cat['note']}" if cat.get("note") else ""
            await query.edit_message_text(
                f"{cat.get('emoji','')} {cat.get('label','')}{note_line}\n\n{_cart_block(chat_id)}",
                reply_markup=_item_keyboard(cat_key, chat_id),
            )

        elif data.startswith("bm_qty_"):
            rest    = data[7:]
            cat_key = next((k for k in _CATEGORIES if rest.endswith(f"_{k}")), None)
            if not cat_key:
                return
            slug = rest[:-(len(cat_key) + 1)]
            name = _NAME.get(slug)
            if not name:
                return
            state = {
                "name": name,
                "cat_key": cat_key,
                "message_id": query.message.message_id,
            }
            _qty_pending[chat_id] = state
            set_qty_pending(chat_id, state)
            await query.edit_message_text(
                f"How many {name}?\nType a number (0 to remove):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Cancel", callback_data=f"bm_cat_{cat_key}"),
                ]]),
            )

        elif data == "bm_confirm":
            await _do_confirm(query, chat_id, context)

    except Exception as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            logger.warning("menu callback error data=%s: %s", data, e)


async def _do_confirm(query, chat_id: int, context) -> None:
    from b2b_bot.orders import (
        _pending, _state, _last_confirmation,
        _resolve_bread_history, _resolve_cake_history,
        _split_mini_items, _mini_rejection_note,
        _build_confirmation, _confirm_keyboard,
    )
    from shared.database import get_b2b_customer, upsert_b2b_customer

    cart = _cart.pop(chat_id, {})
    if not cart:
        await query.answer("Cart is empty — add items first.", show_alert=True)
        return

    delivery_date = _get_cart_date(chat_id)
    bread_items, cake_items = [], []

    for key, qty in cart.items():
        if "|" in key:
            item_name, grams_str = key.split("|", 1)
            bread_items.append({"item": item_name, "qty": qty, "grams": int(grams_str), "notes": None})
        elif key in B2B_MENU:
            bread_items.append({"item": key, "qty": qty, "grams": None, "notes": None})
        else:
            d  = B2B_CAKE_MENU[key]
            ot = "piece" if d["cake_category"] in ("B", "C") else None
            cake_items.append({"item": key, "qty": qty, "cake_category": d["cake_category"], "order_type": ot, "slices": None})

    bread_items            = _resolve_bread_history(chat_id, bread_items)
    cake_items, needs_spec = _resolve_cake_history(chat_id, cake_items)
    bread_items, rejected  = _split_mini_items(bread_items, delivery_date)

    customer = get_b2b_customer(chat_id)
    method   = _get_cart_method(chat_id)
    time_str = _get_cart_time(chat_id)
    location = customer["location"] if customer else None
    business = get_business_name(chat_id)
    _cart_time.pop(chat_id, None)
    _cart_date.pop(chat_id, None)
    _cart_method.pop(chat_id, None)

    _pending[chat_id] = {
        "bread_items": bread_items, "cake_items": cake_items,
        "delivery_method": method, "delivery_time": time_str,
        "location": location, "delivery_date": delivery_date,
        "ai_unmatched": [],
        "editing_session_key": _editing_session.pop(chat_id, None),
    }

    if needs_spec:
        _state[chat_id] = {"mode": "awaiting_cake_spec", "needs_spec": needs_spec}
        await query.edit_message_text(
            f"For the {', '.join(needs_spec)} — sliced or whole?\n"
            "(If sliced, tell me how many slices, e.g. 'sliced 10')",
            reply_markup=None,
        )
        return

    if not method:
        _state[chat_id] = {"mode": "awaiting_delivery"}
        upsert_b2b_customer(chat_id, business)
        await query.edit_message_text(
            "Almost there! Pickup or delivery, and what time?\n"
            "Example: Delivery at 8am  |  Pickup at 7am",
            reply_markup=None,
        )
        return

    msg = _build_confirmation(bread_items, cake_items, method, time_str, location, delivery_date)
    if rejected:
        msg += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(rejected)

    _last_confirmation[chat_id] = query.message.message_id
    await query.edit_message_text(msg, reply_markup=_confirm_keyboard())
