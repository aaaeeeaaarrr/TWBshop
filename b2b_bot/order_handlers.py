"""B2B order handlers — in-memory state, notifications, confirm helper, and Telegram handlers."""

import uuid
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

import config
from b2b_bot.order_parsing import (
    _parse_order_ai, _ai_items_to_orders,
    _resolve_bread_history, _resolve_cake_history,
    _split_mini_items, _mini_rejection_note,
    _build_confirmation, _build_confirmed_text, _confirm_keyboard,
    _send_confirmation, _parse_delivery_text,
    _CONFIRM_WORDS, _CANCEL_WORDS,
    _date_label, _bread_line, _cake_line,
)
from b2b_bot.customers import get_business_name, is_b2b_group

def _delivery_cost_for(chat_id: int, method: str | None) -> float | None:
    if method != "delivery":
        return None
    cust = get_b2b_customer(chat_id)
    return float(cust["delivery_cost"]) if cust and cust.get("delivery_cost") else None
from b2b_bot.menu import INSTANT_BREAD_ITEMS, MINI_ITEMS
from b2b_bot.cake_menu import B2B_CAKE_MENU
from shared.database import (
    get_b2b_customer, upsert_b2b_customer,
    save_b2b_order, save_b2b_cake_order,
    delete_b2b_orders_for_date, delete_b2b_cake_orders_for_date,
    delete_b2b_order_session, get_b2b_order_sessions,
    get_pending_order, set_pending_order,
    get_order_state, set_order_state,
    get_last_confirmation_msg, set_last_confirmation_msg,
    set_menu_message_id,
    save_b2b_recurring_order, get_recurring_order,
    get_or_create_recurring_confirmation,
    confirm_recurring_instance, skip_recurring_instance,
)
from shared.ai_client import extract_b2b_order_from_image

logger = logging.getLogger(__name__)

# In-memory pending orders: {group_chat_id: {bread_items, cake_items, delivery_*, ...}}
_pending: dict[int, dict] = {}
# Conversation state: {group_chat_id: {"mode": str, ...}}
_state:   dict[int, dict] = {}
# Last confirmation message ID per chat (to remove buttons when superseded)
_last_confirmation: dict[int, int] = {}


# ─── Instant notifications ────────────────────────────────────────────────────

async def _notify_cake_order(bot, business_name: str, cake_items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str) -> None:
    lines = [f"DESSERT ORDER — {business_name}", ""]
    for it in cake_items:
        lines.append(_cake_line(it))
    from b2b_bot.order_parsing import _delivery_line
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        lines += ["", dl]
    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines))


async def _notify_urgent_bread_order(bot, business_name: str, bread_items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str) -> None:
    urgent = [it for it in bread_items if it["item"] in INSTANT_BREAD_ITEMS]
    if not urgent:
        return
    lines = [f"Add to order — {business_name}", ""]
    for it in urgent:
        lines.append(_bread_line(it))
    from b2b_bot.order_parsing import _delivery_line
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        lines += ["", dl]
    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines))


async def _notify_mini_order(bot, business_name: str, bread_items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str) -> None:
    minis = [it for it in bread_items if it["item"] in MINI_ITEMS]
    if not minis:
        return
    lines = [f"MINI ORDER — {business_name}", ""]
    for it in minis:
        lines.append(_bread_line(it))
    from b2b_bot.order_parsing import _delivery_line
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        lines += ["", dl]
    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines))


# ─── Confirm helper ───────────────────────────────────────────────────────────

