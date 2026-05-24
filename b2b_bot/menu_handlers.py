"""B2B menu — command/callback handlers and cart-to-confirmation bridge."""

import logging
from datetime import date, datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

import config
from b2b_bot.menu_keyboards import (
    _cart, _qty_pending, _menu_msg, _editing_session,
    _cart_time, _cart_date, _cart_method, _last_menu_prompt,
    _recurring_days, _recurring_pending,
    _SESAME_CODE_LABEL, _SESAME_LABEL_CODE,
    _DELIVERY_TIME_CODES,
    _get_cart_time, _get_cart_date, _get_cart_method, _delivery_date_label,
    _orders_locked, _MENU_PROMPT_COOLDOWN_SEC,
    _CATEGORIES, _BUNS, _NAME,
    _category_keyboard, _item_keyboard, _cart_block,
    _bun_size_keyboard, _bun_page_keyboard, _bun_gram_grid_keyboard,
    _bun_sesame_keyboard,
    _qty_button_keyboard, _bun_qty_keyboard,
    _date_picker_keyboard, _day_picker_keyboard, _time_picker_keyboard,
    _method_picker_keyboard, _existing_orders_keyboard,
    _confirm_screen_keyboard, _recurring_day_keyboard,
    _format_time,
)
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.menu import B2B_MENU, MINI_ITEMS
from b2b_bot.cake_menu import B2B_CAKE_MENU
from b2b_bot.pricing import order_total
from shared.database import (
    get_menu_message_id, set_menu_message_id,
    get_qty_pending, set_qty_pending,
    get_b2b_order_sessions, get_b2b_customer,
    upsert_b2b_customer,
    get_editing_session, set_editing_session,
    set_pending_order, set_order_state, set_last_confirmation_msg,
    get_b2b_recurring_orders, get_recurring_order, cancel_b2b_recurring_order,
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
    _editing_session.pop(chat_id, None); set_editing_session(chat_id, None)
    await _delete_old_menu(chat_id, context.bot)

    delivery_date    = _get_cart_date(chat_id)
    sessions         = get_b2b_order_sessions(chat_id, delivery_date)
    recurring_orders = get_b2b_recurring_orders(chat_id)

    if sessions or recurring_orders:
        locked = _orders_locked()
        lines = []
        if sessions:
            n = len(sessions)
            lines.append(f"You have {n} confirmed order{'s' if n > 1 else ''} for tomorrow:\n")
            for i, s in enumerate(sessions, 1):
                lines.append(f"Order #{i}:\n{_session_summary(s)}")
        if recurring_orders:
            from b2b_bot.recurring import days_label
            import json
            if lines:
                lines.append("")
            lines.append("Standing orders:")
            for rec in recurring_orders:
                days = json.loads(rec["days_of_week"])
                lines.append(f"  🔄 {days_label(days)} at {rec['delivery_time']}")
        if locked:
            lines.append("\n🔒 Orders are locked — bakery is producing.")
            lines.append("Anything urgent, chat with our staff here, no private chats please")
        else:
            lines.append("\nWhat would you like to do?")
        sent = await update.message.reply_text(
            "\n".join(lines),
            reply_markup=_existing_orders_keyboard(sessions, locked, recurring_orders),
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
        sesame_code = state.get("sesame_code")
        cart_key    = f"{state['item']}|{state['grams']}|{sesame_code}" if sesame_code else f"{state['item']}|{state['grams']}"
        if qty == 0:
            cart.pop(cart_key, None)
        else:
            cart[cart_key] = qty
        bun_key  = state["bun_key"]
        bun      = _BUNS[bun_key]
        _bun_txt = f"{bun['emoji']} {bun['label']}\n\n{_cart_block(chat_id)}"
        _bun_kb  = _bun_size_keyboard(bun_key, chat_id)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=state["message_id"],
                text=_bun_txt,
                reply_markup=_bun_kb,
            )
        except Exception:
            sent = await context.bot.send_message(chat_id, _bun_txt, reply_markup=_bun_kb)
            _menu_msg[chat_id] = sent.message_id
            set_menu_message_id(chat_id, sent.message_id)
    else:
        name = state["name"]
        if name in MINI_ITEMS and qty > 0 and qty < 100:
            await update.message.reply_text(
                f"Minimum order for {name} is 100 pieces. Please send a number ≥ 100 (or 0 to remove):"
            )
            _qty_pending[chat_id] = state
            set_qty_pending(chat_id, state)
            return
        if qty == 0:
            cart.pop(name, None)
        else:
            cart[name] = qty
        cat_key   = state["cat_key"]
        cat       = _CATEGORIES[cat_key]
        note_line = "".join(f"\n{e} {t}" for e, t in cat.get("note", []))
        _cat_txt  = f"{cat.get('emoji','')} {cat.get('label','')}{note_line}\n\n{_cart_block(chat_id)}"
        _cat_kb   = _item_keyboard(cat_key, chat_id)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=state["message_id"],
                text=_cat_txt,
                reply_markup=_cat_kb,
            )
        except Exception:
            sent = await context.bot.send_message(chat_id, _cat_txt, reply_markup=_cat_kb)
            _menu_msg[chat_id] = sent.message_id
            set_menu_message_id(chat_id, sent.message_id)

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
            _editing_session.pop(chat_id, None); set_editing_session(chat_id, None)
            _cart.pop(chat_id, None)
            _cart_time.pop(chat_id, None)
            _cart_date.pop(chat_id, None)
            _cart_method.pop(chat_id, None)
            _recurring_days.pop(chat_id, None)
            _recurring_pending.pop(chat_id, None)
            await query.edit_message_text(
                f"📋 Select a category:\n\n{_cart_block(chat_id)}",
                reply_markup=_category_keyboard(chat_id),
            )

        elif data.startswith("bm_edit_session_"):
            if _orders_locked():
                await query.answer("Orders are locked after 10pm. Contact us directly.", show_alert=True)
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
                if it.get("grams"):
                    sc  = _SESAME_LABEL_CODE.get(it.get("notes", ""))
                    key = f"{it['item']}|{it['grams']}|{sc}" if sc else f"{it['item']}|{it['grams']}"
                else:
                    key = it["item"]
                cart[key] = it["qty"]
            for it in session["cake"]:
                cart[it["item"]] = it["qty"]
            _editing_session[chat_id] = session["session_key"]
            set_editing_session(chat_id, session["session_key"])
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
                reply_markup=_date_picker_keyboard(back_cb="bm_cs_show"),
            )

        elif data == "bm_date_tmrw":
            if _orders_locked():
                await query.answer("Orders are locked after 10pm — bakery is producing.", show_alert=True)
                return
            tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
            tomorrow_d   = date.today() + timedelta(days=1)
            await query.edit_message_text(
                f"🕐 Select time — tomorrow ({tomorrow_d.strftime('%a %d %b')}):",
                reply_markup=_time_picker_keyboard(f"bm_dt_{tomorrow_str}_", "bm_time_select"),
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
                reply_markup=_time_picker_keyboard(f"bm_dt_{date_str}_", f"bm_date_m_{date_str[:6]}"),
            )

        elif data.startswith("bm_dt_"):
            rest      = data[6:]
            date_str  = rest[:8]
            time_code = rest[9:]
            _cart_date[chat_id] = datetime.strptime(date_str, "%Y%m%d").date().isoformat()
            _cart_time[chat_id] = _format_time(time_code)
            cart = _cart.get(chat_id, {})
            bread_tmp, cake_tmp = [], []
            for k, q in cart.items():
                if "|" in k:
                    parts = k.split("|")
                    nm, gs = parts[0], int(parts[1])
                    bread_tmp.append({"item": nm, "qty": q, "grams": gs, "notes": None})
                elif k in B2B_MENU:
                    bread_tmp.append({"item": k, "qty": q, "grams": None, "notes": None})
                else:
                    ck_def = B2B_CAKE_MENU[k]
                    ot = "piece" if ck_def["cake_category"] in ("B", "C") else "full"
                    cake_tmp.append({"item": k, "qty": q, "order_type": ot})
            total        = order_total(bread_tmp, cake_tmp)
            d            = datetime.strptime(date_str, "%Y%m%d").date()
            tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
            back_cb      = "bm_time_select" if date_str == tomorrow_str else f"bm_date_m_{date_str[:6]}"
            await query.edit_message_text(
                f"🚚 How will you receive your order?\n{d.strftime('%a %d %b')} at {_format_time(time_code)}",
                reply_markup=_method_picker_keyboard(
                    f"bm_method_{date_str}_{time_code}_", back_cb, total
                ),
            )

        elif data.startswith("bm_method_"):
            rest     = data[10:]
            date_str = rest[:8]
            rest2    = rest[9:]
            time_code, method = rest2.rsplit("_", 1)
            _cart_date[chat_id]   = datetime.strptime(date_str, "%Y%m%d").date().isoformat()
            _cart_time[chat_id]   = _format_time(time_code)
            _cart_method[chat_id] = method
            await _do_confirm(query, chat_id, context)

        elif data == "bm_menu_prompt":
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            _editing_session.pop(chat_id, None); set_editing_session(chat_id, None)
            await query.answer()
            await _delete_old_menu(chat_id, context.bot)
            delivery_date    = (date.today() + timedelta(days=1)).isoformat()
            sessions         = get_b2b_order_sessions(chat_id, delivery_date)
            recurring_orders = get_b2b_recurring_orders(chat_id)
            if sessions or recurring_orders:
                locked = _orders_locked()
                lines = []
                if sessions:
                    n = len(sessions)
                    lines.append(f"You have {n} confirmed order{'s' if n > 1 else ''} for tomorrow:\n")
                    for i, s in enumerate(sessions, 1):
                        lines.append(f"Order #{i}:\n{_session_summary(s)}")
                if recurring_orders:
                    from b2b_bot.recurring import days_label
                    import json
                    if lines:
                        lines.append("")
                    lines.append("Standing orders:")
                    for rec in recurring_orders:
                        days = json.loads(rec["days_of_week"])
                        lines.append(f"  🔄 {days_label(days)} at {rec['delivery_time']}")
                if locked:
                    lines.append("\n🔒 Orders are locked — bakery has been notified.")
                    lines.append("For changes, please contact us directly.")
                else:
                    lines.append("\nWhat would you like to do?")
                sent = await context.bot.send_message(
                    chat_id,
                    "\n".join(lines),
                    reply_markup=_existing_orders_keyboard(sessions, locked, recurring_orders),
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
            if bun_key == "burger":
                await query.edit_message_text(
                    f"{bun['label']} {grams}g — sesame topping?\n\n{_cart_block(chat_id)}",
                    reply_markup=_bun_sesame_keyboard(bun_key, grams, chat_id),
                )
            else:
                cart_key    = f"{bun['item']}|{grams}"
                current_qty = _cart.get(chat_id, {}).get(cart_key, 0)
                await query.edit_message_text(
                    f"{bun['label']} {grams}g — how many?\n\n{_cart_block(chat_id)}",
                    reply_markup=_bun_qty_keyboard(bun_key, grams, None, current_qty),
                )

        elif data.startswith("bm_bunqtyval_"):
            rest    = data[13:]
            bun_key = next((k for k in _BUNS if rest.startswith(f"{k}_")), None)
            if not bun_key:
                return
            after_bun = rest[len(bun_key) + 1:]
            if bun_key == "burger":
                parts = after_bun.split("_")   # ["70", "black", "9"]
                grams_str, sesame_code, qty_str = parts
            else:
                grams_str, qty_str = after_bun.rsplit("_", 1)
                sesame_code = None
            grams    = int(grams_str)
            qty      = int(qty_str)
            bun      = _BUNS[bun_key]
            cart     = _cart.setdefault(chat_id, {})
            cart_key = f"{bun['item']}|{grams}|{sesame_code}" if sesame_code else f"{bun['item']}|{grams}"
            if qty == 0:
                cart.pop(cart_key, None)
            else:
                cart[cart_key] = qty
            bun_txt = f"{bun['emoji']} {bun['label']}\n\n{_cart_block(chat_id)}"
            bun_kb  = _bun_size_keyboard(bun_key, chat_id)
            try:
                await query.edit_message_text(bun_txt, reply_markup=bun_kb)
            except Exception:
                sent = await context.bot.send_message(chat_id, bun_txt, reply_markup=bun_kb)
                _menu_msg[chat_id] = sent.message_id
                set_menu_message_id(chat_id, sent.message_id)

        elif data.startswith("bm_bunqtytext_"):
            rest    = data[14:]
            bun_key = next((k for k in _BUNS if rest.startswith(f"{k}_")), None)
            if not bun_key:
                return
            after_bun = rest[len(bun_key) + 1:]
            if bun_key == "burger":
                grams_str, sesame_code = after_bun.rsplit("_", 1)
                grams = int(grams_str)
            else:
                grams = int(after_bun)
                sesame_code = None
            bun   = _BUNS[bun_key]
            state = {
                "bun_key": bun_key,
                "item": bun["item"],
                "grams": grams,
                "sesame_code": sesame_code,
                "message_id": query.message.message_id,
            }
            _qty_pending[chat_id] = state
            set_qty_pending(chat_id, state)
            back_cb = f"bm_bunsesame_{bun_key}_{grams}_{sesame_code}" if sesame_code else f"bm_bun_size_{bun_key}_{grams}"
            await query.edit_message_text(
                f"How many {grams}g {bun['label']}?\nType a number (0 to remove):",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Menu", callback_data=back_cb),
                ]]),
            )

        elif data.startswith("bm_bunsesame_"):
            rest    = data[13:]
            bun_key = next((k for k in _BUNS if rest.startswith(f"{k}_")), None)
            if not bun_key:
                return
            after_bun              = rest[len(bun_key) + 1:]
            grams_str, sesame_code = after_bun.rsplit("_", 1)
            grams        = int(grams_str)
            bun          = _BUNS[bun_key]
            cart_key     = f"{bun['item']}|{grams}|{sesame_code}"
            current_qty  = _cart.get(chat_id, {}).get(cart_key, 0)
            sesame_label = _SESAME_CODE_LABEL[sesame_code]
            await query.edit_message_text(
                f"{bun['label']} {grams}g · {sesame_label} — how many?\n\n{_cart_block(chat_id)}",
                reply_markup=_bun_qty_keyboard(bun_key, grams, sesame_code, current_qty),
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
            bun     = _BUNS[bun_key]
            bun_txt = f"{bun['emoji']} {bun['label']}\n\n{_cart_block(chat_id)}"
            bun_kb  = _bun_size_keyboard(bun_key, chat_id)
            try:
                await query.edit_message_text(bun_txt, reply_markup=bun_kb)
            except Exception:
                sent = await context.bot.send_message(chat_id, bun_txt, reply_markup=bun_kb)
                _menu_msg[chat_id] = sent.message_id
                set_menu_message_id(chat_id, sent.message_id)

        elif data.startswith("bm_cat_"):
            _qty_pending.pop(chat_id, None)
            set_qty_pending(chat_id, None)
            cat_key   = data[7:]
            cat       = _CATEGORIES.get(cat_key, {})
            note_line = "".join(f"\n{e} {t}" for e, t in cat.get("note", []))
            cat_txt   = f"{cat.get('emoji','')} {cat.get('label','')}{note_line}\n\n{_cart_block(chat_id)}"
            cat_kb    = _item_keyboard(cat_key, chat_id)
            try:
                await query.edit_message_text(cat_txt, reply_markup=cat_kb)
            except Exception:
                sent = await context.bot.send_message(chat_id, cat_txt, reply_markup=cat_kb)
                _menu_msg[chat_id] = sent.message_id
                set_menu_message_id(chat_id, sent.message_id)

        elif data.startswith("bm_qty_"):
            rest    = data[7:]
            cat_key = next((k for k in _CATEGORIES if rest.endswith(f"_{k}")), None)
            if not cat_key:
                return
            slug = rest[:-(len(cat_key) + 1)]
            name = _NAME.get(slug)
            if not name:
                return
            current_qty = _cart.get(chat_id, {}).get(name, 0)
            cat         = _CATEGORIES[cat_key]
            note_line   = "".join(f"\n{e} {t}" for e, t in cat.get("note", []))
            await query.edit_message_text(
                f"{name} — how many?{note_line}\n\n{_cart_block(chat_id)}",
                reply_markup=_qty_button_keyboard(name, slug, cat_key, current_qty),
            )

        elif data.startswith("bm_qtyval_"):
            rest             = data[10:]
            rest_no_qty, qty_str = rest.rsplit("_", 1)
            cat_key = next((k for k in _CATEGORIES if rest_no_qty.endswith(f"_{k}")), None)
            if not cat_key:
                return
            slug = rest_no_qty[:-(len(cat_key) + 1)]
            name = _NAME.get(slug)
            if not name:
                return
            qty  = int(qty_str)
            cart = _cart.setdefault(chat_id, {})
            if qty == 0:
                cart.pop(name, None)
            else:
                cart[name] = qty
            cat       = _CATEGORIES[cat_key]
            note_line = "".join(f"\n{e} {t}" for e, t in cat.get("note", []))
            cat_txt   = f"{cat.get('emoji','')} {cat.get('label','')}{note_line}\n\n{_cart_block(chat_id)}"
            cat_kb    = _item_keyboard(cat_key, chat_id)
            try:
                await query.edit_message_text(cat_txt, reply_markup=cat_kb)
            except Exception:
                sent = await context.bot.send_message(chat_id, cat_txt, reply_markup=cat_kb)
                _menu_msg[chat_id] = sent.message_id
                set_menu_message_id(chat_id, sent.message_id)

        elif data.startswith("bm_qtytext_"):
            rest    = data[11:]
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
            if name in MINI_ITEMS:
                prompt = f"How many {name}?\n⚠️ Min. 100pc\n⚠️ 48h Advance Order\nType a number (0 to remove):"
            else:
                prompt = f"How many {name}?\nType a number (0 to remove):"
            await query.edit_message_text(
                prompt,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Menu", callback_data=f"bm_qty_{slug}_{cat_key}"),
                ]]),
            )

        elif data == "bm_confirm":
            cart = _cart.get(chat_id, {})
            if not cart:
                await query.answer("Cart is empty — add items first.", show_alert=True)
                return
            await query.edit_message_text(
                f"🛒 Ready to confirm?\n\n{_cart_block(chat_id)}\n\nHow would you like to receive this order?",
                reply_markup=_confirm_screen_keyboard(chat_id),
            )

        # ── Confirm screen ────────────────────────────────────────────────────
        elif data == "bm_cs_show":
            cart = _cart.get(chat_id, {})
            if not cart:
                await query.answer("Cart is empty.", show_alert=True)
                return
            await query.edit_message_text(
                f"🛒 Ready to confirm?\n\n{_cart_block(chat_id)}\n\nHow would you like to receive this order?",
                reply_markup=_confirm_screen_keyboard(chat_id),
            )

        elif data == "bm_cs_default":
            await _do_confirm(query, chat_id, context)

        elif data == "bm_cs_delivery":
            if not _cart.get(chat_id):
                await query.answer("Cart is empty.", show_alert=True)
                return
            from b2b_bot.pricing import order_total as _ot
            date_str  = datetime.strptime(_get_cart_date(chat_id), "%Y-%m-%d").strftime("%Y%m%d")
            curr_time = _get_cart_time(chat_id)
            time_code = next((c for c in _DELIVERY_TIME_CODES if _format_time(c) == curr_time), "0800")
            bread_tmp, cake_tmp = _parse_cart_items(chat_id)
            total = _ot(bread_tmp, cake_tmp)
            await query.edit_message_text(
                "🚚 Pickup or delivery?",
                reply_markup=_method_picker_keyboard(
                    f"bm_method_{date_str}_{time_code}_", "bm_cs_show", total
                ),
            )

        elif data == "bm_cs_datetime":
            time_str   = _get_cart_time(chat_id)
            date_label = _delivery_date_label(_get_cart_date(chat_id))
            await query.edit_message_text(
                f"📅 Select delivery date & time\n\nCurrent: {date_label} at {time_str}",
                reply_markup=_date_picker_keyboard(back_cb="bm_cs_show"),
            )

        elif data == "bm_cs_recurring":
            cart = _cart.get(chat_id, {})
            if not cart:
                await query.answer("Cart is empty.", show_alert=True)
                return
            bread_items, cake_items = _parse_cart_items(chat_id)
            if not bread_items:
                await query.answer("No bread items in cart. Recurring orders need at least one bread item.", show_alert=True)
                return
            if cake_items:
                await query.answer("Cakes are not supported in recurring orders — they'll be excluded.", show_alert=True)
            _recurring_pending[chat_id] = {"items": {"bread_items": bread_items, "cake_items": []}}
            selected = _recurring_days.get(chat_id, set())
            await query.edit_message_text(
                "🔄 Daily/Weekly order — pick which days:",
                reply_markup=_recurring_day_keyboard(selected),
            )

        # ── Recurring day selection ───────────────────────────────────────────
        elif data.startswith("bm_rd_") and data != "bm_rd_done":
            day = data[6:]
            if day not in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
                return
            sel = _recurring_days.setdefault(chat_id, set())
            if day in sel:
                sel.discard(day)
            else:
                sel.add(day)
            await query.edit_message_text(
                "🔄 Daily/Weekly order — pick which days:",
                reply_markup=_recurring_day_keyboard(sel),
            )

        elif data == "bm_rd_done":
            sel = _recurring_days.get(chat_id, set())
            if not sel:
                await query.answer("Please select at least one day.", show_alert=True)
                return
            from b2b_bot.recurring import days_label
            _recurring_pending.setdefault(chat_id, {})["days"] = sorted(sel)
            await query.edit_message_text(
                f"🔄 {days_label(sorted(sel))} — what time?",
                reply_markup=_time_picker_keyboard("bm_rt_", "bm_cs_recurring"),
            )

        elif data.startswith("bm_rt_"):
            time_code = data[6:]
            from b2b_bot.recurring import days_label
            pending = _recurring_pending.get(chat_id, {})
            pending["time"] = _format_time(time_code)
            _recurring_pending[chat_id] = pending
            days_lbl = days_label(pending.get("days", []))
            await query.edit_message_text(
                f"🔄 {days_lbl} at {_format_time(time_code)} — pickup or delivery?",
                reply_markup=_method_picker_keyboard("bm_rm_", "bm_cs_recurring"),
            )

        elif data.startswith("bm_rm_"):
            method = data[6:]
            if method not in ("pickup", "delivery"):
                return
            pending = _recurring_pending.get(chat_id, {})
            pending["method"] = method
            _recurring_pending[chat_id] = pending
            await _show_recurring_preconfirm(query, chat_id, context)

        # ── Edit / cancel a standing order ────────────────────────────────────
        elif data.startswith("bm_edit_rec_"):
            rec_id = int(data[12:])
            rec = get_recurring_order(rec_id)
            if not rec or rec["group_chat_id"] != chat_id:
                await query.answer("Standing order not found.", show_alert=True)
                return
            import json
            from b2b_bot.recurring import days_label
            days   = json.loads(rec["days_of_week"])
            items  = json.loads(rec["items_json"])
            method = "Delivery" if rec["delivery_method"] == "delivery" else "Pickup"
            lines  = [f"🔄 Standing order — {days_label(days)}", f"🕐 {method} at {rec['delivery_time']}", ""]
            for it in items.get("bread_items", []):
                line = f"  • {it['qty']}× {it['item']}"
                if it.get("grams"):
                    line += f" — {it['grams']}g"
                lines.append(line)
            lines += ["", "Cancel this standing order?"]
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✕ Cancel Standing Order", callback_data=f"bm_cancel_rec_{rec_id}")],
                    [InlineKeyboardButton("← Keep it",              callback_data="bm_back")],
                ]),
            )

        elif data.startswith("bm_edit_recs_"):
            ids  = [int(x) for x in data[13:].split("_")]
            recs = [get_recurring_order(rid) for rid in ids]
            recs = [r for r in recs if r and r["group_chat_id"] == chat_id]
            if not recs:
                await query.answer("Standing orders not found.", show_alert=True)
                return
            import json
            from b2b_bot.recurring import days_label
            first = recs[0]
            days  = json.loads(first["days_of_week"])
            lines = [f"🔄 Standing orders — {days_label(days)} at {first['delivery_time']}", ""]
            buttons = []
            for rec in recs:
                items  = json.loads(rec["items_json"])
                method = "Delivery" if rec["delivery_method"] == "delivery" else "Pickup"
                lines.append(f"Order {rec['id']}  ({method}):")
                for it in items.get("bread_items", []):
                    line = f"  • {it['qty']}× {it['item']}"
                    if it.get("grams"):
                        line += f" — {it['grams']}g"
                    lines.append(line)
                lines.append("")
                buttons.append([InlineKeyboardButton(
                    f"✕ Cancel — {method}",
                    callback_data=f"bm_cancel_rec_{rec['id']}",
                )])
            lines.append("Which would you like to cancel?")
            buttons.append([InlineKeyboardButton("← Keep them", callback_data="bm_back")])
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        elif data.startswith("bm_cancel_rec_"):
            rec_id = int(data[14:])
            rec = get_recurring_order(rec_id)
            if not rec or rec["group_chat_id"] != chat_id:
                await query.answer("Standing order not found.", show_alert=True)
                return
            cancel_b2b_recurring_order(rec_id)
            import json
            from b2b_bot.recurring import days_label
            days = json.loads(rec["days_of_week"])
            await query.edit_message_text(
                f"✕ Standing order ({days_label(days)}) cancelled.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 New Order", callback_data="bm_new_order"),
                ]]),
            )

    except Exception as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            logger.warning("menu callback error data=%s: %s", data, e)


