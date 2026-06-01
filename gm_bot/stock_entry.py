"""
Paperless /stock entry flow (TEST MODE — owner only for now).

/stock -> category buttons -> item buttons (showing unit + last count) -> type the
count -> stored. '+ Add new item' -> owner gets a private heads-up. Pre-fills the last
count so only changed items need touching.

NOT connected to staff yet: gated to the owner so it can be tested 1:1 with the bot
before opening it up (then swap _allowed to the staff registry + announce + points).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

import config
from shared.database import (
    stock_categories, stock_items_in_category, stock_get_item, stock_record_count,
    stock_add_pending,
)

logger = logging.getLogger(__name__)

CHOOSING_CAT, CHOOSING_ITEM, ENTER_COUNT, ADD_NEW = range(4)


def _allowed(uid: int) -> bool:
    # TEST MODE: owner only. Later: active staff via staff_get_by_uid(uid).
    return uid == config.OWNER_TELEGRAM_ID


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _category_kb() -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(c, callback_data="stk:cat:%s" % c)] for c in stock_categories()]
    kb.append([InlineKeyboardButton("➕ Add new item", callback_data="stk:new")])
    kb.append([InlineKeyboardButton("✅ Done", callback_data="stk:done")])
    return InlineKeyboardMarkup(kb)


def _items_kb(category: str) -> InlineKeyboardMarkup:
    kb = []
    for it in stock_items_in_category(category):
        last = it["last_count"]
        last_s = ("%g" % last) if last is not None else "–"
        label = "%s (%s) · last %s" % (it["item"], it["unit"] or "?", last_s)
        kb.append([InlineKeyboardButton(label, callback_data="stk:item:%d" % it["id"])])
    kb.append([InlineKeyboardButton("⬅️ Categories", callback_data="stk:back")])
    return InlineKeyboardMarkup(kb)


async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _allowed(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text("📋 Stock check — pick a category:", reply_markup=_category_kb())
    return CHOOSING_CAT


async def cb_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    cat = q.data.split(":", 2)[2]
    context.user_data["stk_cat"] = cat
    await q.edit_message_text("%s — tap an item to enter its count:" % cat, reply_markup=_items_kb(cat))
    return CHOOSING_ITEM


async def cb_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("📋 Stock check — pick a category:", reply_markup=_category_kb())
    return CHOOSING_CAT


async def cb_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split(":")[2])
    it = stock_get_item(item_id)
    if not it:
        await q.edit_message_text("Item not found."); return CHOOSING_ITEM
    context.user_data["stk_item_id"] = item_id
    await q.edit_message_text("Enter the current count for *%s* (%s):" % (it["item"], it["unit"] or "unit"),
                              parse_mode="Markdown")
    return ENTER_COUNT


async def enter_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.message.text or "").strip().replace(",", ".")
    item_id = context.user_data.get("stk_item_id")
    cat = context.user_data.get("stk_cat")
    try:
        count = float(raw)
    except ValueError:
        await update.message.reply_text("Please send just a number (e.g. 3 or 2.5).")
        return ENTER_COUNT
    it = stock_get_item(item_id)
    if it:
        stock_record_count(item_id, count, _today())
        await update.message.reply_text(
            "✓ %s = %g %s" % (it["item"], count, it["unit"] or ""),
            reply_markup=_items_kb(cat))
    return CHOOSING_ITEM


async def cb_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Type the name of the new item to add:")
    return ADD_NEW


async def add_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if name:
        user = update.effective_user
        stock_add_pending(name, user.full_name if user else None, user.id if user else None)
        # Private heads-up to the owner about the addition.
        try:
            await context.bot.send_message(
                chat_id=config.OWNER_TELEGRAM_ID,
                text="➕ New stock item proposed: \"%s\" (by %s). Set its unit + minimum when ready." % (
                    name, (user.full_name if user else "?")))
        except Exception as e:
            logger.error("new-item owner notify failed: %s", e)
        await update.message.reply_text("Noted \"%s\" — the owner will set its unit + minimum." % name,
                                        reply_markup=_category_kb())
    return CHOOSING_CAT


async def cb_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("✅ Stock check saved. Thank you!")
    context.user_data.pop("stk_cat", None)
    context.user_data.pop("stk_item_id", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Stock check cancelled.")
    return ConversationHandler.END


def build_stock_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("stock", cmd_stock)],
        states={
            CHOOSING_CAT: [
                CallbackQueryHandler(cb_category, pattern=r"^stk:cat:"),
                CallbackQueryHandler(cb_new, pattern=r"^stk:new$"),
                CallbackQueryHandler(cb_done, pattern=r"^stk:done$"),
            ],
            CHOOSING_ITEM: [
                CallbackQueryHandler(cb_item, pattern=r"^stk:item:"),
                CallbackQueryHandler(cb_back, pattern=r"^stk:back$"),
            ],
            ENTER_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_count)],
            ADD_NEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_new)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True, per_user=True,
    )
