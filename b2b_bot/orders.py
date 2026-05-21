"""B2B order intake — parsing, history resolution, and confirmation flow."""

import re
import difflib
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from b2b_bot.menu import B2B_MENU, ALIAS_MAP
from b2b_bot.customers import get_business_name, is_b2b_group
from shared.database import (
    get_b2b_customer, upsert_b2b_customer,
    save_b2b_order, get_b2b_orders_for_date, get_b2b_last_order_item,
)

logger = logging.getLogger(__name__)

# In-memory pending orders: {group_chat_id: {items, delivery_method, ...}}
_pending: dict[int, dict] = {}
# Conversation state: {group_chat_id: "awaiting_delivery"}
_state: dict[int, str] = {}

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "dozen": 12,
}

_NOISE = re.compile(
    r"^(i('d)?\s+(want|like|would\s+like)|can\s+(i|we)\s+(get|have|order)|"
    r"please\s+(give\s+(me|us)|send\s+(me|us))?|i('ll\s+have)?|"
    r"we('d)?\s+(like|want|need)|i\s+need|give\s+(me|us)|order[:\s]+)\s*",
    re.IGNORECASE,
)
_GRAM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:g\b|grams?\b)', re.IGNORECASE)
_KG_RE   = re.compile(r'(\d+(?:\.\d+)?)\s*kg\b', re.IGNORECASE)
_TIME_RE = re.compile(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', re.IGNORECASE)


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def _strip_noise(text: str) -> str:
    return _NOISE.sub("", text).strip()


def _extract_grams(text: str) -> tuple[int | None, str]:
    """Pull gram amount out of text. Returns (grams, cleaned_text)."""
    m = _KG_RE.search(text)
    if m:
        grams = int(float(m.group(1)) * 1000)
        return grams, (text[:m.start()] + " " + text[m.end():]).strip()
    m = _GRAM_RE.search(text)
    if m:
        grams = int(float(m.group(1)))
        return grams, (text[:m.start()] + " " + text[m.end():]).strip()
    return None, text


def _match_item(text: str) -> tuple[str | None, str]:
    """Match item name from start of text (longest match first). Returns (canonical, leftover)."""
    words = text.split()
    for end in range(len(words), 0, -1):
        candidate = " ".join(words[:end])
        canonical = ALIAS_MAP.get(candidate)
        if not canonical and candidate.endswith("s"):
            canonical = ALIAS_MAP.get(candidate[:-1])
        if not canonical:
            matches = difflib.get_close_matches(candidate, ALIAS_MAP.keys(), n=1, cutoff=0.72)
            if matches:
                canonical = ALIAS_MAP[matches[0]]
        if canonical:
            return canonical, " ".join(words[end:]).strip()
    return None, text


def _parse_attributes(item_name: str, text: str) -> str | None:
    """Match attribute keywords in leftover text. Returns matched option or raw text."""
    item_def = B2B_MENU.get(item_name, {})
    for attr_def in item_def.get("attributes", {}).values():
        for option, keywords in attr_def.get("keywords", {}).items():
            for kw in keywords:
                if kw in text:
                    return option
    return text.strip() or None


def _parse_order(text: str) -> list[dict]:
    """Parse order text into list of {item, qty, grams, notes} dicts."""
    text = _strip_noise(text.lower().strip())
    results: list[dict] = []

    for part in re.split(r",|\band\b", text):
        part = part.strip()
        if not part:
            continue

        # Extract quantity
        qty = 1
        m = re.match(r"^(\d+)\s+(.+)$", part)
        if m:
            qty, part = int(m.group(1)), m.group(2).strip()
        else:
            wm = re.match(r"^(" + "|".join(_WORD_NUMBERS) + r")\s+(.+)$", part)
            if wm:
                qty, part = _WORD_NUMBERS[wm.group(1)], wm.group(2).strip()

        grams, part = _extract_grams(part)
        canonical, leftover = _match_item(part)

        if not canonical:
            logger.warning("B2B UNMATCHED: %s", part)
            _log_unmatched(part)
            continue

        notes = _parse_attributes(canonical, leftover) if leftover else None
        results.append({"item": canonical, "qty": qty, "grams": grams, "notes": notes})

    return results


def _log_unmatched(text: str) -> None:
    import config, os
    os.makedirs("logs", exist_ok=True)
    with open(config.UNMATCHED_LOG, "a", encoding="utf-8") as f:
        f.write(f"[B2B] {text}\n")


def _parse_delivery_text(text: str) -> tuple[str | None, str | None]:
    """Return (method, time_str) from a free-text delivery/pickup message."""
    lower = text.lower()
    method = None
    if "delivery" in lower:
        method = "delivery"
    elif any(w in lower for w in ("pickup", "pick up", "pick-up", "collect")):
        method = "pickup"
    m = _TIME_RE.search(text)
    time_str = m.group(1).strip() if m else None
    return method, time_str


# ─── History resolution ───────────────────────────────────────────────────────

def _resolve_history(group_chat_id: int, items: list[dict]) -> list[dict]:
    """Fill missing grams and notes from order history, falling back to menu standards."""
    resolved = []
    for it in items:
        it = dict(it)
        item_def = B2B_MENU.get(it["item"], {})

        if it["grams"] is None:
            last = get_b2b_last_order_item(group_chat_id, it["item"])
            if last and last["grams"]:
                it["grams"] = last["grams"]
                it["grams_source"] = "history"
            elif item_def.get("standard_grams"):
                it["grams"] = item_def["standard_grams"]
                it["grams_source"] = "standard"

        if it["notes"] is None and item_def.get("attributes"):
            last = get_b2b_last_order_item(group_chat_id, it["item"])
            if last and last["notes"]:
                it["notes"] = last["notes"]
                it["notes_source"] = "history"
            else:
                for attr_def in item_def["attributes"].values():
                    it["notes"] = attr_def.get("standard")
                    it["notes_source"] = "standard"
                    break

        resolved.append(it)
    return resolved


# ─── Formatting ───────────────────────────────────────────────────────────────

def _item_line(it: dict) -> str:
    item_def = B2B_MENU.get(it["item"], {})
    line = f"  • {it['qty']}x {it['item']}"

    if it.get("grams"):
        src = it.get("grams_source", "")
        tag = " (same as last time)" if src == "history" else (" (our standard)" if src == "standard" else "")
        line += f" — {it['grams']}g{tag}"
    elif item_def.get("unit"):
        line += f" ({item_def['unit']} each)"
    elif item_def.get("standard_grams") and not item_def.get("requires_grams"):
        line += f" — {item_def['standard_grams']}g each"

    if it.get("notes"):
        src = it.get("notes_source", "")
        tag = " (same as last time)" if src == "history" else (" (our standard)" if src == "standard" else "")
        line += f"\n    {it['notes']}{tag}"

    if item_def.get("order_note"):
        line += f"\n    Note: {item_def['order_note']}"

    return line


def _date_label(delivery_date: str) -> str:
    """Return a human-readable date label like 'tomorrow (Thu 22 May)'."""
    d = date.fromisoformat(delivery_date)
    if d == date.today() + timedelta(days=1):
        return f"tomorrow ({d.strftime('%a %d %b')})"
    return d.strftime("%a %d %b")


def _delivery_line(method: str | None, time_str: str | None, location: str | None, delivery_date: str | None = None) -> str:
    if not method or not time_str:
        return ""
    when = f" {_date_label(delivery_date)}" if delivery_date else " tomorrow"
    if method == "delivery":
        loc = f" — {location}" if location else ""
        return f"Delivery{when} at {time_str}{loc}"
    return f"Pickup{when} at {time_str}"


def _confirmation_text(items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str | None = None, heading: str = "Here's the order:") -> str:
    parts = [heading, ""]
    parts += [_item_line(it) for it in items]
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        parts += ["", dl]
    parts += ["", "Is this correct?"]
    return "\n".join(parts)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Confirm ✓", callback_data="b2b_confirm"),
        InlineKeyboardButton("Edit ✗",    callback_data="b2b_edit"),
        InlineKeyboardButton("Cancel",    callback_data="b2b_cancel"),
    ]])


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def handle_group_message(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    business_name = get_business_name(chat_id)

    # ── State: waiting for delivery/pickup info ────────────────────────────────
    if _state.get(chat_id) == "awaiting_delivery":
        method, time_str = _parse_delivery_text(text)
        if not method or not time_str:
            await update.message.reply_text(
                "Please let me know: pickup or delivery, and what time?\n"
                "Example: Delivery at 8am  |  Pickup at 7am"
            )
            return

        location = business_name if method == "delivery" else None
        upsert_b2b_customer(chat_id, business_name, method, time_str, location)
        _state.pop(chat_id, None)

        pending = _pending.get(chat_id, {})
        pending.update(delivery_method=method, delivery_time=time_str, location=location)
        _pending[chat_id] = pending

        await update.message.reply_text(
            _confirmation_text(pending["items"], method, time_str, location, pending.get("delivery_date")),
            reply_markup=_confirm_keyboard(),
        )
        return

    # ── Parse order ───────────────────────────────────────────────────────────
    items = _parse_order(text)
    if not items:
        return  # Not an order — ignore silently

    items = _resolve_history(chat_id, items)

    customer      = get_b2b_customer(chat_id)
    method        = customer["delivery_method"] if customer else None
    time_str      = customer["delivery_time"]   if customer else None
    location      = customer["location"]        if customer else None
    delivery_date = (date.today() + timedelta(days=1)).isoformat()

    # ── Re-order: group already has an order for the same delivery date ────────
    existing = get_b2b_orders_for_date(chat_id, delivery_date)

    if existing:
        existing_items = [dict(r) for r in existing]
        for ei in existing_items:
            ei["qty"] = ei.pop("quantity", 1)

        _pending[chat_id] = {
            "items": items,
            "existing_items": existing_items,
            "delivery_method": method,
            "delivery_time": time_str,
            "location": location,
            "delivery_date": delivery_date,
        }

        existing_lines = "\n".join(
            f"  • {ei['qty']}x {ei['item']}"
            + (f" — {ei['grams']}g" if ei.get("grams") else "")
            + (f"\n    {ei['notes']}" if ei.get("notes") else "")
            for ei in existing_items
        )
        await update.message.reply_text(
            f"You already have an order for {_date_label(delivery_date)}:\n{existing_lines}\n\n"
            "Is this new order in addition to that?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Yes, it's extra", callback_data="b2b_extra_yes"),
                InlineKeyboardButton("Cancel",          callback_data="b2b_cancel"),
            ]]),
        )
        return

    # ── First order for this delivery date ────────────────────────────────────
    _pending[chat_id] = {
        "items": items,
        "delivery_method": method,
        "delivery_time": time_str,
        "location": location,
        "delivery_date": delivery_date,
    }

    if not method:
        upsert_b2b_customer(chat_id, business_name)  # register if not yet known
        _state[chat_id] = "awaiting_delivery"
        await update.message.reply_text(
            "Got it! One quick question before I confirm — pickup or delivery, and what time?\n"
            "Example: Delivery at 8am  |  Pickup at 7am"
        )
        return

    await update.message.reply_text(
        _confirmation_text(items, method, time_str, location, delivery_date),
        reply_markup=_confirm_keyboard(),
    )