def _parse_cart_items(chat_id: int):
    """Convert cart dict → (bread_items, cake_items) lists."""
    cart = _cart.get(chat_id, {})
    bread_items, cake_items = [], []
    for key, qty in cart.items():
        if "|" in key:
            parts       = key.split("|")
            item_name   = parts[0]
            grams       = int(parts[1])
            sesame_code = parts[2] if len(parts) > 2 else None
            notes       = _SESAME_CODE_LABEL.get(sesame_code) if sesame_code else None
            bread_items.append({"item": item_name, "qty": qty, "grams": grams, "notes": notes})
        elif key in B2B_MENU:
            bread_items.append({"item": key, "qty": qty, "grams": None, "notes": None})
        else:
            d  = B2B_CAKE_MENU[key]
            ot = "piece" if d["cake_category"] in ("B", "C") else None
            cake_items.append({"item": key, "qty": qty, "cake_category": d["cake_category"], "order_type": ot, "slices": None})
    return bread_items, cake_items


async def _show_recurring_preconfirm(query, chat_id: int, context) -> None:
    from b2b_bot.recurring import days_label
    pending = _recurring_pending.get(chat_id, {})
    days    = pending.get("days", [])
    time_s  = pending.get("time", "")
    method  = pending.get("method", "")
    items   = pending.get("items", {})
    bread_items = items.get("bread_items", [])

    method_lbl = "Delivery" if method == "delivery" else "Pickup"
    lines = [
        f"🔄 Every {days_label(days)}",
        f"🕐 {method_lbl} at {time_s}",
        "",
        "Items every order:",
    ]
    for it in bread_items:
        line = f"  • {it['qty']}× {it['item']}"
        if it.get("grams"):
            line += f" — {it['grams']}g"
        if it.get("notes"):
            line += f" ({it['notes']})"
        lines.append(line)
    lines += [
        "",
        "We'll remind you the day before each delivery. Confirm once and it repeats every week.",
        "",
        "Is this correct?",
    ]
    try:
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Confirm Standing Order", callback_data="b2b_rec_setup_confirm"),
                InlineKeyboardButton("✕ Cancel",                 callback_data="b2b_rec_setup_cancel"),
            ]]),
        )
    except Exception:
        sent = await context.bot.send_message(
            chat_id,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Confirm Standing Order", callback_data="b2b_rec_setup_confirm"),
                InlineKeyboardButton("✕ Cancel",                 callback_data="b2b_rec_setup_cancel"),
            ]]),
        )
        _menu_msg[chat_id] = sent.message_id
        set_menu_message_id(chat_id, sent.message_id)


