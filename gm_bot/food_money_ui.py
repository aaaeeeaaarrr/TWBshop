"""Food Allowance — the listener's /menu button (live wiring), GATED so it's safe even when deployed.

Reachable ONLY when the feature is live (`gm_state 'food_money_live' = 'on'`) OR the attendance TEST MODE
is on (the owner's walk) — `_food_gate_on()`. OFF by default → a deploy can't expose it until the owner
flips it after walking it. `is_test` follows the attendance test switch (`att_test_on()`), so a walk never
touches real food data. Access = the shop/listener account + the owner, in a PRIVATE chat only.

This NEVER moves the drawer/report money — it only records who took meal cash (a separate list, shown on
the report). Thin glue over the tested core (`food_money.py` + `food_money_db.py`).
"""
import datetime as _dt
import logging
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from gm_bot.attendance_ui import shift_len_min
from gm_bot.food_money import food_menu_rows, food_money_cents, render_food_list
from gm_bot.food_money_db import (close_food_period, food_arrived_staff, food_money_open_ids,
                                  food_money_open_list, record_food_money_give)
from shared.database import att_test_on, gm_get_state

logger = logging.getLogger(__name__)
_PP = ZoneInfo("Asia/Phnom_Penh")
LISTENER_ID = config.DISPATCH_REMINDER_TELEGRAM_ID
# The menu lives in the Expenses TWB group so the owner OR the listener (both in it) can run /menu there.
# ⚠ The GM bot must be a MEMBER of this group, and able to see /menu (privacy off, or /menu@<gmbot>).
EXPENSE_GROUP_ID = -5417163768


def _food_gate_on() -> bool:
    """Reachable when it has gone live OR the attendance test mode is on (the owner's walk). Off otherwise."""
    return att_test_on() or (gm_get_state("food_money_live") == "on")


def _may_use(update) -> bool:
    """The Food Allowance menu = the Expenses TWB group, owner or listener only (not other members)."""
    chat, user = update.effective_chat, update.effective_user
    if chat is None or user is None:
        return False
    return chat.id == EXPENSE_GROUP_ID and user.id in (config.OWNER_TELEGRAM_ID, LISTENER_ID)


def _shift_dates():
    """Today + yesterday (PP) — covers an overnight shift's check-in date."""
    today = _dt.datetime.now(_PP).date()
    return [today, today - _dt.timedelta(days=1)]


def _coming_report_hint() -> str:
    """Friendly prediction for the confirm message (assignment itself is event-driven, on report store)."""
    h = _dt.datetime.now(_PP).hour
    return "Day report (~4pm)" if 6 <= h < 16 else "Night report (~5am)"


def _kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for (t, d) in row] for row in rows])


def _food_list_kb():
    """(rows, keyboard) for the live Food Allowance list: one button per arrived-and-not-yet-given staff."""
    is_test = att_test_on()
    rows = food_menu_rows(food_arrived_staff(_shift_dates(), is_test=is_test), food_money_open_ids(is_test=is_test))
    btns = [[(f"{name} · ${c / 100:.2f}", f"food:give:{sid}")] for (sid, name, c) in rows]
    btns.append([("🔄 Refresh", "food:open"), ("✅ Done", "food:close")])
    return rows, _kb(btns)


async def food_menu_entry(update, context) -> bool:
    """/menu in the EXPENSES TWB group by the owner or listener → show the shop menu (1 button for now).
    Returns True if WE handled it — crucially, True for the owner here too, so the owner's salary menu can
    NEVER fall through and render in a group. Silent when the feature is gated off (no group spam)."""
    if not _may_use(update):
        return False                       # not the food-menu context → cmd_menu handles (owner private)
    if _food_gate_on():
        await update.message.reply_text("🗂 Menu", reply_markup=_kb([[("🍚 Food Allowance", "food:open")]]))
    return True                            # handled (shown if live; silent if off) — never falls through


async def on_food_callback(update, context) -> None:
    """food:* taps (listener/owner, private, gated). open = show list · give:<id> = record · close = summary."""
    q = update.callback_query
    await q.answer()
    if not _may_use(update) or not _food_gate_on():
        return
    parts = (q.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    if action == "open":
        rows, kb = _food_list_kb()
        head = ("🍚 Food Allowance — tap a staff member who is here to record their meal money:"
                if rows else "🍚 Food Allowance — nobody to record (none checked in yet, or all given).")
        await q.edit_message_text(head, reply_markup=kb)
    elif action == "give" and len(parts) > 2:
        try:
            sid = int(parts[2])
        except ValueError:
            return
        is_test = att_test_on()
        # recompute the amount server-side from the staff's STANDARD shift — never trust the button
        arrived = {a["staff_id"]: a for a in food_arrived_staff(_shift_dates(), is_test=is_test)}
        a = arrived.get(sid)
        if not a:
            await q.answer("Not checked in / already given.", show_alert=True)
            return
        cents = food_money_cents(shift_len_min(a.get("work_start"), a.get("work_end")))
        if cents <= 0:
            await q.answer("No standard shift on record for them.", show_alert=True)
            return
        newly = record_food_money_give(sid, a.get("name"), cents,
                                       given_by=update.effective_user.id, is_test=is_test)
        note = (f"✅ {a.get('name')} · ${cents / 100:.2f} — on the coming {_coming_report_hint()}."
                if newly else f"{a.get('name')} was already recorded.")
        _, kb = _food_list_kb()                       # refresh → the given name disappears
        await q.edit_message_text("🍚 Food Allowance — " + note + "\nTap another, or ✅ Done.", reply_markup=kb)
    elif action == "close":
        lst = food_money_open_list(is_test=att_test_on())
        total = sum(c for _, c in lst)
        await q.edit_message_text(f"🍚 Recorded so far this period: {len(lst)} staff · ${total / 100:.2f}.\n"
                                  "They'll be listed automatically on the next report.")


async def post_food_list_on_report(bot, report_id, business_day_iso, report_kind) -> None:
    """Close hook: a daily report was stored → attach the open gives to it and post the 'Day/Night staff
    food' list to the listener. GATED + a no-op when the feature is off or there were no gives. Never raises
    into the report flow."""
    if not _food_gate_on():
        return
    try:
        biz = _dt.date.fromisoformat(business_day_iso) if isinstance(business_day_iso, str) else business_day_iso
        closed = close_food_period(report_id, biz, report_kind, is_test=att_test_on())
        if closed:
            await bot.send_message(EXPENSE_GROUP_ID, render_food_list(report_kind, biz, closed))
    except Exception:
        logger.exception("food list post on report failed")
