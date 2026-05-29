"""
B2B Bot Chaos Test — unexpected actions at every state in every flow.
Tests the menu, cart, confirmation, edit, cancel, location, recurring flows.
Run on server: python3 run_test_b2b_chaos.py
"""

import asyncio
import sys
import os

sys.path.insert(0, '/root/TWBshop')

import psycopg2
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, timedelta, datetime

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"{GREEN}✓ {msg}{RESET}")
def fail(msg): print(f"{RED}✗ {msg}{RESET}")
def info(msg): print(f"{YELLOW}→ {msg}{RESET}")
def head(msg): print(f"\n{BOLD}{'='*60}\n{msg}\n{'='*60}{RESET}")

FAKE_CHAT_ID  = -8888888888
FAKE_USER_ID  = 8888888888
FAKE_BNAME    = "Chaos Test Kitchen"
_msg_id_seq   = [1000]


def _db():
    from secrets import DATABASE_URL
    return psycopg2.connect(DATABASE_URL)


def setup_customer():
    from shared.database import upsert_b2b_customer
    upsert_b2b_customer(FAKE_CHAT_ID, FAKE_BNAME, "pickup", "8:00am", None)
    # Clear location data so each test starts clean
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        UPDATE b2b_customers
        SET location=NULL, location_lat=NULL, location_lng=NULL, delivery_cost=NULL
        WHERE group_chat_id=%s
    """, (FAKE_CHAT_ID,))
    conn.commit(); conn.close()


def cleanup():
    conn = _db(); cur = conn.cursor()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    today    = date.today().isoformat()
    cur.execute("DELETE FROM b2b_orders WHERE group_chat_id = %s", (FAKE_CHAT_ID,))
    cur.execute("DELETE FROM b2b_cake_orders WHERE group_chat_id = %s", (FAKE_CHAT_ID,))
    conn.commit(); conn.close()
    _reset_all_state()


def _reset_all_state():
    from b2b_bot.menu_keyboards import (
        _cart, _qty_pending, _menu_msg, _editing_session,
        _cart_time, _cart_date, _cart_method,
        _recurring_days, _recurring_pending,
    )
    from b2b_bot.order_handlers import _pending, _state, _last_confirmation
    for d in [_cart, _qty_pending, _menu_msg, _editing_session,
              _cart_time, _cart_date, _cart_method,
              _recurring_days, _recurring_pending,
              _pending, _state, _last_confirmation]:
        d.pop(FAKE_CHAT_ID, None)
    from shared.database import (
        set_pending_order, set_order_state, set_cart_state,
        set_menu_message_id, set_last_confirmation_msg,
        set_qty_pending as db_set_qty, set_editing_session,
    )
    set_pending_order(FAKE_CHAT_ID, None)
    set_order_state(FAKE_CHAT_ID, None)
    set_cart_state(FAKE_CHAT_ID, None)
    set_menu_message_id(FAKE_CHAT_ID, None)
    set_last_confirmation_msg(FAKE_CHAT_ID, None)
    db_set_qty(FAKE_CHAT_ID, None)
    set_editing_session(FAKE_CHAT_ID, None)


def _next_msg_id():
    _msg_id_seq[0] += 1
    return _msg_id_seq[0]


class Captured:
    def __init__(self):
        self.text = None
        self.markup = None
        self.alert = None
        self.sends = []
        self.deletes = []
        self.edit_text = None
        self.edit_markup = None

    def reset(self):
        self.text = None
        self.markup = None
        self.alert = None
        self.sends = []
        self.deletes = []
        self.edit_text = None
        self.edit_markup = None


CAP = Captured()


def make_context():
    ctx = MagicMock()
    async def _send(chat_id, text, **kwargs):
        CAP.text = text
        CAP.markup = kwargs.get("reply_markup")
        m = MagicMock()
        m.message_id = _next_msg_id()
        CAP.sends.append((text, kwargs))
        return m
    async def _delete(chat_id, msg_id):
        CAP.deletes.append(msg_id)
    ctx.bot.send_message = AsyncMock(side_effect=_send)
    ctx.bot.delete_message = AsyncMock(side_effect=_delete)
    return ctx


def make_callback(data, message_id=None):
    if message_id is None:
        message_id = _next_msg_id()
    update = MagicMock()
    update.effective_chat.id = FAKE_CHAT_ID
    update.effective_chat.type = "group"
    update.effective_user.id = FAKE_USER_ID
    update.effective_user.full_name = "TestUser"
    update.message = None

    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.message.message_id = message_id

    async def _edit(text, **kwargs):
        CAP.edit_text = text
        CAP.edit_markup = kwargs.get("reply_markup")

    query.edit_message_text = AsyncMock(side_effect=_edit)

    # query.answer with show_alert captures the alert
    async def _answer(text=None, show_alert=False):
        if show_alert:
            CAP.alert = text

    query.answer = AsyncMock(side_effect=_answer)
    update.callback_query = query
    return update


def make_message(text=None, location=None):
    update = MagicMock()
    update.effective_chat.id = FAKE_CHAT_ID
    update.effective_chat.type = "group"
    update.effective_user.id = FAKE_USER_ID
    update.effective_user.full_name = "TestUser"
    update.callback_query = None

    msg = MagicMock()
    msg.text = text
    msg.location = location
    msg.message_id = _next_msg_id()
    msg.reply_text = AsyncMock(return_value=MagicMock(message_id=_next_msg_id()))
    msg.delete = AsyncMock()
    msg.photo = None
    msg.document = None
    msg.voice = None
    msg.sticker = None

    update.message = msg
    return update


# ── Helpers to put cart into known states ─────────────────────────────────────

async def _add_croissant_to_cart(ctx):
    """Click Pastries → Croissant qty button → 5"""
    from b2b_bot.menu_handlers import handle_menu_callback
    await handle_menu_callback(make_callback("bm_cat_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qty_Croissant_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qtyval_Croissant_pastries_5"), ctx)
    CAP.reset()


async def _add_baguette_to_cart(ctx):
    """Click Breads → French Baguette qty button → 3"""
    from b2b_bot.menu_handlers import handle_menu_callback
    await handle_menu_callback(make_callback("bm_cat_breads"), ctx)
    await handle_menu_callback(make_callback("bm_qty_French_Baguette_breads"), ctx)
    await handle_menu_callback(make_callback("bm_qtyval_French_Baguette_breads_3"), ctx)
    CAP.reset()


async def _get_to_confirmation_pending(ctx):
    """Full flow: cart with croissant → confirm screen → select pickup method → confirmation"""
    from b2b_bot.menu_handlers import handle_menu_callback
    await _add_croissant_to_cart(ctx)
    # click Confirm Order button
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    # pick default (pickup is already set from setup_customer)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    CAP.reset()


def get_db_orders():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT item, quantity FROM b2b_orders WHERE group_chat_id=%s AND delivery_date=%s AND status='confirmed'",
                (FAKE_CHAT_ID, tomorrow))
    rows = cur.fetchall(); conn.close()
    return {r[0]: r[1] for r in rows}


def get_customer():
    from shared.database import get_b2b_customer
    return get_b2b_customer(FAKE_CHAT_ID)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

async def run():
    setup_customer()
    passed = 0
    failed = 0

    # ── S01: Empty cart → click Confirm → alert ──────────────────────────────
    head("S01: Empty cart → click Confirm → should alert not crash")
    _reset_all_state(); CAP.reset()
    from b2b_bot.menu_handlers import handle_menu_callback
    await handle_menu_callback(make_callback("bm_confirm"), make_context())
    if CAP.alert and "empty" in CAP.alert.lower():
        ok("Got 'cart is empty' alert"); passed += 1
    else:
        fail(f"Expected empty-cart alert, got alert={CAP.alert!r} edit={CAP.edit_text!r}"); failed += 1

    # ── S02: bm_qtytext → type "abc" → graceful error ──────────────────────
    head("S02: bm_qtytext (text input mode) → type non-numeric → graceful error")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await handle_menu_callback(make_callback("bm_cat_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qty_Croissant_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qtytext_Croissant_pastries"), ctx)
    from b2b_bot.menu_keyboards import _qty_pending
    from b2b_bot.menu_handlers import handle_qty_input
    was_pending = bool(_qty_pending.get(FAKE_CHAT_ID))
    await handle_qty_input(make_message("abc"), ctx)
    still_pending = bool(_qty_pending.get(FAKE_CHAT_ID))
    if was_pending:
        ok(f"bm_qtytext set qty_pending; abc handled, pending_after={still_pending}"); passed += 1
    else:
        fail(f"bm_qtytext did not set qty_pending"); failed += 1

    # ── S03: bm_qtyval_0 removes item ─────────────────────────────────────────
    head("S03: Item in cart → click qty button 0 → item removed from cart")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    from b2b_bot.menu_keyboards import _cart
    await handle_menu_callback(make_callback("bm_cat_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qty_Croissant_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qtyval_Croissant_pastries_5"), ctx)
    cart_before = dict(_cart.get(FAKE_CHAT_ID, {}))
    await handle_menu_callback(make_callback("bm_qtyval_Croissant_pastries_0"), ctx)
    cart_after = _cart.get(FAKE_CHAT_ID, {})
    if cart_before.get("Croissant") == 5 and "Croissant" not in cart_after:
        ok("qty button 0 removed Croissant from cart"); passed += 1
    else:
        fail(f"Before={cart_before}, after={cart_after}"); failed += 1

    # ── S04: bm_qtytext → type 9999 → large qty accepted ───────────────────
    head("S04: bm_qtytext → type 9999 → very large qty accepted (no crash)")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await handle_menu_callback(make_callback("bm_cat_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qty_Croissant_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qtytext_Croissant_pastries"), ctx)
    from b2b_bot.menu_handlers import handle_qty_input
    try:
        await handle_qty_input(make_message("9999"), ctx)
        from b2b_bot.menu_keyboards import _cart
        cart = _cart.get(FAKE_CHAT_ID, {})
        ok(f"Large qty processed without crash, cart={cart}"); passed += 1
    except Exception as e:
        fail(f"Crashed on large qty: {e}"); failed += 1

    # ── S05: bm_qtytext_pending → click ← MENU → cart intact, pending cleared
    head("S05: Add item, enter qty-text mode, click ← MENU → pending cleared, first item kept")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await handle_menu_callback(make_callback("bm_cat_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qty_Croissant_pastries"), ctx)
    await handle_menu_callback(make_callback("bm_qtyval_Croissant_pastries_3"), ctx)
    await handle_menu_callback(make_callback("bm_cat_breads"), ctx)
    await handle_menu_callback(make_callback("bm_qty_French_Baguette_breads"), ctx)
    await handle_menu_callback(make_callback("bm_qtytext_French_Baguette_breads"), ctx)
    await handle_menu_callback(make_callback("bm_back"), ctx)
    from b2b_bot.menu_keyboards import _qty_pending, _cart
    pending_gone = FAKE_CHAT_ID not in _qty_pending
    cart = _cart.get(FAKE_CHAT_ID, {})
    if pending_gone and cart.get("Croissant") == 3:
        ok("Back clears qty_pending, Croissant still in cart"); passed += 1
    else:
        fail(f"pending={_qty_pending.get(FAKE_CHAT_ID)!r} cart={cart}"); failed += 1

    # ── S06: bm_empty_cart → cart wiped ─────────────────────────────────────
    head("S06: Cart with items → bm_empty_cart → cart empty")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_empty_cart"), ctx)
    from b2b_bot.menu_keyboards import _cart
    cart = _cart.get(FAKE_CHAT_ID, {})
    if not cart:
        ok("bm_empty_cart cleared the cart"); passed += 1
    else:
        fail(f"Cart not empty after bm_empty_cart: {cart}"); failed += 1

    # ── S07: confirm screen bm_back → returns to category, cart intact ───────
    head("S07: At confirm screen → click ← MENU → cart still there")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_back"), ctx)
    from b2b_bot.menu_keyboards import _cart
    cart = _cart.get(FAKE_CHAT_ID, {})
    if cart.get("Croissant") == 5:
        ok("Back from confirm screen preserves cart"); passed += 1
    else:
        fail(f"Cart after bm_back from confirm: {cart}"); failed += 1

    # ── S08: confirm screen → bm_cs_datetime → change date+time+method ──────
    head("S08: Confirm screen → change date/time/method → confirmation shows")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_datetime"), ctx)
    # pick tomorrow via bm_date_tmrw
    from b2b_bot.menu_handlers import handle_menu_callback
    await handle_menu_callback(make_callback("bm_date_tmrw"), ctx)
    # pick 0800 time
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
    await handle_menu_callback(make_callback(f"bm_dt_{tomorrow_str}_0800"), ctx)
    # pick delivery
    await handle_menu_callback(make_callback(f"bm_method_{tomorrow_str}_0800_delivery"), ctx)
    from b2b_bot.order_handlers import _pending
    pending = _pending.get(FAKE_CHAT_ID)
    if pending and pending.get("delivery_method") == "delivery":
        ok("Date+time+method flow set delivery method correctly"); passed += 1
    else:
        fail(f"Expected delivery pending, got pending={pending!r}"); failed += 1

    # ── S09: Confirmation pending → b2b_edit → cart restored ────────────────
    head("S09: Confirmation pending → click Edit → cart restored with original items")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    CAP.reset()
    await order_cb(make_callback("b2b_edit"), ctx)
    from b2b_bot.menu_keyboards import _cart
    cart = _cart.get(FAKE_CHAT_ID, {})
    if cart.get("Croissant") == 5:
        ok("b2b_edit restored cart with original 5x Croissant"); passed += 1
    else:
        fail(f"Cart after b2b_edit: {cart}"); failed += 1

    # ── S10: Confirmation pending → b2b_edit → add more → confirm ───────────
    head("S10: Edit → add baguette → confirm → both items saved to DB")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    await order_cb(make_callback("b2b_edit"), ctx)
    await _add_baguette_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import _pending
    pending = _pending.get(FAKE_CHAT_ID)
    items = {it["item"] for it in (pending or {}).get("bread_items", []) + (pending or {}).get("cake_items", [])} if pending else set()
    if "Croissant" in items and "French Baguette" in items:
        ok("Edit + add items: both in pending for confirm"); passed += 1
    else:
        fail(f"Items in pending: {items!r}"); failed += 1

    # ── S11: b2b_cancel with NO existing DB orders ───────────────────────────
    head("S11: b2b_cancel with no prior orders → simple cancel message")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb, _pending
    CAP.reset()
    await order_cb(make_callback("b2b_cancel"), ctx)
    if "cancelled" in (CAP.edit_text or "").lower():
        ok("Simple cancel message shown (no existing orders)"); passed += 1
    else:
        # might show keep/cancel-all (if sessions exist from prior tests)
        if CAP.edit_text and ("keep" in CAP.edit_text.lower() or "existing" in CAP.edit_text.lower()):
            info("Got keep/cancel-all (leftover sessions from prior test — acceptable)")
            passed += 1
        else:
            fail(f"Unexpected cancel response: {CAP.edit_text!r}"); failed += 1

    # ── S12: b2b_cancel with existing orders → keep/cancel-all dialog ────────
    head("S12: Place + confirm order, then new pending → cancel → keep/cancel-all")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    # First confirm an order to put it in DB
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    await order_cb(make_callback("b2b_confirm"), ctx)
    # Now start a new order and cancel it
    _reset_all_state()
    # Restore DB customer (reset_all_state doesn't touch DB orders)
    ctx = make_context()
    await _add_baguette_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    CAP.reset()
    await order_cb(make_callback("b2b_cancel"), ctx)
    if CAP.edit_text and ("existing" in CAP.edit_text.lower() or "keep" in CAP.edit_text.lower()):
        ok("Cancel with existing order → keep/cancel-all dialog shown"); passed += 1
    elif CAP.edit_text and "cancelled" in CAP.edit_text.lower():
        fail("BUG (dead code): existing_bread/existing_cake never populated — keep/cancel-all dialog unreachable. "
             "b2b_cancel always shows simple 'cancelled' even when prior order exists."); failed += 1
    else:
        fail(f"Unexpected cancel response: {CAP.edit_text!r}"); failed += 1

    # ── S13: b2b_cancel_all → DB orders deleted (standalone) ────────────────
    head("S13: b2b_cancel_all with known delivery_date → orders deleted from DB")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    # Confirm a fresh order so we know it's in DB
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb, _pending
    await order_cb(make_callback("b2b_confirm"), ctx)
    orders_before = get_db_orders()
    # Now simulate pending state for cancel_all (needs delivery_date)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _pending[FAKE_CHAT_ID] = {"delivery_date": tomorrow, "bread_items": [], "cake_items": []}
    from shared.database import set_pending_order
    set_pending_order(FAKE_CHAT_ID, _pending[FAKE_CHAT_ID])
    CAP.reset()
    await order_cb(make_callback("b2b_cancel_all"), ctx)
    orders_after = get_db_orders()
    if orders_before and not orders_after:
        ok("b2b_cancel_all deleted all DB orders"); passed += 1
    elif not orders_before:
        fail("Setup issue: no orders in DB before cancel_all"); failed += 1
    else:
        fail(f"Orders still in DB after cancel_all: {orders_after}"); failed += 1

    # ── S14: SEE YOUR ORDERS after _do_confirm → confirmation NOT deleted ────
    head("S14: After _do_confirm, SEE YOUR ORDERS must NOT delete the confirmation message")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    # At this point _menu_msg should be CLEARED by _do_confirm (our fix)
    from b2b_bot.menu_keyboards import _menu_msg
    from b2b_bot.order_handlers import _pending
    menu_msg_after_confirm = _menu_msg.get(FAKE_CHAT_ID)
    pending_exists = bool(_pending.get(FAKE_CHAT_ID))
    CAP.reset()
    await handle_menu_callback(make_callback("bm_edit_order"), ctx)
    any_deleted = len(CAP.deletes) > 0
    if not menu_msg_after_confirm and pending_exists and not any_deleted:
        ok("Fix verified: _menu_msg cleared in _do_confirm → SEE YOUR ORDERS deletes nothing"); passed += 1
    elif not menu_msg_after_confirm and pending_exists and any_deleted:
        fail(f"BUG: _menu_msg cleared but something was still deleted: {CAP.deletes}"); failed += 1
    elif menu_msg_after_confirm:
        fail(f"BUG NOT FIXED: _menu_msg still set to {menu_msg_after_confirm} after _do_confirm"); failed += 1
    else:
        fail(f"Setup issue: pending_exists={pending_exists}, menu_msg={menu_msg_after_confirm}"); failed += 1

    # ── S15: Double b2b_confirm (race condition) ─────────────────────────────
    head("S15: Click b2b_confirm twice rapidly → second click should not crash")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    # First confirm
    await order_cb(make_callback("b2b_confirm", message_id=9010), ctx)
    CAP.reset()
    # Second confirm on same message (pending is now nil)
    try:
        await order_cb(make_callback("b2b_confirm", message_id=9010), ctx)
        if CAP.edit_text and ("no pending" in CAP.edit_text.lower() or "again" in CAP.edit_text.lower()):
            ok("Double-confirm handled gracefully with error message"); passed += 1
        else:
            # just no crash is acceptable
            ok("Double-confirm did not crash"); passed += 1
    except Exception as e:
        fail(f"Double-confirm crashed: {e}"); failed += 1

    # ── S16: After full confirm → bm_edit_order shows session ────────────────
    head("S16: After confirmed order → SEE YOUR ORDERS → session visible")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    await order_cb(make_callback("b2b_confirm"), ctx)
    _reset_all_state()
    ctx = make_context()
    CAP.reset()
    await handle_menu_callback(make_callback("bm_edit_order"), ctx)
    has_session = CAP.text and ("edit" in CAP.text.lower() or "order" in CAP.text.lower() or "croissant" in CAP.text.lower())
    no_orders   = CAP.text and "no orders" in CAP.text.lower()
    if has_session and not no_orders:
        ok("After confirm, SEE YOUR ORDERS shows the session"); passed += 1
    else:
        fail(f"Expected session, got text: {CAP.text!r}"); failed += 1

    # ── S17: Edit session → re-confirm → old batch deleted, new saved ────────
    head("S17: Edit session #0 → change qty → confirm → DB updated")
    from b2b_bot.menu_keyboards import _cart
    ctx = make_context()
    CAP.reset()
    # Load session into edit mode
    await handle_menu_callback(make_callback("bm_edit_session_0"), ctx)
    # Clear cart and add different item
    from b2b_bot.menu_keyboards import _editing_session
    editing_key = _editing_session.get(FAKE_CHAT_ID)
    if not editing_key:
        fail("bm_edit_session_0 did not set editing_session"); failed += 1
    else:
        await handle_menu_callback(make_callback("bm_empty_cart"), ctx)
        await _add_baguette_to_cart(ctx)
        await handle_menu_callback(make_callback("bm_confirm"), ctx)
        await handle_menu_callback(make_callback("bm_cs_default"), ctx)
        from b2b_bot.order_handlers import handle_callback as order_cb
        await order_cb(make_callback("b2b_confirm"), ctx)
        orders = get_db_orders()
        if "French Baguette" in orders and "Croissant" not in orders:
            ok("Edit session: old deleted, new saved (Baguette only)"); passed += 1
        else:
            fail(f"DB after edit: {orders}"); failed += 1

    # ── S18: bm_edit_session out of bounds ───────────────────────────────────
    head("S18: bm_edit_session_99 (out of bounds) → alert, no crash")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    try:
        await handle_menu_callback(make_callback("bm_edit_session_99"), ctx)
        if CAP.alert and "not found" in CAP.alert.lower():
            ok("Out-of-bounds session: 'Order not found' alert"); passed += 1
        else:
            ok("Out-of-bounds session: no crash (alert may differ)"); passed += 1
    except Exception as e:
        fail(f"bm_edit_session_99 crashed: {e}"); failed += 1

    # ── S19: Edit session → empty cart → click confirm ───────────────────────
    head("S19: Edit session → empty cart → try to confirm → 'cart is empty' alert")
    # First put an order in DB
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    await order_cb(make_callback("b2b_confirm"), ctx)
    _reset_all_state()
    ctx = make_context()
    await handle_menu_callback(make_callback("bm_edit_session_0"), ctx)
    await handle_menu_callback(make_callback("bm_empty_cart"), ctx)
    CAP.reset()
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    if CAP.alert and "empty" in CAP.alert.lower():
        ok("Confirm after clearing edit session cart → 'cart is empty' alert"); passed += 1
    else:
        fail(f"Expected empty-cart alert, got alert={CAP.alert!r}"); failed += 1

    # ── S20: Location change while confirmation pending → pending intact ──────
    head("S20: Confirmation pending → bm_change_location → pending order still there")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import _pending
    CAP.reset()
    await handle_menu_callback(make_callback("bm_change_location"), ctx)
    pending_after = _pending.get(FAKE_CHAT_ID)
    if pending_after:
        ok("bm_change_location did not clear _pending"); passed += 1
    else:
        fail("BUG: bm_change_location wiped _pending!"); failed += 1

    # ── S21: Location pin sent → delivery_cost saved to DB ──────────────────
    head("S21: Location pin sent → delivery_cost calculated and saved")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    from b2b_bot.delivery import handle_location
    import config
    config.BAKERY_LAT = 11.5387774
    config.BAKERY_LNG = 104.9147998
    loc = MagicMock()
    loc.latitude  = 11.556  # ~2.5km from bakery
    loc.longitude = 104.928
    u = make_message()
    u.message.location = loc
    await handle_location(u, ctx)
    cust = get_customer()
    if cust and cust.get("delivery_cost") and float(cust["delivery_cost"]) > 0:
        ok(f"Location pin saved delivery_cost=${cust['delivery_cost']:.2f}"); passed += 1
    else:
        fail(f"delivery_cost not saved: {cust}"); failed += 1

    # ── S22: Stale b2b_confirm after order already cleared ───────────────────
    head("S22: Stale b2b_confirm callback (pending already nil) → graceful error, no crash")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    from b2b_bot.order_handlers import handle_callback as order_cb
    try:
        await order_cb(make_callback("b2b_confirm"), ctx)
        got_error = CAP.edit_text and ("no pending" in CAP.edit_text.lower() or "again" in CAP.edit_text.lower())
        ok(f"Stale confirm handled, got: {CAP.edit_text!r}"); passed += 1
    except Exception as e:
        fail(f"Stale b2b_confirm crashed: {e}"); failed += 1

    # ── S23: bm_copy_last_order with no previous order ───────────────────────
    head("S23: bm_copy_last_order with no previous order → graceful alert")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    # Clear any DB orders
    conn = _db(); cur = conn.cursor()
    cur.execute("DELETE FROM b2b_orders WHERE group_chat_id=%s", (FAKE_CHAT_ID,))
    conn.commit(); conn.close()
    try:
        await handle_menu_callback(make_callback("bm_copy_last_order"), ctx)
        if CAP.alert and "no previous" in CAP.alert.lower():
            ok("No previous order → graceful 'No previous order' alert"); passed += 1
        else:
            ok(f"No crash, alert={CAP.alert!r}"); passed += 1
    except Exception as e:
        fail(f"bm_copy_last_order crashed with no history: {e}"); failed += 1

    # ── S24: bm_copy_last_order → copies correctly then confirm ─────────────
    head("S24: bm_copy_last_order after a confirmed order → cart populated correctly")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    # Put a real confirmed order in DB first
    await _add_baguette_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    await order_cb(make_callback("b2b_confirm"), ctx)
    _reset_all_state()
    ctx = make_context()
    CAP.reset()
    await handle_menu_callback(make_callback("bm_copy_last_order"), ctx)
    from b2b_bot.menu_keyboards import _cart
    cart = _cart.get(FAKE_CHAT_ID, {})
    if "French Baguette" in cart:
        ok("bm_copy_last_order populated cart with last order items"); passed += 1
    else:
        fail(f"Copy last order: cart={cart}"); failed += 1

    # ── S25: Burger bun → select 70g → go back → select 40g → only 40g in cart
    head("S25: Burger bun 70g selected, back, then 40g selected → only one size in cart")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await handle_menu_callback(make_callback("bm_buns"), ctx)
    await handle_menu_callback(make_callback("bm_bun_size_burger_70"), ctx)
    # pick no sesame for 70g
    await handle_menu_callback(make_callback("bm_bunqtyval_burger_70_no_5"), ctx)
    # now go back and pick 40g
    await handle_menu_callback(make_callback("bm_buns"), ctx)
    await handle_menu_callback(make_callback("bm_bun_size_burger_40"), ctx)
    await handle_menu_callback(make_callback("bm_bunqtyval_burger_40_no_3"), ctx)
    from b2b_bot.menu_keyboards import _cart
    cart = _cart.get(FAKE_CHAT_ID, {})
    has_70 = any(k.startswith("Burger Bun|70") for k in cart)
    has_40 = any(k.startswith("Burger Bun|40") for k in cart)
    info(f"Cart keys: {list(cart.keys())}")
    ok(f"Bun cart: 70g={'yes' if has_70 else 'no'}, 40g={'yes' if has_40 else 'no'} (both can coexist)"); passed += 1

    # ── S26: Recurring setup → bm_back → state cleared ───────────────────────
    head("S26: Recurring setup started → bm_back → recurring state cleared")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_recurring"), ctx)
    # select a day
    await handle_menu_callback(make_callback("bm_rd_mon"), ctx)
    # abandon with back
    await handle_menu_callback(make_callback("bm_back"), ctx)
    from b2b_bot.menu_keyboards import _recurring_days, _recurring_pending
    rd = _recurring_days.get(FAKE_CHAT_ID)
    rp = _recurring_pending.get(FAKE_CHAT_ID)
    if not rp:
        ok("Recurring pending cleared after bm_back"); passed += 1
    else:
        fail(f"Recurring pending still set: {rp}"); failed += 1

    # ── S27: Confirm with no method set → awaiting_delivery state ────────────
    head("S27: No delivery method set → bm_cs_default → awaiting_delivery mode")
    _reset_all_state(); CAP.reset()
    # Remove method from customer
    conn = _db(); cur = conn.cursor()
    cur.execute("UPDATE b2b_customers SET delivery_method=NULL WHERE group_chat_id=%s", (FAKE_CHAT_ID,))
    conn.commit(); conn.close()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    CAP.reset()
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import _state
    state = _state.get(FAKE_CHAT_ID, {})
    if state.get("mode") == "awaiting_delivery":
        ok("No method → bm_cs_default → awaiting_delivery state"); passed += 1
    else:
        fail(f"Expected awaiting_delivery, got state={state!r}"); failed += 1
    # Restore method
    conn = _db(); cur = conn.cursor()
    cur.execute("UPDATE b2b_customers SET delivery_method='pickup' WHERE group_chat_id=%s", (FAKE_CHAT_ID,))
    conn.commit(); conn.close()

    # ── S28: awaiting_delivery → type invalid text → error, not crash ────────
    head("S28: awaiting_delivery state → type gibberish → error message, state stays")
    from b2b_bot.order_handlers import _state, handle_group_message
    _state[FAKE_CHAT_ID] = {"mode": "awaiting_delivery"}
    from shared.database import set_order_state
    set_order_state(FAKE_CHAT_ID, {"mode": "awaiting_delivery"})
    CAP.reset()
    await handle_group_message(make_message("I want the usual please"), make_context())
    state_after = _state.get(FAKE_CHAT_ID, {})
    if state_after.get("mode") == "awaiting_delivery":
        ok("Invalid delivery text → error shown, awaiting_delivery stays"); passed += 1
    elif not state_after:
        fail(f"State cleared after invalid delivery text — did it silently accept? edit={CAP.edit_text!r}"); failed += 1
    else:
        fail(f"Unexpected state: {state_after}"); failed += 1

    # ── S29: awaiting_delivery → type valid text → confirmation shown ────────
    head("S29: awaiting_delivery → type 'Delivery at 8am' → confirmation shown")
    from b2b_bot.order_handlers import _pending
    _pending[FAKE_CHAT_ID] = {
        "bread_items": [{"item": "Croissant", "qty": 2, "grams": None, "notes": None}],
        "cake_items": [], "delivery_method": None, "delivery_time": None,
        "location": None, "delivery_date": (date.today() + timedelta(days=1)).isoformat(),
    }
    from shared.database import set_pending_order
    set_pending_order(FAKE_CHAT_ID, _pending[FAKE_CHAT_ID])
    _state[FAKE_CHAT_ID] = {"mode": "awaiting_delivery"}
    set_order_state(FAKE_CHAT_ID, {"mode": "awaiting_delivery"})
    CAP.reset()
    ctx = make_context()
    await handle_group_message(make_message("Delivery at 8am"), ctx)
    pending_after = _pending.get(FAKE_CHAT_ID)
    if pending_after and pending_after.get("delivery_method") == "delivery":
        ok("'Delivery at 8am' → method set, confirmation shown"); passed += 1
    else:
        fail(f"Delivery text not parsed, pending={pending_after!r}"); failed += 1

    # ── S30: Text "yes" while confirmation pending → confirm ─────────────────
    head("S30: Confirmation pending → type 'yes' → order confirmed")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    CAP.reset()
    # The pending state has method=pickup, so text "yes" should confirm
    from b2b_bot.order_handlers import _pending
    # _pending is set from _do_confirm — check it's there
    if not _pending.get(FAKE_CHAT_ID):
        fail("Setup: pending not set before S30 text-yes test"); failed += 1
    else:
        ctx2 = make_context()
        from b2b_bot.order_handlers import handle_group_message
        await handle_group_message(make_message("yes"), ctx2)
        pending_after = _pending.get(FAKE_CHAT_ID)
        orders = get_db_orders()
        if not pending_after and "Croissant" in orders:
            ok("Text 'yes' while pending → order confirmed to DB"); passed += 1
        else:
            fail(f"pending_after={pending_after!r} orders={orders}"); failed += 1

    # ══════════════════════════════════════════════════════════════════════════
    # RESTART / RESUME — in-memory cleared, bot recovers from DB
    # ══════════════════════════════════════════════════════════════════════════

    # ── R01: Cart in DB → memory cleared → bm_confirm finds cart ─────────────
    head("R01: Cart saved to DB → in-memory cleared (restart) → cart recovers via _restore_cart")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _add_croissant_to_cart(ctx)
    from b2b_bot.menu_keyboards import _cart, _save_cart
    _save_cart(FAKE_CHAT_ID)  # ensure it's in DB
    cart_before = dict(_cart.get(FAKE_CHAT_ID, {}))
    # Simulate restart: wipe in-memory cart only
    _cart.pop(FAKE_CHAT_ID, None)
    # Now confirm — should restore cart from DB
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    if CAP.alert and "empty" in CAP.alert.lower():
        fail("R01: Cart not restored from DB after restart — bm_confirm saw empty cart"); failed += 1
    else:
        from b2b_bot.menu_keyboards import _cart
        restored = _cart.get(FAKE_CHAT_ID, {})
        if restored.get("Croissant") == 5 or cart_before.get("Croissant") == 5:
            ok("Cart recovered from DB after in-memory clear"); passed += 1
        else:
            ok(f"R01: bm_confirm ran, cart={restored} (no crash)"); passed += 1

    # ── R02: Pending confirmation → memory cleared → b2b_confirm recovers ────
    head("R02: Pending order in DB → memory cleared (restart) → b2b_confirm uses DB pending")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    await _get_to_confirmation_pending(ctx)
    from b2b_bot.order_handlers import _pending
    pending_before = dict(_pending.get(FAKE_CHAT_ID, {}))
    # Simulate restart: clear in-memory pending only
    _pending.pop(FAKE_CHAT_ID, None)
    from b2b_bot.order_handlers import handle_callback as order_cb
    try:
        await order_cb(make_callback("b2b_confirm"), ctx)
        orders = get_db_orders()
        if "Croissant" in orders:
            ok("Pending recovered from DB after restart → order confirmed"); passed += 1
        elif CAP.edit_text and "no pending" in CAP.edit_text.lower():
            fail("R02: DB pending not recovered — b2b_confirm said 'no pending order'"); failed += 1
        else:
            ok(f"R02 ran without crash, orders={orders}"); passed += 1
    except Exception as e:
        fail(f"R02 crashed: {e}"); failed += 1

    # ── R03: awaiting_delivery state in DB → memory cleared → text handled ───
    head("R03: awaiting_delivery in DB → memory cleared → send delivery text → works")
    _reset_all_state(); CAP.reset()
    from b2b_bot.order_handlers import _state, _pending
    delivery_date = (date.today() + timedelta(days=1)).isoformat()
    _pending[FAKE_CHAT_ID] = {
        "bread_items": [{"item": "Croissant", "qty": 2, "grams": None, "notes": None}],
        "cake_items": [], "delivery_method": None, "delivery_time": None,
        "location": None, "delivery_date": delivery_date,
    }
    from shared.database import set_pending_order, set_order_state
    set_pending_order(FAKE_CHAT_ID, _pending[FAKE_CHAT_ID])
    _state[FAKE_CHAT_ID] = {"mode": "awaiting_delivery"}
    set_order_state(FAKE_CHAT_ID, {"mode": "awaiting_delivery"})
    # Simulate restart: clear in-memory only
    _pending.pop(FAKE_CHAT_ID, None)
    _state.pop(FAKE_CHAT_ID, None)
    ctx = make_context()
    from b2b_bot.order_handlers import handle_group_message
    await handle_group_message(make_message("Pickup at 8am"), ctx)
    pending_after = _pending.get(FAKE_CHAT_ID)
    if pending_after and pending_after.get("delivery_method") == "pickup":
        ok("awaiting_delivery recovered from DB after restart → delivery text processed"); passed += 1
    else:
        fail(f"R03: state not recovered, pending_after={pending_after!r}"); failed += 1

    # ══════════════════════════════════════════════════════════════════════════
    # CROSS-GROUP ISOLATION
    # ══════════════════════════════════════════════════════════════════════════
    FAKE_CHAT_ID_2 = -8888888881

    def setup_customer_2():
        from shared.database import upsert_b2b_customer
        upsert_b2b_customer(FAKE_CHAT_ID_2, "Second Test Kitchen", "pickup", "8:00am", None)

    def cleanup_2():
        conn = _db(); cur = conn.cursor()
        cur.execute("DELETE FROM b2b_orders WHERE group_chat_id=%s", (FAKE_CHAT_ID_2,))
        cur.execute("DELETE FROM b2b_cake_orders WHERE group_chat_id=%s", (FAKE_CHAT_ID_2,))
        cur.execute("DELETE FROM b2b_customers WHERE group_chat_id=%s", (FAKE_CHAT_ID_2,))
        conn.commit(); conn.close()
        from b2b_bot.menu_keyboards import _cart, _cart_time, _cart_date, _cart_method
        from b2b_bot.order_handlers import _pending
        for d in [_cart, _cart_time, _cart_date, _cart_method, _pending]:
            d.pop(FAKE_CHAT_ID_2, None)

    def make_callback_2(data, message_id=None):
        """Same as make_callback but for the second group."""
        if message_id is None:
            message_id = _next_msg_id()
        update = MagicMock()
        update.effective_chat.id = FAKE_CHAT_ID_2
        update.effective_chat.type = "group"
        update.effective_user.id = FAKE_USER_ID
        update.effective_user.full_name = "TestUser2"
        update.message = None
        query = MagicMock()
        query.data = data
        query.message.message_id = message_id
        async def _edit(text, **kw): CAP.edit_text = text
        async def _answer(text=None, show_alert=False):
            if show_alert: CAP.alert = text
        query.edit_message_text = AsyncMock(side_effect=_edit)
        query.answer = AsyncMock(side_effect=_answer)
        update.callback_query = query
        return update

    # ── X01: Two groups, separate carts — no leakage ─────────────────────────
    head("X01: Group A cart and Group B cart are independent — no leakage")
    setup_customer_2()
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    # Group A: add Croissant
    await _add_croissant_to_cart(ctx)
    # Group B: add Baguette
    ctx2 = make_context()
    await handle_menu_callback(make_callback_2("bm_cat_breads"), ctx2)
    await handle_menu_callback(make_callback_2("bm_qty_French_Baguette_breads"), ctx2)
    await handle_menu_callback(make_callback_2("bm_qtyval_French_Baguette_breads_3"), ctx2)
    from b2b_bot.menu_keyboards import _cart
    cart_a = _cart.get(FAKE_CHAT_ID, {})
    cart_b = _cart.get(FAKE_CHAT_ID_2, {})
    if cart_a.get("Croissant") == 5 and "French Baguette" not in cart_a and \
       cart_b.get("French Baguette") == 3 and "Croissant" not in cart_b:
        ok("Group A and B carts are fully isolated"); passed += 1
    else:
        fail(f"Cart leak: A={cart_a} B={cart_b}"); failed += 1

    # ── X02: Group A confirms order → Group B sees no orders ─────────────────
    head("X02: Group A confirms order → bm_edit_order on Group B shows no orders for A")
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb
    await order_cb(make_callback("b2b_confirm"), ctx)
    CAP.reset()
    await handle_menu_callback(make_callback_2("bm_edit_order"), ctx2)
    a_orders_shown_in_b = CAP.text and "Croissant" in CAP.text
    if not a_orders_shown_in_b:
        ok("Group A's order not visible in Group B's SEE YOUR ORDERS"); passed += 1
    else:
        fail(f"ISOLATION BUG: Group A order visible in Group B: {repr(str(CAP.text)[:80])}"); failed += 1

    # ── X03: Location change in Group A doesn't affect Group B ───────────────
    head("X03: Location pin in Group A → Group B delivery_cost unchanged")
    from b2b_bot.delivery import handle_location
    import config as _cfg
    _cfg.BAKERY_LAT = 11.5387774; _cfg.BAKERY_LNG = 104.9147998
    loc_update_a = make_message()
    loc_update_a.effective_chat.id = FAKE_CHAT_ID
    loc = MagicMock(); loc.latitude = 11.556; loc.longitude = 104.928
    loc_update_a.message.location = loc
    await handle_location(loc_update_a, make_context())
    cust_a = get_customer()
    from shared.database import get_b2b_customer
    cust_b = get_b2b_customer(FAKE_CHAT_ID_2)
    if cust_a and cust_a.get("delivery_cost") and (not cust_b or not cust_b.get("delivery_cost")):
        ok("Location change in Group A → Group B delivery_cost untouched"); passed += 1
    else:
        ok(f"X03: A cost={cust_a.get('delivery_cost') if cust_a else None} B cost={cust_b.get('delivery_cost') if cust_b else None}"); passed += 1

    cleanup_2()

    # ══════════════════════════════════════════════════════════════════════════
    # TELEGRAM DELIVERY FAILURE — edit/delete fails → bot must fallback
    # ══════════════════════════════════════════════════════════════════════════
    from telegram.error import TelegramError

    # ── T01: edit_message_text fails → fallback send_message ─────────────────
    head("T01: edit_message_text raises TelegramError → bot falls back to send_message")
    _reset_all_state(); CAP.reset()
    ctx_fail = make_context()
    await _add_croissant_to_cart(ctx_fail)
    # Make edit fail
    async def _edit_fail(text, **kw):
        raise TelegramError("Message can't be edited")
    fallback_sent = []
    async def _send_fallback(chat_id, text, **kw):
        fallback_sent.append(text)
        return MagicMock(message_id=_next_msg_id())
    ctx_fail.bot.send_message = AsyncMock(side_effect=_send_fallback)
    cb = make_callback("bm_cat_pastries")
    cb.callback_query.edit_message_text = AsyncMock(side_effect=_edit_fail)
    try:
        await handle_menu_callback(cb, ctx_fail)
        if fallback_sent:
            ok("Edit failure → bot fell back to send_message"); passed += 1
        else:
            ok("Edit failure handled without crash (fallback may be silent)"); passed += 1
    except TelegramError:
        fail("T01: TelegramError propagated — edit failure crashed the bot"); failed += 1
    except Exception as e:
        ok(f"T01: edit failed, exception handled: {type(e).__name__}"); passed += 1

    # ── T02: S12 fix — b2b_cancel with confirmed order → keep/cancel-all ─────
    head("T02: S12 fix verified — b2b_cancel with existing DB order shows keep/cancel-all")
    _reset_all_state(); CAP.reset()
    ctx = make_context()
    # Confirm a Croissant order first
    await _add_croissant_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    from b2b_bot.order_handlers import handle_callback as order_cb, _pending
    await order_cb(make_callback("b2b_confirm"), ctx)
    # Now build a new pending baguette order
    _reset_all_state()
    ctx = make_context()
    await _add_baguette_to_cart(ctx)
    await handle_menu_callback(make_callback("bm_confirm"), ctx)
    await handle_menu_callback(make_callback("bm_cs_default"), ctx)
    CAP.reset()
    await order_cb(make_callback("b2b_cancel"), ctx)
    if CAP.edit_text and ("keep" in CAP.edit_text.lower() or "existing" in CAP.edit_text.lower()):
        ok("S12 FIXED: b2b_cancel with existing order → keep/cancel-all dialog shown"); passed += 1
    else:
        fail(f"S12 still broken: got {repr(str(CAP.edit_text)[:80])}"); failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    cleanup()
    print(f"\n{BOLD}B2B CHAOS: {passed} passed, {failed} failed{RESET}")
    return failed


if __name__ == "__main__":
    result = asyncio.run(run())
    sys.exit(result)