async def _do_confirm(query, chat_id: int, context) -> None:
    from b2b_bot.order_handlers import _pending, _state, _last_confirmation
    from b2b_bot.order_parsing import (
        _resolve_bread_history, _resolve_cake_history,
        _split_mini_items, _mini_rejection_note,
        _build_confirmation, _confirm_keyboard,
    )

    if not _cart.get(chat_id):
        await query.answer("Cart is empty — add items first.", show_alert=True)
        return

    delivery_date = _get_cart_date(chat_id)
    bread_items, cake_items = _parse_cart_items(chat_id)

    bread_items            = _resolve_bread_history(chat_id, bread_items)
    cake_items, needs_spec = _resolve_cake_history(chat_id, cake_items)
    bread_items, rejected  = _split_mini_items(bread_items, delivery_date)

    customer = get_b2b_customer(chat_id)
    method   = _get_cart_method(chat_id)
    time_str = _get_cart_time(chat_id)
    location = customer["location"] if customer else None
    business = get_business_name(chat_id)

    editing_key = _editing_session.pop(chat_id, None) or get_editing_session(chat_id)
    set_editing_session(chat_id, None)
    _pending[chat_id] = {
        "bread_items": bread_items, "cake_items": cake_items,
        "delivery_method": method, "delivery_time": time_str,
        "location": location, "delivery_date": delivery_date,
        "ai_unmatched": [],
        "editing_session_key": editing_key,
    }
    set_pending_order(chat_id, _pending[chat_id])

    # Committed — clear cart state now
    _cart.pop(chat_id, None)
    _cart_time.pop(chat_id, None)
    _cart_date.pop(chat_id, None)
    _cart_method.pop(chat_id, None)

    if needs_spec:
        _state[chat_id] = {"mode": "awaiting_cake_spec", "needs_spec": needs_spec}
        set_order_state(chat_id, _state[chat_id])
        await query.edit_message_text(
            f"For the {', '.join(needs_spec)} — sliced or whole?\n"
            "(If sliced, tell me how many slices, e.g. 'sliced 10')",
            reply_markup=None,
        )
        return

    if not method:
        _state[chat_id] = {"mode": "awaiting_delivery"}
        set_order_state(chat_id, _state[chat_id])
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
    set_last_confirmation_msg(chat_id, query.message.message_id)
    try:
        await query.edit_message_text(msg, reply_markup=_confirm_keyboard())
    except Exception:
        sent = await context.bot.send_message(chat_id, msg, reply_markup=_confirm_keyboard())
        _last_confirmation[chat_id] = sent.message_id
        set_last_confirmation_msg(chat_id, sent.message_id)
