"""Interactive /menu command and welcome flow for B2B groups."""

import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters as _filters

import config
from b2b_bot.menu import B2B_MENU
from b2b_bot.cake_menu import B2B_CAKE_MENU
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.pricing import item_price, order_total

logger = logging.getLogger(__name__)

# ── In-memory state ───────────────────────────────────────────────────────────
_cart: dict[int, dict[str, int]] = {}  # {chat_id: {item_name: qty}}
_qty_pending: dict[int, dict] = {}     # {chat_id: {name, cat_key, message_id}}
_menu_msg: dict[int, int] = {}         # {chat_id: message_id of active menu}

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
    for name, qty in cart.items():
        if name in B2B_MENU:
            it = {"item": name, "qty": qty, "grams": B2B_MENU[name].get("standard_grams"), "notes": None}
            bread.append(it)
        else:
            d = B2B_CAKE_MENU[name]
            ot = "piece" if d["cake_category"] in ("B", "C") else "full"
            it = {"item": name, "qty": qty, "order_type": ot}
            cake.append(it)
        lines.append(f"  {qty}× {name} — ${item_price(it):.2f}")
    total = order_total(bread, cake)
    return "🛒 Cart:\n" + "\n".join(lines) + f"\n  Total: ${total:.2f}"


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
    rows.append([InlineKeyboardButton(
        "🍔 Buns & Rolls — tap for info",
        callback_data="bm_buns",
    )])
    if cart:
        rows.append([InlineKeyboardButton("✓ Confirm Order", callback_data="bm_confirm")])
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


# ── Handlers ──────────────────────────────────────────────────────────────────

async def _delete_old_menu(chat_id: int, bot) -> None:
    msg_id = _menu_msg.pop(chat_id, None)
    if msg_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass


async def handle_menu_command(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return
    _cart.pop(chat_id, None)
    _qty_pending.pop(chat_id, None)
    await _delete_old_menu(chat_id, context.bot)
    sent = await update.message.reply_text(
        f"📋 Select a category:\n\n{_cart_block(chat_id)}",
        reply_markup=_category_keyboard(chat_id),
    )
    _menu_msg[chat_id] = sent.message_id


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
    _cart.pop(chat_id, None)
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


async def handle_qty_input(update: Update, context) -> None:
    """Intercepts a typed number when a qty prompt is pending for this chat."""
    chat_id = update.effective_chat.id
    state = _qty_pending.get(chat_id)
    if not state:
        return
    text = update.message.text.strip()
    try:
        qty = int(text)
        if qty < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a whole number, e.g. 40  (or 0 to remove)")
        return

    _qty_pending.pop(chat_id, None)
    cart = _cart.setdefault(chat_id, {})
    if qty == 0:
        cart.pop(state["name"], None)
    else:
        cart[state["name"]] = qty

    cat_key = state["cat_key"]
    cat = _CATEGORIES[cat_key]
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
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data    = query.data

    if data == "bm_noop":
        return

    if data == "bm_back":
        _qty_pending.pop(chat_id, None)
        await query.edit_message_text(
            f"📋 Select a category:\n\n{_cart_block(chat_id)}",
            reply_markup=_category_keyboard(chat_id),
        )
        return

    if data == "bm_buns":
        await query.answer(
            "Type bun orders with grams directly:\n\n"
            "e.g.  10 burger buns 70g\n"
            "      20 hotdog rolls 55g\n"
            "      15 slider buns 40g",
            show_alert=True,
        )
        return

    if data.startswith("bm_cat_"):
        _qty_pending.pop(chat_id, None)
        cat_key = data[7:]
        cat = _CATEGORIES.get(cat_key, {})
        note_line = f"\n⚠️ {cat['note']}" if cat.get("note") else ""
        await query.edit_message_text(
            f"{cat.get('emoji','')} {cat.get('label','')}{note_line}\n\n{_cart_block(chat_id)}",
            reply_markup=_item_keyboard(cat_key, chat_id),
        )
        return

    if data.startswith("bm_qty_"):
        rest    = data[7:]
        cat_key = next((k for k in _CATEGORIES if rest.endswith(f"_{k}")), None)
        if not cat_key:
            return
        slug = rest[:-(len(cat_key) + 1)]
        name = _NAME.get(slug)
        if not name:
            return
        _qty_pending[chat_id] = {
            "name": name,
            "cat_key": cat_key,
            "message_id": query.message.message_id,
        }
        cancel_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("← Cancel", callback_data=f"bm_cat_{cat_key}"),
        ]])
        await query.edit_message_text(
            f"How many {name}?\nType a number (0 to remove):",
            reply_markup=cancel_kb,
        )
        return

    if data == "bm_confirm":
        await _do_confirm(query, chat_id, context)


async def _do_confirm(query, chat_id: int, context) -> None:
    from b2b_bot.orders import (
        _pending, _state, _last_confirmation,
        _resolve_bread_history, _resolve_cake_history,
        _split_mini_items, _mini_rejection_note,
        _build_confirmation, _confirm_keyboard,
    )
    from b2b_bot.customers import get_b2b_customer, upsert_b2b_customer

    cart = _cart.pop(chat_id, {})
    if not cart:
        await query.answer("Cart is empty — add items first.", show_alert=True)
        return

    delivery_date = (date.today() + timedelta(days=1)).isoformat()
    bread_items, cake_items = [], []

    for name, qty in cart.items():
        if name in B2B_MENU:
            bread_items.append({"item": name, "qty": qty, "grams": None, "notes": None})
        else:
            d  = B2B_CAKE_MENU[name]
            ot = "piece" if d["cake_category"] in ("B", "C") else None
            cake_items.append({"item": name, "qty": qty, "cake_category": d["cake_category"], "order_type": ot, "slices": None})

    bread_items            = _resolve_bread_history(chat_id, bread_items)
    cake_items, needs_spec = _resolve_cake_history(chat_id, cake_items)
    bread_items, rejected  = _split_mini_items(bread_items, delivery_date)

    customer     = get_b2b_customer(chat_id)
    method       = customer["delivery_method"] if customer else None
    time_str     = customer["delivery_time"]   if customer else None
    location     = customer["location"]        if customer else None
    business     = get_business_name(chat_id)

    _pending[chat_id] = {
        "bread_items": bread_items, "cake_items": cake_items,
        "delivery_method": method, "delivery_time": time_str,
        "location": location, "delivery_date": delivery_date,
        "ai_unmatched": [],
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