async def _do_confirm_order(chat_id: int, pending: dict, context, reply_fn, from_user=None) -> None:
    business_name = get_business_name(chat_id)
    delivery_date = pending.get("delivery_date", (date.today() + timedelta(days=1)).isoformat())
    new_bread, _ = _split_mini_items(pending.get("bread_items", []), delivery_date)
    new_cake     = pending.get("cake_items", [])
    method_   = pending.get("delivery_method")
    time_str_ = pending.get("delivery_time")
    location_ = pending.get("location")

    editing_session_key = pending.get("editing_session_key")
    if editing_session_key:
        delete_b2b_order_session(chat_id, delivery_date, editing_session_key)

    # Merge all existing sessions for this date into the new order
    bread_items = list(new_bread)
    cake_items  = list(new_cake)
    for session in get_b2b_order_sessions(chat_id, delivery_date):
        for it in session["bread"]:
            key = (it["item"], it.get("grams"), it.get("notes"))
            for m in bread_items:
                if (m["item"], m.get("grams"), m.get("notes")) == key:
                    m["qty"] += it["qty"]
                    break
            else:
                bread_items.append(dict(it))
        for it in session["cake"]:
            key = (it["item"], it.get("order_type"), it.get("slices"))
            for m in cake_items:
                if (m["item"], m.get("order_type"), m.get("slices")) == key:
                    m["qty"] += it["qty"]
                    break
            else:
                cake_items.append(dict(it))
        delete_b2b_order_session(chat_id, delivery_date, session["session_key"])

    batch_id = str(uuid.uuid4())

    if bread_items:
        save_b2b_order(chat_id, business_name, bread_items, delivery_date, batch_id=batch_id)
        if any(it["item"] in INSTANT_BREAD_ITEMS for it in new_bread):
            await _notify_urgent_bread_order(
                context.bot, business_name, new_bread, method_, time_str_, location_, delivery_date,
            )
        if any(it["item"] in MINI_ITEMS for it in new_bread):
            await _notify_mini_order(
                context.bot, business_name, new_bread, method_, time_str_, location_, delivery_date,
            )
    if cake_items:
        save_b2b_cake_order(chat_id, business_name, cake_items, delivery_date, batch_id=batch_id)
        if new_cake:
            await _notify_cake_order(
                context.bot, business_name, new_cake, method_, time_str_, location_, delivery_date,
            )

    upsert_b2b_customer(chat_id, business_name, method_, time_str_, location_)

    confirmed_text = _build_confirmed_text(
        bread_items, cake_items, method_, time_str_, location_, delivery_date, from_user,
        delivery_cost=_delivery_cost_for(chat_id, method_),
    )
    logger.info("B2B order confirmed for %s (%s) delivery %s", business_name, chat_id, delivery_date)
    await reply_fn(confirmed_text, parse_mode=ParseMode.HTML)


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def handle_group_message(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    from shared.database import get_qty_pending as _get_qty_pending
    if _get_qty_pending(chat_id):
        from b2b_bot.menu_handlers import handle_qty_input
        await handle_qty_input(update, context)
        return

    business_name = get_business_name(chat_id)
    state = _state.get(chat_id) or get_order_state(chat_id) or {}

    if state.get("mode") == "awaiting_delivery":
        method, time_str = _parse_delivery_text(text)
        if not method or not time_str:
            await update.message.reply_text(
                "Please let me know: pickup or delivery, and what time?\n"
                "Example: Delivery at 8am  |  Pickup at 7am"
            )
            return
        location = business_name if method == "delivery" else None
        upsert_b2b_customer(chat_id, business_name, method, time_str, location)
        _state.pop(chat_id, None); set_order_state(chat_id, None)
        pending = _pending.get(chat_id) or get_pending_order(chat_id) or {}
        pending.update(delivery_method=method, delivery_time=time_str, location=location)
        _pending[chat_id] = pending; set_pending_order(chat_id, pending)
        await _send_confirmation(
            update, chat_id,
            _build_confirmation(pending.get("bread_items", []), pending.get("cake_items", []), method, time_str, location, pending.get("delivery_date"),
                                delivery_cost=_delivery_cost_for(chat_id, method)),
        )
        return

    if state.get("mode") == "awaiting_cake_spec":
        from b2b_bot.order_parsing import _WHOLE_RE, _SLICED_RE, _SLICE_COUNT_RE
        pending = _pending.get(chat_id) or get_pending_order(chat_id) or {}
        cake_items = pending.get("cake_items", [])
        needs_spec = state.get("needs_spec", [])
        lower = text.lower()

        for it in cake_items:
            if it["item"] not in needs_spec:
                continue
            cake_def = B2B_CAKE_MENU[it["item"]]
            if _WHOLE_RE.search(lower):
                it["order_type"] = "full"
            elif _SLICED_RE.search(lower) or _SLICE_COUNT_RE.search(lower):
                it["order_type"] = "sliced"
                m = _SLICE_COUNT_RE.search(lower)
                it["slices"] = int(m.group(1)) if m else cake_def["standard_slices"]

        still_unresolved = [it["item"] for it in cake_items if it.get("order_type") is None]
        if still_unresolved:
            await update.message.reply_text(
                f"Still need to know for: {', '.join(still_unresolved)}\n"
                "Please reply: sliced or whole?"
            )
            return

        _state.pop(chat_id, None); set_order_state(chat_id, None)
        pending["cake_items"] = cake_items
        _pending[chat_id] = pending; set_pending_order(chat_id, pending)
        m_ = pending.get("delivery_method")
        t_ = pending.get("delivery_time")
        l_ = pending.get("location")
        dd = pending.get("delivery_date")
        if not m_:
            _state[chat_id] = {"mode": "awaiting_delivery"}; set_order_state(chat_id, {"mode": "awaiting_delivery"})
            upsert_b2b_customer(chat_id, business_name)
            await update.message.reply_text(
                "Got it! One quick question — pickup or delivery, and what time?\n"
                "Example: Delivery at 8am  |  Pickup at 7am"
            )
        else:
            await _send_confirmation(
                update, chat_id,
                _build_confirmation(pending.get("bread_items", []), cake_items, m_, t_, l_, dd,
                                    delivery_cost=_delivery_cost_for(chat_id, m_)),
            )
        return

    pending = _pending.get(chat_id) or get_pending_order(chat_id)
    if pending and not state:
        _pending[chat_id] = pending
        lower_text = text.lower().strip()

        if lower_text in _CONFIRM_WORDS:
            _pending.pop(chat_id, None); set_pending_order(chat_id, None)
            _state.pop(chat_id, None); set_order_state(chat_id, None)
            _last_confirmation.pop(chat_id, None); set_last_confirmation_msg(chat_id, None)
            await _do_confirm_order(chat_id, pending, context, update.message.reply_text, from_user=update.effective_user)
            return

        if lower_text in _CANCEL_WORDS:
            _pending.pop(chat_id, None); set_pending_order(chat_id, None)
            _state.pop(chat_id, None); set_order_state(chat_id, None)
            _last_confirmation.pop(chat_id, None); set_last_confirmation_msg(chat_id, None)
            await update.message.reply_text("Order cancelled.")
            return

    # Nudge: show "Open Menu" button once per 6 hours
    from b2b_bot.menu_handlers import maybe_send_menu_prompt
    await maybe_send_menu_prompt(chat_id, context.bot)


async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    if query.data == "b2b_confirm":
        pending = _pending.pop(chat_id, None) or get_pending_order(chat_id)
        _state.pop(chat_id, None); set_order_state(chat_id, None)
        _last_confirmation.pop(chat_id, None); set_last_confirmation_msg(chat_id, None)
        set_pending_order(chat_id, None)
        if not pending:
            await query.edit_message_text("No pending order. Please send your order again.")
            return

        async def _reply(txt, parse_mode=None):
            await query.edit_message_text(txt, reply_markup=None, parse_mode=parse_mode)
        try:
            await _do_confirm_order(chat_id, pending, context, _reply, from_user=query.from_user)
        except Exception as e:
            logger.error("Error in _do_confirm_order for %s: %s", chat_id, e, exc_info=True)
            try:
                await query.edit_message_text("✓ Order confirmed!", reply_markup=None)
            except Exception:
                pass
        from b2b_bot.menu_keyboards import _menu_msg
        _menu_msg.pop(chat_id, None)
        set_menu_message_id(chat_id, None)

    elif query.data == "b2b_edit":
        pending = _pending.pop(chat_id, None) or get_pending_order(chat_id) or {}
        _state.pop(chat_id, None); set_order_state(chat_id, None)
        set_pending_order(chat_id, None)
        from b2b_bot.menu_keyboards import (
            _cart, _cart_time, _cart_date, _cart_method, _editing_session,
            _SESAME_LABEL_CODE, _category_keyboard, _cart_block,
        )
        from b2b_bot.menu import B2B_MENU as _BM
        cart = {}
        for it in pending.get("bread_items", []):
            if _BM.get(it["item"], {}).get("requires_grams") and it.get("grams"):
                sc  = _SESAME_LABEL_CODE.get(it.get("notes", ""))
                key = f"{it['item']}|{it['grams']}|{sc}" if sc else f"{it['item']}|{it['grams']}"
                cart[key] = it["qty"]
            else:
                cart[it["item"]] = it["qty"]
        for it in pending.get("cake_items", []):
            cart[it["item"]] = it["qty"]
        _cart[chat_id] = cart
        if pending.get("delivery_time"):
            _cart_time[chat_id] = pending["delivery_time"]
        if pending.get("delivery_date"):
            _cart_date[chat_id] = pending["delivery_date"]
        if pending.get("delivery_method"):
            _cart_method[chat_id] = pending["delivery_method"]
        if pending.get("editing_session_key"):
            from shared.database import set_editing_session
            _editing_session[chat_id] = pending["editing_session_key"]
            set_editing_session(chat_id, pending["editing_session_key"])
        await query.edit_message_text(
            f"✏️ Edit your order:\n\n{_cart_block(chat_id)}",
            reply_markup=_category_keyboard(chat_id),
        )

    elif query.data == "b2b_cancel":
        pending        = _pending.get(chat_id) or get_pending_order(chat_id) or {}
        existing_bread = pending.get("existing_bread", [])
        existing_cake  = pending.get("existing_cake", [])

        if existing_bread or existing_cake:
            cancelled_bread = pending.get("bread_items", [])
            cancelled_cake  = pending.get("cake_items", [])
            delivery_date   = pending.get("delivery_date", "")

            lines = ["Cancelled:"]
            for it in cancelled_bread:
                line = f"  ✗ {it['qty']}x {it['item']}"
                if it.get("grams"):
                    line += f" — {it['grams']}g"
                lines.append(line)
            for it in cancelled_cake:
                lines.append(f"  ✗ {it['qty']}x {it['item']}")

            lines += ["", "─" * 32, "",
                      f"Your existing order for {_date_label(delivery_date)} is still active:"]
            for ei in existing_bread + existing_cake:
                ei_line = f"  • {ei['qty']}x {ei['item']}"
                if ei.get("grams"):
                    ei_line += f" — {ei['grams']}g"
                lines.append(ei_line)
            lines += ["", "Would you like to keep it or cancel everything?"]

            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Confirm ✓",    callback_data="b2b_keep_existing"),
                    InlineKeyboardButton("Cancel all ✗", callback_data="b2b_cancel_all"),
                ]]),
            )
        else:
            _pending.pop(chat_id, None); set_pending_order(chat_id, None)
            _state.pop(chat_id, None); set_order_state(chat_id, None)
            await query.edit_message_text("Order cancelled.")

    elif query.data == "b2b_keep_existing":
        _pending.pop(chat_id, None); set_pending_order(chat_id, None)
        _state.pop(chat_id, None); set_order_state(chat_id, None)
        await query.edit_message_text("Your existing order remains active. ✓")

    elif query.data == "b2b_cancel_all":
        pending       = _pending.pop(chat_id, None) or get_pending_order(chat_id) or {}
        _state.pop(chat_id, None); set_order_state(chat_id, None)
        set_pending_order(chat_id, None)
        delivery_date = pending.get("delivery_date")
        if delivery_date:
            delete_b2b_orders_for_date(chat_id, delivery_date)
            delete_b2b_cake_orders_for_date(chat_id, delivery_date)
        label = _date_label(delivery_date) if delivery_date else "this delivery"
        await query.edit_message_text(f"All orders for {label} have been cancelled.")

    elif query.data == "b2b_rec_setup_confirm":
        from b2b_bot.menu_keyboards import _cart, _cart_time, _cart_date, _cart_method, _recurring_days, _recurring_pending
        pending = _recurring_pending.pop(chat_id, None)
        if not pending:
            await query.edit_message_text("Setup session expired. Please start again via /menu.")
            return
        _recurring_days.pop(chat_id, None)
        business_name = get_business_name(chat_id)
        rec_id = save_b2b_recurring_order(
            chat_id,
            business_name,
            pending["items"],
            pending.get("days", []),
            pending.get("time", ""),
            pending.get("method", ""),
        )
        location = business_name if pending.get("method") == "delivery" else None
        upsert_b2b_customer(chat_id, business_name, pending.get("method"), pending.get("time"), location)
        _cart.pop(chat_id, None)
        _cart_time.pop(chat_id, None)
        _cart_date.pop(chat_id, None)
        _cart_method.pop(chat_id, None)
        from b2b_bot.menu_keyboards import _menu_msg
        _menu_msg.pop(chat_id, None)
        set_menu_message_id(chat_id, None)
        items      = pending.get("items", {})
        bread_list = items.get("bread_items", [])
        confirmed_text = _build_confirmed_text(
            bread_list, [],
            pending.get("method"),
            pending.get("time", ""),
            None,
            None,
            query.from_user,
            days_list=pending.get("days", []),
            delivery_cost=_delivery_cost_for(chat_id, pending.get("method")),
        )
        try:
            await query.edit_message_text("✅ Standing order saved.", reply_markup=None)
        except Exception:
            pass
        from telegram.constants import ParseMode
        await context.bot.send_message(chat_id, confirmed_text, parse_mode=ParseMode.HTML)
        logger.info("Recurring order #%s saved for %s (%s)", rec_id, business_name, chat_id)

    elif query.data == "b2b_rec_setup_cancel":
        from b2b_bot.menu_keyboards import _cart, _recurring_days, _recurring_pending, _category_keyboard, _cart_block
        _recurring_pending.pop(chat_id, None)
        _recurring_days.pop(chat_id, None)
        await query.edit_message_text(
            f"Standing order cancelled.\n\n📋 Select a category:\n\n{_cart_block(chat_id)}",
            reply_markup=_category_keyboard(chat_id),
        )

    elif query.data.startswith("b2b_rec_confirm_"):
        rest = query.data[16:]
        rec_id_str, fulfillment_date = rest.rsplit("_", 1)
        rec_id = int(rec_id_str)
        rec = get_recurring_order(rec_id)
        if not rec:
            await query.edit_message_text("Standing order not found.")
            return
        conf = get_or_create_recurring_confirmation(rec_id, fulfillment_date)
        if conf["status"] == "confirmed":
            await query.answer("Already confirmed ✅", show_alert=True)
            return
        if conf["status"] == "skipped":
            await query.answer("This order was already skipped.", show_alert=True)
            return
        changed = confirm_recurring_instance(rec_id, fulfillment_date)
        if not changed:
            await query.answer("Could not confirm — status may have changed.", show_alert=True)
            return
        import json
        items = json.loads(rec["items_json"])
        business_name = get_business_name(chat_id)
        import uuid
        batch_id = f"rec_{rec_id}_{fulfillment_date}"
        if items.get("bread_items"):
            save_b2b_order(chat_id, business_name, items["bread_items"], fulfillment_date, batch_id=batch_id)
        upsert_b2b_customer(chat_id, business_name, rec["delivery_method"], rec["delivery_time"])
        from b2b_bot.recurring import days_label
        days_lbl = days_label(json.loads(rec["days_of_week"]))
        await query.edit_message_text(
            f"✅ Confirmed! Your {days_lbl} order is in for {fulfillment_date}.\n\nSee you tomorrow!",
            reply_markup=None,
        )
        logger.info("Recurring order #%s confirmed for %s by %s", rec_id, fulfillment_date, chat_id)

    elif query.data.startswith("b2b_rec_skip_"):
        rest = query.data[13:]
        rec_id_str, fulfillment_date = rest.rsplit("_", 1)
        rec_id = int(rec_id_str)
        conf = get_or_create_recurring_confirmation(rec_id, fulfillment_date)
        if conf["status"] != "pending":
            await query.answer(f"Already {conf['status']}.", show_alert=True)
            return
        skip_recurring_instance(rec_id, fulfillment_date)
        rec = get_recurring_order(rec_id)
        from b2b_bot.recurring import days_label
        import json
        days_lbl = days_label(json.loads(rec["days_of_week"])) if rec else "standing"
        await query.edit_message_text(
            f"⏭ Skipped for {fulfillment_date}. Your {days_lbl} order will resume next time.",
            reply_markup=None,
        )


