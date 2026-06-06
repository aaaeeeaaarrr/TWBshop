"""Staff and owner commands: /markpaid, /balance, /history, /addaccount, /removeaccount, /commands."""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import filters as _filters

import config
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.billing import (
    apply_payment, get_effective_balance,
    format_balance_for_group, _unpaid_by_date,
)
from shared.database import (
    get_b2b_customer, get_b2b_customer_credit,
    get_groups_with_unpaid_orders,
    save_b2b_payment,
    get_valid_payment_accounts, get_all_payment_accounts,
    upsert_payment_account, remove_payment_account,
    get_b2b_payment_history, get_all_payment_history,
    get_all_b2b_customers,
    save_markpaid_request, get_markpaid_request,
    set_markpaid_amount, set_markpaid_method,
    set_markpaid_staff_msg, set_markpaid_owner_msg,
    set_markpaid_status,
)

logger = logging.getLogger(__name__)

_STAFF_ID = config.DISPATCH_REMINDER_TELEGRAM_ID
_OWNER_ID = config.OWNER_TELEGRAM_ID

# ── In-memory state ────────────────────────────────────────────────────────────
_markpaid_custom_pending: dict[int, int] = {}   # user_id → request_id
_addaccount_state: dict[int, dict] = {}         # user_id → {"type": "bank"|"seller"}


def _is_owner(uid: int) -> bool:
    return uid == _OWNER_ID

def _is_authorized(uid: int) -> bool:
    return uid in (_OWNER_ID, _STAFF_ID)

def _fmt_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d")
    except Exception:
        return iso

def _method_label(m: str) -> str:
    return {"cash": "Cash", "bank": "Bank Transfer", "photo": "Screenshot"}.get(m, m)


def _status_prefix(s: str | None) -> str:
    return {"applied": "✅ ", "pending": "⏳ ", "rejected": "❌ "}.get(s or "", "✅ ")


# ── /balance ──────────────────────────────────────────────────────────────────

async def cmd_balance_enhanced(update: Update, context) -> None:
    chat = update.effective_chat
    uid = update.effective_user.id
    if chat.type in ("group", "supergroup"):
        if not is_b2b_group(chat.id):
            return
        business = get_business_name(chat.id)
        await update.message.reply_text(
            format_balance_for_group(chat.id, business), parse_mode=ParseMode.HTML
        )
    else:
        if not _is_authorized(uid):
            return
        await _reply_all_balances(update.message.reply_text)


async def _reply_all_balances(send_fn) -> None:
    groups = get_groups_with_unpaid_orders()
    lines = ["<b>Outstanding Balances</b>", ""]
    found = False
    for row in groups:
        eff = get_effective_balance(row["group_chat_id"])
        if eff > 0:
            lines.append(f"• {row['business_name']}: <b>${eff:.2f}</b>")
            found = True
    if not found:
        await send_fn("✅ All B2B accounts are paid up.")
    else:
        await send_fn("\n".join(lines), parse_mode=ParseMode.HTML)


