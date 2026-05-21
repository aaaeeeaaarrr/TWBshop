"""B2B order intake — parsing, history resolution, confirmation flow.

Handles both bread and cake/dessert items in the same group.
Cake items trigger an instant notification to the bakery staff group on confirmation.
"""

import re
import difflib
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

import config
from b2b_bot.menu import B2B_MENU, ALIAS_MAP, INSTANT_BREAD_ITEMS, MINI_ITEMS
from b2b_bot.cake_menu import B2B_CAKE_MENU, CAKE_ALIAS_MAP
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.pricing import item_price, order_total, price_summary
from shared.database import (
    get_b2b_customer, upsert_b2b_customer,
    save_b2b_order, get_b2b_orders_for_date, get_b2b_last_order_item,
    save_b2b_cake_order, get_b2b_cake_orders_for_date, get_b2b_cake_last_order_item,
)

logger = logging.getLogger(__name__)

# In-memory pending orders: {group_chat_id: {bread_items, cake_items, delivery_*, ...}}
_pending: dict[int, dict] = {}
# Conversation state: {group_chat_id: "awaiting_delivery" | "awaiting_cake_spec"}
_state:   dict[int, dict] = {}  # {group_chat_id: {"mode": str, ...}}

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
_GRAM_RE  = re.compile(r'(\d+(?:\.\d+)?)\s*(?:g\b|grams?\b)', re.IGNORECASE)
_KG_RE    = re.compile(r'(\d+(?:\.\d+)?)\s*kg\b', re.IGNORECASE)
_TIME_RE  = re.compile(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', re.IGNORECASE)
_TODAY_RE = re.compile(
    r'\b(today|tonight|now|asap|same.?day|this\s+afternoon|this\s+evening)\b',
    re.IGNORECASE,
)
_SLICED_RE = re.compile(r'\b(sliced?|cut|in\s+slices?)\b', re.IGNORECASE)
_WHOLE_RE  = re.compile(r'\b(whole|unsliced|full\s+cake|not\s+sliced)\b', re.IGNORECASE)
_TRAY_RE   = re.compile(r'\b(tray|full\s+tray)\b', re.IGNORECASE)
_SLICE_COUNT_RE = re.compile(r'(\d+)\s*(?:slices?|cuts?|pieces?|pcs?)', re.IGNORECASE)


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def _strip_noise(text: str) -> str:
    return _NOISE.sub("", text).strip()


def _extract_grams(text: str) -> tuple[int | None, str]:
    m = _KG_RE.search(text)
    if m:
        return int(float(m.group(1)) * 1000), (text[:m.start()] + " " + text[m.end():]).strip()
    m = _GRAM_RE.search(text)
    if m:
        return int(float(m.group(1))), (text[:m.start()] + " " + text[m.end():]).strip()
    return None, text


def _match_bread(text: str) -> tuple[str | None, str]:
    """Longest-match against bread ALIAS_MAP. Returns (canonical, leftover)."""
    words = text.split()
    for end in range(len(words), 0, -1):
        candidate = " ".join(words[:end])
        canonical = ALIAS_MAP.get(candidate)
        if not canonical and candidate.endswith("s"):
            canonical = ALIAS_MAP.get(candidate[:-1])
        if not canonical:
            hits = difflib.get_close_matches(candidate, ALIAS_MAP.keys(), n=1, cutoff=0.72)
            if hits:
                canonical = ALIAS_MAP[hits[0]]
        if canonical:
            return canonical, " ".join(words[end:]).strip()
    return None, text


def _match_cake(text: str) -> tuple[str | None, str]:
    """Longest-match against cake CAKE_ALIAS_MAP. Returns (canonical, leftover)."""
    words = text.split()
    for end in range(len(words), 0, -1):
        candidate = " ".join(words[:end])
        canonical = CAKE_ALIAS_MAP.get(candidate)
        if not canonical and candidate.endswith("s"):
            canonical = CAKE_ALIAS_MAP.get(candidate[:-1])
        if not canonical:
            hits = difflib.get_close_matches(candidate, CAKE_ALIAS_MAP.keys(), n=1, cutoff=0.72)
            if hits:
                canonical = CAKE_ALIAS_MAP[hits[0]]
        if canonical:
            return canonical, " ".join(words[end:]).strip()
    return None, text


def _extract_cake_spec(text: str, cake_category: str) -> tuple[str | None, int | None]:
    """Parse order_type and slice count from text for a cake item."""
    if cake_category == "C":
        return "piece", None

    if cake_category == "B":
        return ("tray", None) if _TRAY_RE.search(text) else ("piece", None)

    # Category A: whole or sliced
    if _WHOLE_RE.search(text):
        return "full", None

    slice_count_m = _SLICE_COUNT_RE.search(text)
    if slice_count_m:
        return "sliced", int(slice_count_m.group(1))

    if _SLICED_RE.search(text):
        return "sliced", None  # slice count resolved from history

    return None, None  # unspecified — needs resolution


def _parse_order(raw: str) -> tuple[list[dict], list[dict]]:
    """Parse text into (bread_items, cake_items). Each item is a dict."""
    text = _strip_noise(raw.lower().strip())
    bread_items: list[dict] = []
    cake_items:  list[dict] = []

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

        # Extract grams (for bread buns)
        grams, part_no_grams = _extract_grams(part)

        # Try bread menu first
        canonical, leftover = _match_bread(part_no_grams)
        if canonical:
            item_def = B2B_MENU[canonical]
            notes = None
            for attr_def in item_def.get("attributes", {}).values():
                for option, keywords in attr_def.get("keywords", {}).items():
                    if any(kw in leftover for kw in keywords):
                        notes = option
                        break
            bread_items.append({"item": canonical, "qty": qty, "grams": grams, "notes": notes})
            continue

        # Try cake menu
        canonical, leftover = _match_cake(part_no_grams)
        if not canonical:
            # try original part text (no gram stripped) for cake names
            canonical, leftover = _match_cake(part)

        if canonical:
            cake_def = B2B_CAKE_MENU[canonical]
            order_type, slices = _extract_cake_spec(part, cake_def["cake_category"])
            cake_items.append({
                "item": canonical,
                "qty": qty,
                "cake_category": cake_def["cake_category"],
                "order_type": order_type,
                "slices": slices,
            })
            continue

        logger.warning("B2B UNMATCHED: %s", part)
        _log_unmatched(part)

    return bread_items, cake_items


def _log_unmatched(text: str) -> None:
    import os
    os.makedirs("logs", exist_ok=True)
    with open(config.UNMATCHED_LOG, "a", encoding="utf-8") as f:
        f.write(f"[B2B] {text}\n")


# ─── History resolution ───────────────────────────────────────────────────────

def _resolve_bread_history(group_chat_id: int, items: list[dict]) -> list[dict]:
    resolved = []
    for it in items:
        it = dict(it)
        item_def = B2B_MENU[it["item"]]

        if it["grams"] is None:
            last = get_b2b_last_order_item(group_chat_id, it["item"])
            if last and last["grams"]:
                it["grams"], it["grams_source"] = last["grams"], "history"
            elif item_def.get("standard_grams"):
                it["grams"], it["grams_source"] = item_def["standard_grams"], "standard"

        if it["notes"] is None and item_def.get("attributes"):
            last = get_b2b_last_order_item(group_chat_id, it["item"])
            if last and last["notes"]:
                it["notes"], it["notes_source"] = last["notes"], "history"
            else:
                for attr_def in item_def["attributes"].values():
                    it["notes"], it["notes_source"] = attr_def.get("standard"), "standard"
                    break

        resolved.append(it)
    return resolved


def _resolve_cake_history(group_chat_id: int, items: list[dict]) -> tuple[list[dict], list[str]]:
    """Resolve order_type/slices from history. Returns (resolved_items, names_needing_spec)."""
    resolved = []
    needs_spec = []

    for it in items:
        it = dict(it)
        cake_def = B2B_CAKE_MENU[it["item"]]

        if it.get("order_type") is None and cake_def["cake_category"] == "A":
            last = get_b2b_cake_last_order_item(group_chat_id, it["item"])
            if last:
                it["order_type"] = last["order_type"]
                it["order_type_source"] = "history"
                if last["order_type"] == "sliced":
                    it["slices"] = last["slices"] or cake_def["standard_slices"]
                    it["slices_source"] = "history"
            else:
                needs_spec.append(it["item"])

        if it.get("order_type") == "sliced" and it.get("slices") is None:
            last = get_b2b_cake_last_order_item(group_chat_id, it["item"])
            if last and last["slices"]:
                it["slices"], it["slices_source"] = last["slices"], "history"
            else:
                it["slices"], it["slices_source"] = cake_def["standard_slices"], "standard"

        resolved.append(it)
    return resolved, needs_spec


# ─── Formatting ───────────────────────────────────────────────────────────────

def _bread_line(it: dict) -> str:
    item_def = B2B_MENU[it["item"]]
    line = f"  • {it['qty']}x {it['item']}"

    if it.get("grams"):
        src = it.get("grams_source", "")
        tag = " (same as last time)" if src == "history" else (" (our standard)" if src == "standard" else "")
        line += f" — {it['grams']}g{tag}"
    elif item_def.get("unit"):
        line += f" ({item_def['unit']} each)"

    if it.get("notes"):
        src = it.get("notes_source", "")
        tag = " (same as last time)" if src == "history" else (" (our standard)" if src == "standard" else "")
        line += f"\n    {it['notes']}{tag}"

    if item_def.get("order_note"):
        line += f"\n    Note: {item_def['order_note']}"

    price = item_price(it)
    if price:
        line += f" — ${price:.2f}"

    return line


def _cake_line(it: dict) -> str:
    line = f"  • {it['qty']}x {it['item']}"
    order_type = it.get("order_type")

    if order_type == "full":
        src = " (same as last time — please confirm)" if it.get("order_type_source") == "history" else ""
        line += f" — whole{src}"
    elif order_type == "sliced":
        slices = it.get("slices", "?")
        src = it.get("slices_source", "")
        slice_tag = " (same as last time — please confirm)" if src == "history" else (" (our standard — please confirm)" if src == "standard" else "")
        ot_tag = " (same as last time — please confirm)" if it.get("order_type_source") == "history" else ""
        line += f" — sliced, {slices} slices{slice_tag or ot_tag}"
    elif order_type == "tray":
        line += " — full tray (~35pc)"
    elif order_type == "piece":
        pass  # just quantity is enough

    if order_type == "needs_spec":
        line += " — PLEASE SPECIFY: sliced or whole?"

    price = item_price(it)
    if price:
        line += f" — ${price:.2f}"

    return line


def _date_label(delivery_date: str) -> str:
    d = date.fromisoformat(delivery_date)
    if d == date.today() + timedelta(days=1):
        return f"tomorrow ({d.strftime('%a %d %b')})"
    if d == date.today():
        return f"today ({d.strftime('%a %d %b')})"
    return d.strftime("%a %d %b")


def _delivery_line(method: str | None, time_str: str | None, location: str | None, delivery_date: str | None = None) -> str:
    if not method or not time_str:
        return ""
    when = f" {_date_label(delivery_date)}" if delivery_date else " tomorrow"
    if method == "delivery":
        loc = f" — {location}" if location else ""
        return f"Delivery{when} at {time_str}{loc}"
    return f"Pickup{when} at {time_str}"


def _build_confirmation(
    bread_items: list[dict],
    cake_items:  list[dict],
    method:        str | None,
    time_str:      str | None,
    location:      str | None,
    delivery_date: str | None = None,
    heading:       str = "Here's the order:",
) -> str:
    parts = [heading, ""]

    if bread_items:
        parts += [_bread_line(it) for it in bread_items]
    if cake_items:
        if bread_items:
            parts.append("")
        parts += [_cake_line(it) for it in cake_items]

    total = order_total(bread_items, cake_items)
    dl    = _delivery_line(method, time_str, location, delivery_date)

    parts += ["", price_summary(total)]
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


def _parse_delivery_text(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    method = None
    if "delivery" in lower:
        method = "delivery"
    elif any(w in lower for w in ("pickup", "pick up", "pick-up", "collect")):
        method = "pickup"
    m = _TIME_RE.search(text)
    return method, (m.group(1).strip() if m else None)


# ─── Instant cake notification ────────────────────────────────────────────────

async def _notify_cake_order(bot, business_name: str, cake_items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str) -> None:
    lines = [f"DESSERT ORDER — {business_name}", ""]
    for it in cake_items:
        lines.append(_cake_line(it))
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        lines += ["", dl]
    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines))