async def handle_order_photo(bot, chat_id: int, image_bytes: bytes, message_id: int, mime_type: str = "image/jpeg", ai_items: list = None) -> None:
    business_name = get_business_name(chat_id)
    if ai_items is None:
        ai_items = await extract_b2b_order_from_image(image_bytes, mime_type=mime_type)
    ai_bread, ai_cake, unmatched = _ai_items_to_orders(ai_items)

    if not ai_bread and not ai_cake and not unmatched:
        await bot.send_message(
            chat_id,
            "I couldn't read any order items from that photo. Please type your order.",
            reply_to_message_id=message_id,
        )
        return

    bread_items = _resolve_bread_history(chat_id, ai_bread)
    cake_items, needs_spec = _resolve_cake_history(chat_id, ai_cake)
    for it in cake_items:
        if it.get("order_type") is None:
            it["order_type"] = "full"
            it["order_type_source"] = "default"

    customer = get_b2b_customer(chat_id)
    method   = customer["delivery_method"] if customer else None
    time_str = customer["delivery_time"]   if customer else None
    location = customer["location"]        if customer else None
    delivery_date = (date.today() + timedelta(days=1)).isoformat()

    bread_items, photo_rejected = _split_mini_items(bread_items, delivery_date)

    _pending[chat_id] = {
        "bread_items": bread_items, "cake_items": cake_items,
        "delivery_method": method, "delivery_time": time_str,
        "location": location, "delivery_date": delivery_date,
        "ai_unmatched": unmatched,
    }
    set_pending_order(chat_id, _pending[chat_id])

    if needs_spec:
        _state[chat_id] = {"mode": "awaiting_cake_spec", "needs_spec": needs_spec}
        set_order_state(chat_id, _state[chat_id])
        await bot.send_message(
            chat_id,
            f"Got the order from your photo! For the {', '.join(needs_spec)} — sliced or whole?",
            reply_to_message_id=message_id,
        )
        return

    if not method:
        _state[chat_id] = {"mode": "awaiting_delivery"}
        set_order_state(chat_id, _state[chat_id])
        upsert_b2b_customer(chat_id, business_name)
        await bot.send_message(
            chat_id,
            "Got the order from your photo! Pickup or delivery, and what time?\n"
            "Example: Delivery at 8am  |  Pickup at 7am",
            reply_to_message_id=message_id,
        )
        return

    msg = _build_confirmation(bread_items, cake_items, method, time_str, location, delivery_date,
                              heading="Order from your photo:",
                              delivery_cost=_delivery_cost_for(chat_id, method))
    if unmatched:
        unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in unmatched)
        msg = msg.replace("Is this correct?", f"Not recognised:\n{unknown_lines}\n\nPlease edit or let us know what these are.\n\nIs this correct?")
    if photo_rejected:
        msg += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(photo_rejected)

    await _send_confirmation(bot, chat_id, msg)