async def callback_balance(update: Update, context) -> None:
    """Check Balance button pressed inside a customer group."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return
    business = get_business_name(chat_id)
    await context.bot.send_message(
        chat_id, format_balance_for_group(chat_id, business), parse_mode=ParseMode.HTML
    )


# ── /markpaid ─────────────────────────────────────────────────────────────────

async def cmd_markpaid(update: Update, context) -> None:
    uid = update.effective_user.id
    if not _is_authorized(uid):
        return
    if update.effective_chat.type in ("group", "supergroup"):
        return
    groups = get_groups_with_unpaid_orders()
    rows = []
    for row in groups:
        eff = get_effective_balance(row["group_chat_id"])
        if eff > 0:
            rows.append([InlineKeyboardButton(
                f"{row['business_name']} — ${eff:.2f}",
                callback_data=f"bmp_pick_{row['group_chat_id']}",
            )])
    if not rows:
        await update.message.reply_text("✅ No outstanding balances.")
        return
    await update.message.reply_text("Which customer?", reply_markup=InlineKeyboardMarkup(rows))


async def _start_markpaid(bot, uid: int, group_chat_id: int) -> None:
    business = get_business_name(group_chat_id)
    by_date = _unpaid_by_date(group_chat_id)
    credit = get_b2b_customer_credit(group_chat_id)
    eff = get_effective_balance(group_chat_id)

    if eff <= 0:
        try:
            await bot.send_message(uid, f"✅ {business} has no outstanding balance.")
        except Exception:
            pass
        return

    req_id = save_markpaid_request(group_chat_id, business, uid)

    rows = [[InlineKeyboardButton("CUSTOM AMOUNT", callback_data=f"bmp_custom_{req_id}")]]
    remaining_credit = credit
    for d in sorted(by_date.keys()):
        total = by_date[d]["total"]
        if remaining_credit >= total:
            remaining_credit = round(remaining_credit - total, 2)
            label = f"{_fmt_date(d)} — ${total:.2f} (credit covers)"
        elif remaining_credit > 0:
            owed = round(total - remaining_credit, 2)
            remaining_credit = 0.0
            label = f"{_fmt_date(d)} — ${owed:.2f} remaining"
        else:
            label = f"{_fmt_date(d)} — ${total:.2f}"
        bill_count = len(by_date[d].get("batch_ids") or set())
        if bill_count > 1:
            label += f" ({bill_count} bills)"
        rows.append([InlineKeyboardButton(label, callback_data=f"bmp_date_{req_id}_{d}")])

    rows.append([InlineKeyboardButton(f"Full balance — ${eff:.2f}", callback_data=f"bmp_full_{req_id}")])

    try:
        await bot.send_message(
            uid,
            f"💰 Mark payment for <b>{business}</b>\nOutstanding: <b>${eff:.2f}</b>\n\nHow much was paid?",
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error("Failed to DM for markpaid: %s", e)


async def callback_markpaid_pick(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    group_chat_id = int(query.data.split("_")[2])
    await query.delete_message()
    await _start_markpaid(context.bot, update.effective_user.id, group_chat_id)


async def callback_markpaid_date(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")   # bmp_date_REQID_DATE
    req_id = int(parts[2])
    date_str = parts[3]

    req = get_markpaid_request(req_id)
    if not req:
        await query.edit_message_text("Request expired. Start again with /markpaid.")
        return

    by_date = _unpaid_by_date(req["group_chat_id"])
    credit = get_b2b_customer_credit(req["group_chat_id"])
    remaining_credit = credit
    for d in sorted(by_date.keys()):
        if d == date_str:
            break
        remaining_credit = round(max(0.0, remaining_credit - by_date[d]["total"]), 2)

    day = by_date.get(date_str)
    if not day:
        await query.edit_message_text("Date not found.")
        return

    amount = round(max(0.0, day["total"] - remaining_credit), 2)
    set_markpaid_amount(req_id, amount)
    await _ask_method(query, req_id, req["business_name"], amount, _fmt_date(date_str))


async def callback_markpaid_full(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[2])
    req = get_markpaid_request(req_id)
    if not req:
        await query.edit_message_text("Request expired.")
        return
    amount = get_effective_balance(req["group_chat_id"])
    set_markpaid_amount(req_id, amount)
    await _ask_method(query, req_id, req["business_name"], amount, "full balance")


async def callback_markpaid_custom(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split("_")[2])
    req = get_markpaid_request(req_id)
    if not req:
        await query.edit_message_text("Request expired.")
        return
    _markpaid_custom_pending[update.effective_user.id] = req_id
    await query.edit_message_text(
        f"💰 <b>{req['business_name']}</b>\n\nType the amount paid (e.g. <code>15.50</code>):",
        parse_mode=ParseMode.HTML,
    )


async def _ask_method(query, req_id: int, business: str, amount: float, label: str) -> None:
    await query.edit_message_text(
        f"💰 <b>{business}</b> — ${amount:.2f} ({label})\n\nPayment method?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💵 Cash", callback_data=f"bmp_cash_{req_id}"),
            InlineKeyboardButton("🏦 Bank Transfer", callback_data=f"bmp_bank_{req_id}"),
        ]]),
        parse_mode=ParseMode.HTML,
    )


async def callback_markpaid_method(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")   # bmp_cash_REQID or bmp_bank_REQID
    method_key = parts[1]
    req_id = int(parts[2])
    method = "cash" if method_key == "cash" else "bank"

    req = get_markpaid_request(req_id)
    if not req or req.get("amount") is None:
        await query.edit_message_text("Request expired or amount missing. Start again.")
        return

    amount = float(req["amount"])
    set_markpaid_method(req_id, method)

    details = (
        f"Customer: <b>{req['business_name']}</b>\n"
        f"Amount: <b>${amount:.2f}</b>\n"
        f"Method: {_method_label(method)}"
    )

    # Edit staff message → "Awaiting owner approval"
    staff_text = f"⏳ Awaiting owner approval\n\n{details}"
    await query.edit_message_text(staff_text, parse_mode=ParseMode.HTML)
    set_markpaid_staff_msg(req_id, query.message.message_id)

    # If owner is doing it themselves — apply directly
    if update.effective_user.id == _OWNER_ID:
        await _do_confirm(context.bot, req_id)
        return

    # Send owner verification
    if _OWNER_ID:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirm", callback_data=f"bmp_confirm_{req_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"bmp_reject_{req_id}"),
        ]])
        try:
            msg = await context.bot.send_message(
                _OWNER_ID, f"💰 Payment entry by staff\n\n{details}",
                reply_markup=kb, parse_mode=ParseMode.HTML,
            )
            set_markpaid_owner_msg(req_id, msg.message_id)
        except Exception as e:
            logger.error("Failed to send owner markpaid: %s", e)


async def callback_markpaid_confirm(update: Update, context) -> None:
    query = update.callback_query
    if update.effective_user.id != _OWNER_ID:
        await query.answer("Not authorised.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[2])
    await _do_confirm(context.bot, req_id)


async def _do_confirm(bot, req_id: int) -> None:
    req = get_markpaid_request(req_id)
    if not req or req["status"] not in ("draft", "pending"):
        return

    amount = float(req["amount"])
    result = apply_payment(req["group_chat_id"], amount)
    covered = ",".join(result.get("paid_dates", []))

    save_b2b_payment(
        req["group_chat_id"], req["business_name"], amount,
        None, method=req["method"], covered_dates=covered,
    )
    set_markpaid_status(req_id, "approved", covered_dates=covered)

    eff = get_effective_balance(req["group_chat_id"])
    details = (
        f"Customer: <b>{req['business_name']}</b>\n"
        f"Amount: <b>${amount:.2f}</b>\n"
        f"Method: {_method_label(req['method'])}\n"
        f"<b>Remaining balance: ${eff:.2f}</b>"
    )

    # Group notification
    try:
        await bot.send_message(
            req["group_chat_id"],
            f"✓ Payment recorded — ${amount:.2f} · {_method_label(req['method'])}\n"
            f"<b>Remaining balance: ${eff:.2f}</b>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error("Group markpaid notification failed: %s", e)

    # Edit owner message
    if req.get("owner_msg_id") and _OWNER_ID:
        try:
            await bot.edit_message_text(
                f"✅ Confirmed\n\n{details}", chat_id=_OWNER_ID,
                message_id=req["owner_msg_id"], parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    # Edit staff message
    if req.get("staff_msg_id") and _STAFF_ID and req["staff_user_id"] != _OWNER_ID:
        try:
            await bot.edit_message_text(
                f"✅ Approved by owner\n\n{details}", chat_id=_STAFF_ID,
                message_id=req["staff_msg_id"], parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def callback_markpaid_reject(update: Update, context) -> None:
    query = update.callback_query
    if update.effective_user.id != _OWNER_ID:
        await query.answer("Not authorised.", show_alert=True)
        return
    await query.answer()
    req_id = int(query.data.split("_")[2])
    req = get_markpaid_request(req_id)
    if not req or req["status"] != "pending":
        return

    set_markpaid_status(req_id, "rejected")
    amount = float(req["amount"])
    details = (
        f"Customer: <b>{req['business_name']}</b>\n"
        f"Amount: <b>${amount:.2f}</b>\n"
        f"Method: {_method_label(req['method'])}"
    )

    await query.edit_message_text(f"❌ Rejected\n\n{details}", parse_mode=ParseMode.HTML)

    if req.get("staff_msg_id") and _STAFF_ID:
        try:
            await context.bot.edit_message_text(
                f"❌ Rejected by owner\n\n{details}", chat_id=_STAFF_ID,
                message_id=req["staff_msg_id"], parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


async def handle_custom_amount_text(update: Update, context) -> bool:
    """Returns True if the message was consumed as a custom markpaid amount."""
    uid = update.effective_user.id
    if uid not in _markpaid_custom_pending:
        return False
    req_id = _markpaid_custom_pending.pop(uid)
    text = (update.message.text or "").strip().replace("$", "").replace(",", "")
    try:
        amount = round(float(text), 2)
        if amount <= 0:
            raise ValueError
    except ValueError:
        _markpaid_custom_pending[uid] = req_id
        await update.message.reply_text("Please type a valid amount (e.g. 15.50):")
        return True

    req = get_markpaid_request(req_id)
    if not req:
        await update.message.reply_text("Request expired. Start again with /markpaid.")
        return True

    set_markpaid_amount(req_id, amount)
    await update.message.reply_text(
        f"💰 <b>{req['business_name']}</b> — ${amount:.2f}\n\nPayment method?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💵 Cash", callback_data=f"bmp_cash_{req_id}"),
            InlineKeyboardButton("🏦 Bank Transfer", callback_data=f"bmp_bank_{req_id}"),
        ]]),
        parse_mode=ParseMode.HTML,
    )
    return True


# ── /addaccount & /removeaccount (owner only) ─────────────────────────────────

async def cmd_addaccount(update: Update, context) -> None:
    if not _is_owner(update.effective_user.id):
        return
    if update.effective_chat.type != "private":
        await update.message.reply_text("Use this command in private chat with me.")
        return
    await update.message.reply_text(
        "What type of account?",
        # long label gets its own row — truncates side by side (session 28 rule)
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏦 Bank account number", callback_data="bmc_acct_bank")],
            [InlineKeyboardButton("🏪 Seller name", callback_data="bmc_acct_seller")],
        ]),
    )


async def callback_acct_type(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_owner(update.effective_user.id):
        return
    acct_type = query.data.split("_")[2]   # bank or seller
    _addaccount_state[update.effective_user.id] = {"type": acct_type}
    label = "account number" if acct_type == "bank" else "seller name"
    await query.edit_message_text(f"Type the {label} to add:")


async def cmd_removeaccount(update: Update, context) -> None:
    if not _is_owner(update.effective_user.id):
        return
    if update.effective_chat.type != "private":
        await update.message.reply_text("Use this command in private chat with me.")
        return
    accounts = get_all_payment_accounts()
    if not accounts:
        await update.message.reply_text("No accounts stored.")
        return
    rows = []
    for acct in accounts:
        icon = "🏦" if acct["type"] == "bank" else "🏪"
        rows.append([InlineKeyboardButton(
            f"{icon} {acct['value']}",
            callback_data=f"bmc_rm_{acct['id']}",
        )])
    await update.message.reply_text("Tap to remove:", reply_markup=InlineKeyboardMarkup(rows))


async def callback_remove_account(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_owner(update.effective_user.id):
        return
    account_id = int(query.data.split("_")[2])
    remove_payment_account(account_id)
    await query.edit_message_text("✅ Account removed.")


async def handle_addaccount_text(update: Update, context) -> bool:
    """Returns True if the message was consumed as an account value input."""
    uid = update.effective_user.id
    if uid not in _addaccount_state:
        return False
    state = _addaccount_state.pop(uid)
    value = (update.message.text or "").strip()
    if not value:
        return False
    upsert_payment_account(state["type"], value)
    label = "Bank account" if state["type"] == "bank" else "Seller name"
    await update.message.reply_text(f"✅ {label} added: <code>{value}</code>", parse_mode=ParseMode.HTML)
    return True


# ── /history ──────────────────────────────────────────────────────────────────

async def cmd_history(update: Update, context) -> None:
    uid = update.effective_user.id
    chat = update.effective_chat
    if not _is_authorized(uid):
        return

    if chat.type in ("group", "supergroup") and is_b2b_group(chat.id):
        await _send_history(update.message.reply_text, chat.id)
        return

    if chat.type != "private":
        return

    customers = get_all_b2b_customers()
    rows = [[InlineKeyboardButton("📋 All Customers", callback_data="bmh_all")]]
    for c in customers:
        rows.append([InlineKeyboardButton(c["business_name"], callback_data=f"bmh_{c['group_chat_id']}")])
    await update.message.reply_text("Payment history for:", reply_markup=InlineKeyboardMarkup(rows))


async def callback_history(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_authorized(update.effective_user.id):
        return
    key = query.data[4:]   # strip "bmh_"
    if key == "all":
        rows = get_all_payment_history()
        if not rows:
            await query.edit_message_text("No payment history yet.")
            return
        lines = ["<b>All Payment History</b>"]
        lines += _month_grouped_lines(rows, show_business=True)
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)
    else:
        group_chat_id = int(key)
        await _send_history(query.edit_message_text, group_chat_id)


async def _send_history(send_fn, group_chat_id: int) -> None:
    business = get_business_name(group_chat_id)
    rows = get_b2b_payment_history(group_chat_id)
    if not rows:
        await send_fn(f"No payment history for <b>{business}</b>.", parse_mode=ParseMode.HTML)
        return
    lines = [f"<b>Payment History — {business}</b>"]
    lines += _month_grouped_lines(rows, show_business=False)
    await send_fn("\n".join(lines), parse_mode=ParseMode.HTML)


def _month_grouped_lines(rows: list[dict], show_business: bool) -> list[str]:
    from collections import defaultdict
    by_month: dict[str, list] = defaultdict(list)
    for r in rows:
        month = (r.get("created_at") or "")[:7]   # "YYYY-MM"
        by_month[month].append(r)
    lines = []
    for month in sorted(by_month.keys(), reverse=True):
        month_rows = by_month[month]
        month_total = sum(float(r["amount"]) for r in month_rows)
        year, mon = month.split("-")
        month_name = datetime(int(year), int(mon), 1).strftime("%B").upper()
        lines.append(f"\n<b>{month_name} {year} (${month_total:.2f})</b>")
        for r in month_rows:
            lines.append(_format_payment_row(r, show_business=show_business))
    return lines


def _format_payment_row(r: dict, show_business: bool = False) -> str:
    dt = (r.get("created_at") or "")[5:10]   # MM-DD
    method = r.get("method") or "photo"
    status = r.get("status")
    biz = f"<i>{r['business_name']}</i> — " if show_business else ""
    line = f"{_status_prefix(status)}{dt} — {biz}<b>${float(r['amount']):.2f}</b> · {_method_label(method)}"
    if r.get("covered_dates"):
        dates = [_fmt_date(d) for d in r["covered_dates"].split(",") if d]
        if dates:
            line += f"\n   ✓ {', '.join(dates)}"
    return line


# ── /commands ─────────────────────────────────────────────────────────────────

async def cmd_commands(update: Update, context) -> None:
    uid = update.effective_user.id
    if _is_owner(uid):
        text = (
            "<b>Owner Commands</b>\n\n"
            "/balance — all customers' outstanding balances\n"
            "/markpaid — record a cash or bank payment\n"
            "/history — payment history by customer\n"
            "/addaccount — add a valid bank account or seller name\n"
            "/removeaccount — remove a stored account\n"
            "/summary — send B2B nightly summary now\n"
            "/commands — this list\n\n"
            "<i>In a customer group:</i>\n"
            "/balance — that customer's full balance breakdown"
        )
    elif uid == _STAFF_ID:
        text = (
            "<b>Staff Commands</b>\n\n"
            "/balance — all customers' outstanding balances\n"
            "/markpaid — record a cash or bank payment\n"
            "/history — payment history\n"
            "/commands — this list\n\n"
            "<i>In a customer group:</i>\n"
            "/balance — that customer's full balance breakdown"
        )
    else:
        return
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── Private text filter (for custom amount and addaccount flows) ───────────────

class _StaffFlowFilter(_filters.MessageFilter):
    def filter(self, message):
        uid = message.from_user.id if message.from_user else None
        return uid in _markpaid_custom_pending or uid in _addaccount_state

staff_flow_filter = _StaffFlowFilter()


async def handle_staff_flow_text(update: Update, context) -> None:
    """Handles private text messages when a staff flow is awaiting input."""
    if await handle_custom_amount_text(update, context):
        return
    await handle_addaccount_text(update, context)


async def handle_private_fallback(update: Update, context) -> None:
    """Catch-all for unrecognised private messages from owner/staff — show command list."""
    uid = update.effective_user.id if update.effective_user else None
    if _is_authorized(uid):
        await cmd_commands(update, context)