async def _notify_urgent_bread_order(bot, business_name: str, bread_items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str) -> None:
    """Instant alert for croissant / pain au chocolat orders."""
    urgent = [it for it in bread_items if it["item"] in INSTANT_BREAD_ITEMS]
    if not urgent:
        return
    lines = [f"CROISSANT / CHOCOLATIN ORDER — {business_name}", ""]
    for it in urgent:
        lines.append(_bread_line(it))
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        lines += ["", dl]
    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines))


async def _notify_mini_order(bot, business_name: str, bread_items: list[dict], method: str | None, time_str: str | None, location: str | None, delivery_date: str) -> None:
    """Instant alert for mini pastry orders (100pc min, 48h advance)."""
    minis = [it for it in bread_items if it["item"] in MINI_ITEMS]
    if not minis:
        return
    lines = [f"MINI ORDER — {business_name}", ""]
    for it in minis:
        lines.append(_bread_line(it))
    dl = _delivery_line(method, time_str, location, delivery_date)
    if dl:
        lines += ["", dl]
    await bot.send_message(config.B2B_STAFF_GROUP_ID, "\n".join(lines))


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def handle_group_message(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    business_name = get_business_name(chat_id)
    state = _state.get(chat_id, {})

    # ── State: awaiting delivery/pickup info ──────────────────────────────────
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
        _state.pop(chat_id, None)
        pending = _pending.get(chat_id, {})
        pending.update(delivery_method=method, delivery_time=time_str, location=location)
        _pending[chat_id] = pending
        await update.message.reply_text(
            _build_confirmation(pending.get("bread_items", []), pending.get("cake_items", []), method, time_str, location, pending.get("delivery_date")),
            reply_markup=_confirm_keyboard(),
        )
        return

    # ── State: awaiting sliced/whole spec for cake items ─────────────────────
    if state.get("mode") == "awaiting_cake_spec":
        pending = _pending.get(chat_id, {})
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

        _state.pop(chat_id, None)
        pending["cake_items"] = cake_items
        _pending[chat_id] = pending
        m_ = pending.get("delivery_method")
        t_ = pending.get("delivery_time")
        l_ = pending.get("location")
        dd = pending.get("delivery_date")
        if not m_:
            _state[chat_id] = {"mode": "awaiting_delivery"}
            upsert_b2b_customer(chat_id, business_name)
            await update.message.reply_text(
                "Got it! One quick question — pickup or delivery, and what time?\n"
                "Example: Delivery at 8am  |  Pickup at 7am"
            )
        else:
            await update.message.reply_text(
                _build_confirmation(pending.get("bread_items", []), cake_items, m_, t_, l_, dd),
                reply_markup=_confirm_keyboard(),
            )
        return

    # ── Parse new order ───────────────────────────────────────────────────────
    bread_items, cake_items = _parse_order(text)
    if not bread_items and not cake_items:
        return

    # Validate mini items: 100pc minimum per item (not combined)
    mini_errors = [
        f"{it['item']}: you ordered {it['qty']}pc (min. 100pc per item)"
        for it in bread_items
        if it["item"] in MINI_ITEMS and it["qty"] < 100
    ]
    if mini_errors:
        await update.message.reply_text(
            "Mini items require a minimum of 100pc per item — quantities cannot be combined:\n"
            + "\n".join(f"  • {e}" for e in mini_errors)
            + "\n\nPlease update your order."
        )
        return

    is_today = bool(_TODAY_RE.search(text))
    delivery_date = date.today().isoformat() if is_today and not bread_items else (date.today() + timedelta(days=1)).isoformat()

    bread_items = _resolve_bread_history(chat_id, bread_items)
    cake_items, needs_spec = _resolve_cake_history(chat_id, cake_items)

    customer = get_b2b_customer(chat_id)
    method   = customer["delivery_method"] if customer else None
    time_str = customer["delivery_time"]   if customer else None
    location = customer["location"]        if customer else None

    # ── Re-order check ────────────────────────────────────────────────────────
    existing_bread = get_b2b_orders_for_date(chat_id, delivery_date)
    existing_cake  = get_b2b_cake_orders_for_date(chat_id, delivery_date)

    if existing_bread or existing_cake:
        existing_items = [dict(r) for r in existing_bread]
        for ei in existing_items:
            ei["qty"] = ei.pop("quantity", 1)
        existing_cake_items = [dict(r) for r in existing_cake]
        for ei in existing_cake_items:
            ei["qty"] = ei.pop("quantity", 1)

        _pending[chat_id] = {
            "bread_items": bread_items,
            "cake_items": cake_items,
            "existing_bread": existing_items,
            "existing_cake": existing_cake_items,
            "delivery_method": method,
            "delivery_time": time_str,
            "location": location,
            "delivery_date": delivery_date,
        }

        existing_lines = "\n".join(
            f"  • {ei['qty']}x {ei['item']}"
            + (f" — {ei.get('grams')}g" if ei.get("grams") else "")
            for ei in existing_items + existing_cake_items
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

    # ── Store pending ─────────────────────────────────────────────────────────
    _pending[chat_id] = {
        "bread_items": bread_items,
        "cake_items": cake_items,
        "delivery_method": method,
        "delivery_time": time_str,
        "location": location,
        "delivery_date": delivery_date,
    }

    # ── Ask for cake spec if any Category A cakes are unspecified ─────────────
    if needs_spec:
        _state[chat_id] = {"mode": "awaiting_cake_spec", "needs_spec": needs_spec}
        names = ", ".join(needs_spec)
        await update.message.reply_text(
            f"For the {names} — sliced or whole?\n"
            "(If sliced, you can also tell me how many slices, e.g. 'sliced 10')"
        )
        return

    # ── Ask for delivery if new customer ──────────────────────────────────────
    if not method:
        _state[chat_id] = {"mode": "awaiting_delivery"}
        upsert_b2b_customer(chat_id, business_name)
        await update.message.reply_text(
            "Got it! One quick question — pickup or delivery, and what time?\n"
            "Example: Delivery at 8am  |  Pickup at 7am"
        )
        return

    await update.message.reply_text(
        _build_confirmation(bread_items, cake_items, method, time_str, location, delivery_date),
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

        bread_items = _resolve_bread_history(chat_id, pending["bread_items"])
        cake_items, _ = _resolve_cake_history(chat_id, pending["cake_items"])
        pending["bread_items"] = bread_items
        pending["cake_items"]  = cake_items
        _pending[chat_id] = pending

        existing_bread = pending.get("existing_bread", [])
        existing_cake  = pending.get("existing_cake", [])

        def _existing_line(ei):
            line = f"  • {ei.get('qty',1)}x {ei['item']}"
            if ei.get("grams"):
                line += f" — {ei['grams']}g"
            return line + " *(existing)*"

        ex_lines  = [_existing_line(ei) for ei in existing_bread + existing_cake]
        new_lines = [_bread_line(it) + " *(new)*" for it in bread_items] + \
                    [_cake_line(it)  + " *(new)*" for it in cake_items]

        total = order_total(bread_items, cake_items)
        dl    = _delivery_line(pending.get("delivery_method"), pending.get("delivery_time"), pending.get("location"), pending.get("delivery_date"))

        body = "Full updated order:\n\n" + "\n".join(ex_lines + new_lines)
        body += "\n\n" + price_summary(total)
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
        bread_items   = pending.get("bread_items", [])
        cake_items    = pending.get("cake_items", [])

        method_   = pending.get("delivery_method")
        time_str_ = pending.get("delivery_time")
        location_ = pending.get("location")

        if bread_items:
            save_b2b_order(chat_id, business_name, bread_items, delivery_date)
            if any(it["item"] in INSTANT_BREAD_ITEMS for it in bread_items):
                await _notify_urgent_bread_order(
                    context.bot, business_name, bread_items,
                    method_, time_str_, location_, delivery_date,
                )
            if any(it["item"] in MINI_ITEMS for it in bread_items):
                await _notify_mini_order(
                    context.bot, business_name, bread_items,
                    method_, time_str_, location_, delivery_date,
                )
        if cake_items:
            save_b2b_cake_order(chat_id, business_name, cake_items, delivery_date)
            await _notify_cake_order(
                context.bot, business_name, cake_items,
                method_, time_str_, location_, delivery_date,
            )

        logger.info("B2B order confirmed for %s (%s) delivery %s", business_name, chat_id, delivery_date)
        await query.edit_message_text("Order confirmed. Thank you!")

    elif query.data == "b2b_edit":
        _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        await query.edit_message_text("No problem — please send your order again.")

    elif query.data == "b2b_cancel":
        _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        await query.edit_message_text("Order cancelled.")