async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    if query.data == "b2b_extra_yes":
        pending = _pending.get(chat_id)
        if not pending:
            await query.edit_message_text("No pending order found. Please send your order again.")
            return

        new_items      = _resolve_history(chat_id, pending["items"])
        existing_items = pending.get("existing_items", [])
        pending["items"] = new_items
        _pending[chat_id] = pending

        existing_lines = [
            _item_line({**ei, "qty": ei.get("qty", ei.get("quantity", 1))}) + " *(existing)*"
            for ei in existing_items
        ]
        new_lines = [_item_line(ni) + " *(new)*" for ni in new_items]

        dl = _delivery_line(pending.get("delivery_method"), pending.get("delivery_time"), pending.get("location"), pending.get("delivery_date"))
        body = "Full updated order:\n\n" + "\n".join(existing_lines + new_lines)
        if dl:
            body += f"\n\n{dl}"
        body += "\n\nConfirm full order?"

        await query.edit_message_text(body, reply_markup=_confirm_keyboard())

    elif query.data == "b2b_confirm":
        pending = _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        if not pending:
            await query.edit_message_text("No pending order. Please send your order again.")
            return
        business_name = get_business_name(chat_id)
        delivery_date = pending.get("delivery_date", (date.today() + timedelta(days=1)).isoformat())
        save_b2b_order(chat_id, business_name, pending["items"], delivery_date)
        logger.info("B2B order confirmed for %s (%s) delivery %s: %s", business_name, chat_id, delivery_date, pending["items"])
        await query.edit_message_text("Order confirmed. Thank you!")

    elif query.data == "b2b_edit":
        _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        await query.edit_message_text("No problem — please send your order again.")

    elif query.data == "b2b_cancel":
        _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        await query.edit_message_text("Order cancelled.")
