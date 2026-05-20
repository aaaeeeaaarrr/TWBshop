"""Order intake, menu matching, and confirmation flow."""

import re
import difflib
import logging
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from menu import ALIAS_MAP, menu_list_text
from database import save_order

logger = logging.getLogger(__name__)

# Pending orders awaiting confirmation: {user_id: parsed_order_dict}
_pending: dict[int, dict] = {}

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Noise phrases stripped before parsing
_NOISE = re.compile(
    r"^(i('d)?\s+(want|like|would\s+like)|can\s+i\s+(get|have|order)|"
    r"please\s+(give\s+me|send\s+me)?|i('ll\s+have)?|"
    r"i\s+need|give\s+me|order[:\s]+|id\s+like)\s*",
    re.IGNORECASE,
)


def _strip_noise(text: str) -> str:
    return _NOISE.sub("", text).strip()


def _parse_items(text: str) -> list[tuple[str, int]]:
    """Return list of (canonical_item, quantity) matched from raw text."""
    text = _strip_noise(text.lower().strip())
    totals: dict[str, int] = defaultdict(int)

    # Split on commas and "and" (but not "almond danish" etc.) — word boundary "and"
    parts = re.split(r",|\band\b", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract leading quantity: digit or word-number
        qty = 1
        qty_match = re.match(r"^(\d+)\s+(.+)$", part)
        if qty_match:
            qty = int(qty_match.group(1))
            item_text = qty_match.group(2).strip()
        else:
            word_match = re.match(
                r"^(" + "|".join(_WORD_NUMBERS.keys()) + r")\s+(.+)$", part
            )
            if word_match:
                qty = _WORD_NUMBERS[word_match.group(1)]
                item_text = word_match.group(2).strip()
            else:
                item_text = part

        # Strip trailing plural 's' only when it doesn't break an alias
        # (try with 's' first, then without)
        canonical = ALIAS_MAP.get(item_text)
        if not canonical and item_text.endswith("s"):
            canonical = ALIAS_MAP.get(item_text[:-1])

        if not canonical:
            matches = difflib.get_close_matches(item_text, ALIAS_MAP.keys(), n=1, cutoff=0.72)
            if matches:
                canonical = ALIAS_MAP[matches[0]]
            else:
                logger.warning("UNMATCHED: %s", item_text)
                _log_unmatched(item_text)
                continue

        totals[canonical] += qty

    return list(totals.items())


def _log_unmatched(text: str) -> None:
    import config
    import os
    os.makedirs("logs", exist_ok=True)
    with open(config.UNMATCHED_LOG, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def _format_order(items: list[tuple[str, int]]) -> str:
    return "\n".join(f"  • {qty}x {name}" for name, qty in items)


async def handle_menu_command(update: Update, context) -> None:
    await update.message.reply_text(f"Our menu:\n\n{menu_list_text()}")


async def handle_order_text(update: Update, context) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    items = _parse_items(text)
    if not items:
        await update.message.reply_text(
            "Sorry, I couldn't match any menu items in your message.\n\n"
            f"Our menu:\n{menu_list_text()}\n\n"
            "You can also type /menu anytime."
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
