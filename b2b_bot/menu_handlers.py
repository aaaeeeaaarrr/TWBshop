"""B2B menu — command/callback handlers and cart-to-confirmation bridge."""

import logging
from datetime import date, datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

import config
from b2b_bot.menu_keyboards import (
    _cart, _qty_pending, _menu_msg, _editing_session,
    _cart_time, _cart_date, _cart_method, _last_menu_prompt,
    _get_cart_time, _get_cart_date, _get_cart_method, _delivery_date_label,
    _orders_locked, _MENU_PROMPT_COOLDOWN_SEC,
    _CATEGORIES, _BUNS, _NAME,
    _category_keyboard, _item_keyboard, _cart_block,
    _bun_size_keyboard, _bun_page_keyboard, _bun_gram_grid_keyboard,
    _date_picker_keyboard, _day_picker_keyboard, _time_picker_keyboard,
    _method_picker_keyboard, _existing_orders_keyboard,
    _format_time,
)
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.menu import B2B_MENU
from b2b_bot.cake_menu import B2B_CAKE_MENU
from b2b_bot.pricing import order_total
from shared.database import (
    get_menu_message_id, set_menu_message_id,
    get_qty_pending, set_qty_pending,
    get_b2b_order_sessions, get_b2b_customer,
    upsert_b2b_customer,
)

logger = logging.getLogger(__name__)


async def maybe_send_menu_prompt(chat_id: int, bot) -> None:
    """Send a one-button menu nudge if 6+ hours have passed since the last one."""
    import time
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
            cart = _cart.setdefault(chat_id, {})
            cart.clear()
            for it in session["bread"]:
                key = f"{it['item']}|{it['grams']}" if it.get("grams") else it["item"]
                cart[key] = it["qty"]
            for it in session["cake"]:
                cart[it["item"]] = it["qty"]
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
            yyyymm      = data[10:]
            import calendar as _cal
            year, month = int(yyyymm[:4]), int(yyyymm[4:])
            month_name  = _cal.month_name[month]
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
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
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
                sent = await context.bot.send_message(
                    chat_id,
                    "\n".join(lines),
                    reply_markup=_existing_orders_keyboard(sessions, locked),
                )
            else:
                sent = await context.bot.send_message(
                    chat_id,
                    f"📋 Select a category:\n\n{_cart_block(chat_id)}",
                    reply_markup=_category_keyboard(chat_id),
                )
            _menu_msg[chat_id] = sent.message_id
            set_menu_message_id(chat_id, sent.message_id)

        elif data == "bm_buns":
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            await query.edit_message_text(
                f"🍔 Buns & Rolls\n\n{_cart_block(chat_id)}",
                reply_markup=_bun_page_keyboard(chat_id),
            )

        elif data.startswith("bm_bun_size_"):
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
    from b2b_bot.order_handlers import _pending, _state, _last_confirmation
    from b2b_bot.order_parsing import (
        _resolve_bread_history, _resolve_cake_history,
        _split_mini_items, _mini_rejection_note,
        _build_confirmation, _confirm_keyboard,
    )

    cart = dict(_cart.get(chat_id, {}))  # copy — don't pop until we're committed
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

    _pending[chat_id] = {
        "bread_items": bread_items, "cake_items": cake_items,
        "delivery_method": method, "delivery_time": time_str,
        "location": location, "delivery_date": delivery_date,
        "ai_unmatched": [],
        "editing_session_key": _editing_session.pop(chat_id, None),
    }

    # Committed — clear cart state now
    _cart.pop(chat_id, None)
    _cart_time.pop(chat_id, None)
    _cart_date.pop(chat_id, None)
    _cart_method.pop(chat_id, None)

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
    try:
        await query.edit_message_text(msg, reply_markup=_confirm_keyboard())
    except Exception:
        # Edit failed (message too old, deleted, etc.) — send as new message
        sent = await context.bot.send_message(chat_id, msg, reply_markup=_confirm_keyboard())
        _last_confirmation[chat_id] = sent.message_id
