"""Order intake, menu matching, and confirmation flow."""

import re
import difflib
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from menu import ALIAS_MAP, MENU
from database import save_order

logger = logging.getLogger(__name__)

# Pending orders awaiting confirmation: {user_id: parsed_order_dict}
_pending: dict[int, dict] = {}


def _parse_items(text: str) -> list[tuple[str, int]]:
    """Return list of (canonical_item, quantity) matched from raw text."""
    text = text.lower().strip()
    results = []

    # Tokenise on commas and "and"
    parts = re.split(r",|\band\b", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract leading number if present (e.g. "2 croissants")
        qty_match = re.match(r"^(\d+)\s+(.+)$", part)
        if qty_match:
            qty = int(qty_match.group(1))
            item_text = qty_match.group(2).strip()
        else:
            qty = 1
            item_text = part

        # Exact alias match first
        canonical = ALIAS_MAP.get(item_text)
        if not canonical:
            # Fuzzy fallback
            matches = difflib.get_close_matches(item_text, ALIAS_MAP.keys(), n=1, cutoff=0.7)
            if matches:
                canonical = ALIAS_MAP[matches[0]]
            else:
                logger.warning("UNMATCHED: %s", item_text)
                _log_unmatched(item_text)
                continue

        results.append((canonical, qty))

    return results


def _log_unmatched(text: str) -> None:
    import config
    import os
    os.makedirs("logs", exist_ok=True)
    with open(config.UNMATCHED_LOG, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def _format_order(items: list[tuple[str, int]]) -> str:
    return "\n".join(f"  • {qty}x {name}" for name, qty in items)


async def handle_order_text(update: Update, context) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    items = _parse_items(text)
    if not items:
        await update.message.reply_text(
            "Sorry, I couldn't match any menu items in your message. "
            "Please check our menu and try again."
        )
        return

    _pending[user_id] = {"items": items, "chat_id": update.effective_chat.id}

    summary = _format_order(items)
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="confirm"),
            InlineKeyboardButton("Edit", callback_data="edit"),
            InlineKeyboardButton("Cancel", callback_data="cancel"),
        ]
    ]
    await update.message.reply_text(
        f"Got it! Here's what I understood:\n\n{summary}\n\nIs this correct?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "confirm":
        order = _pending.pop(user_id, None)
        if order:
            save_order(user_id, order["items"])
            await query.edit_message_text("Your order has been saved. Thank you!")
        else:
            await query.edit_message_text("No pending order found. Please send your order again.")

    elif query.data == "edit":
        _pending.pop(user_id, None)
        await query.edit_message_text("No problem — please send your order again.")

    elif query.data == "cancel":
        _pending.pop(user_id, None)
        await query.edit_message_text("Order cancelled.")
