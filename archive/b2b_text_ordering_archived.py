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
from shared.ai_client import extract_b2b_order_from_image, parse_b2b_order_text
from b2b_bot.customers import get_business_name, is_b2b_group
from b2b_bot.pricing import item_price, order_total, price_summary
from shared.database import (
    get_b2b_customer, upsert_b2b_customer,
    save_b2b_order, get_b2b_orders_for_date, get_b2b_last_order_item,
    save_b2b_cake_order, get_b2b_cake_orders_for_date, get_b2b_cake_last_order_item,
    delete_b2b_orders_for_date, delete_b2b_cake_orders_for_date,
)

logger = logging.getLogger(__name__)

# In-memory pending orders: {group_chat_id: {bread_items, cake_items, delivery_*, ...}}
_pending: dict[int, dict] = {}
# Conversation state: {group_chat_id: "awaiting_delivery" | "awaiting_cake_spec"}
_state:   dict[int, dict] = {}  # {group_chat_id: {"mode": str, ...}}
# Last confirmation message ID per chat (to remove buttons when superseded)
_last_confirmation: dict[int, int] = {}  # {group_chat_id: message_id}

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "dozen": 12,
}

_NOISE = re.compile(
    r"^(no[,.]?\s+)?(i('d)?\s+(want|like|would\s+like)|can\s+(i|we)\s+(get|have|order)|"
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
_ITEM_CODE_RE   = re.compile(r'^[A-Z0-9][A-Z0-9\-]{2,}:\s*', re.IGNORECASE)
_PARENS_RE      = re.compile(r'\s*\([^)]*\)')


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


def _parse_order(raw: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Parse text into (bread_items, cake_items, unmatched_parts).
    unmatched_parts: [{item, qty}] for parts that matched nothing."""
    text = _strip_noise(raw.lower().strip())
    bread_items: list[dict] = []
    cake_items:  list[dict] = []
    unmatched:   list[dict] = []

    for part in re.split(r",|\band\b|\n", text):
        part = _strip_noise(part.strip())
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
        unmatched.append({"item": part, "qty": qty})

    return bread_items, cake_items, unmatched


def _combine_bread(items: list[dict]) -> list[dict]:
    """Merge rows with the same item/grams/notes by summing qty."""
    seen: dict[tuple, dict] = {}
    order: list[tuple] = []
    for it in items:
        key = (it.get("item"), it.get("grams"), it.get("notes"))
        if key in seen:
            seen[key]["qty"] += it.get("qty", 1)
        else:
            seen[key] = dict(it)
            order.append(key)
    return [seen[k] for k in order]


def _combine_cake(items: list[dict]) -> list[dict]:
    """Merge cake rows with the same item/order_type/slices by summing qty."""
    seen: dict[tuple, dict] = {}
    order: list[tuple] = []
    for it in items:
        key = (it.get("item"), it.get("order_type"), it.get("slices"))
        if key in seen:
            seen[key]["qty"] += it.get("qty", 1)
        else:
            seen[key] = dict(it)
            order.append(key)
    return [seen[k] for k in order]


def _merge_edit_bread(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """Edit-mode merge: update an existing item by name, or append if new."""
    result = [dict(it) for it in existing]
    for new in new_items:
        match = next((it for it in result if it["item"] == new["item"]), None)
        if match:
            if new.get("grams") is not None:
                match["grams"] = new["grams"]
                match.pop("grams_source", None)
            if new.get("notes") is not None:
                match["notes"] = new["notes"]
                match.pop("notes_source", None)
            if new.get("qty", 1) > 1:
                match["qty"] = new["qty"]
        else:
            result.append(new)
    return result


def _merge_edit_cake(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """Edit-mode merge: update an existing item by name, or append if new."""
    result = [dict(it) for it in existing]
    for new in new_items:
        match = next((it for it in result if it["item"] == new["item"]), None)
        if match:
            if new.get("order_type") is not None:
                match["order_type"] = new["order_type"]
                match.pop("order_type_source", None)
            if new.get("slices") is not None:
                match["slices"] = new["slices"]
                match.pop("slices_source", None)
            if new.get("qty", 1) > 1:
                match["qty"] = new["qty"]
        else:
            result.append(new)
    return result


def _split_mini_items(bread_items: list[dict], delivery_date: str) -> tuple[list[dict], list[dict]]:
    """Return (valid_bread, rejected). Items rejected if qty < min_quantity or < advance_hours away."""
    valid, rejected = [], []
    try:
        days_ahead = (date.fromisoformat(delivery_date) - date.today()).days
    except (ValueError, TypeError):
        days_ahead = 1
    for it in bread_items:
        item_def = B2B_MENU.get(it["item"], {})
        min_qty     = item_def.get("min_quantity")
        advance_h   = item_def.get("advance_hours")
        if not min_qty and not advance_h:
            valid.append(it)
            continue
        reasons = []
        if min_qty and it["qty"] < min_qty:
            reasons.append(f"only {it['qty']} {it['item']}")
            reasons.append(f"minimum is {min_qty} pieces")
        if advance_h and days_ahead * 24 < advance_h:
            reasons.append(f"{advance_h} hours ahead orders")
        if reasons:
            rejected.append({**it, "_reasons": reasons})
        else:
            valid.append(it)
    return valid, rejected


def _mini_rejection_note(rejected_minis: list[dict]) -> str:
    """Return a formatted rejection block (no leading newlines — callers add separator)."""
    if not rejected_minis:
        return ""
    parts = ["Our apologies, we cannot accept:"]
    for it in rejected_minis:
        parts.append(f"  ✗ {it['qty']}x {it['item']}")
        reasons = it.get("_reasons", [])
        if reasons:
            parts.append("\nREASON:")
            for r in reasons:
                parts.append(f"- {r}")
    return "\n".join(parts)


def _ai_items_to_orders(ai_items: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Fuzzy-match AI-read item names against the menu. Returns (bread, cake, unmatched)."""
    bread, cake, unmatched = [], [], []
    for it in ai_items:
        raw = it.get("item", "").strip()
        qty = max(1, int(it.get("qty", 1)))

        # Strip customer item codes (e.g. "PP-FOOD-BK-2503: ") and parenthetical qualifiers
        cleaned = _ITEM_CODE_RE.sub("", raw)
        cleaned = _PARENS_RE.sub("", cleaned).strip().lower()

        canonical, _ = _match_bread(cleaned)
        if canonical:
            bread.append({"item": canonical, "qty": qty, "grams": None, "notes": None})
            continue

        canonical, _ = _match_cake(cleaned)
        if canonical:
            cake_def = B2B_CAKE_MENU[canonical]
            cake.append({"item": canonical, "qty": qty, "cake_category": cake_def["cake_category"], "order_type": None, "slices": None})
            continue

        logger.warning("AI item not matched to menu: %s", raw)
        unmatched.append({"item": raw, "qty": qty})

    return bread, cake, unmatched


def _log_unmatched(text: str) -> None:
    import os
    os.makedirs("logs", exist_ok=True)
    with open(config.UNMATCHED_LOG, "a", encoding="utf-8") as f:
        f.write(f"[B2B] {text}\n")


_ALL_MENU_ITEMS: list[str] = list(B2B_MENU.keys()) + list(B2B_CAKE_MENU.keys())


async def _parse_order_ai(text: str) -> tuple[list[dict], list[dict], list[dict]]:
    """AI-first order parser. Falls back to rule-based if API not configured or AI returns nothing."""
    if config.ANTHROPIC_API_KEY:
        ai_items = await parse_b2b_order_text(text, _ALL_MENU_ITEMS)
        if ai_items:
            return _ai_items_to_orders(ai_items)
    return _parse_order(text)


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

        if it.get("order_type") is None:
            if cake_def["cake_category"] == "A":
                last = get_b2b_cake_last_order_item(group_chat_id, it["item"])
                if last:
                    it["order_type"] = last["order_type"]
                    it["order_type_source"] = "history"
                    if last["order_type"] == "sliced":
                        it["slices"] = last["slices"] or cake_def["standard_slices"]
                        it["slices_source"] = "history"
                else:
                    needs_spec.append(it["item"])
            else:
                it["order_type"] = "piece"

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


def _cake_line(it: dict, show_edit_hint: bool = False) -> str:
    line = f"  • {it['qty']}x {it['item']}"
    order_type = it.get("order_type")

    if order_type == "full":
        src = it.get("order_type_source")
        if src == "history":
            tag = " (same as last time — please confirm)"
        elif show_edit_hint:
            tag = " (edit if need sliced)"
        else:
            tag = ""
        line += f" — full, not sliced{tag}"
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
        parts += [_cake_line(it, show_edit_hint=True) for it in cake_items]

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


async def _send_confirmation(update_or_bot, chat_id: int, text: str) -> None:
    """Send a confirmation with buttons, removing buttons from the previous one."""
    bot = update_or_bot if not hasattr(update_or_bot, "message") else update_or_bot.message._bot
    old_msg_id = _last_confirmation.get(chat_id)
    if old_msg_id:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=old_msg_id, reply_markup=None)
        except Exception:
            pass
    if hasattr(update_or_bot, "message"):
        sent = await update_or_bot.message.reply_text(text, reply_markup=_confirm_keyboard())
    else:
        sent = await bot.send_message(chat_id, text, reply_markup=_confirm_keyboard())
    _last_confirmation[chat_id] = sent.message_id


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
    lines = [f"Add to order — {business_name}", ""]
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


# ─── Confirm helper (shared by button callback and typed "yes") ───────────────

_CONFIRM_WORDS = frozenset({"yes", "confirm", "confirmed", "ok", "okay", "yep", "yeah", "correct", "good", "fine"})
_CANCEL_WORDS  = frozenset({"no", "cancel", "nope", "nah", "nevermind", "stop"})
_EDIT_WORDS    = frozenset({"edit", "change", "modify", "wrong", "incorrect", "fix"})


async def _do_confirm_order(chat_id: int, pending: dict, context, reply_fn) -> None:
    """Save and confirm a pending order. reply_fn(text) sends the confirmation message."""
    business_name = get_business_name(chat_id)
    delivery_date = pending.get("delivery_date", (date.today() + timedelta(days=1)).isoformat())
    bread_items, _ = _split_mini_items(pending.get("bread_items", []), delivery_date)
    cake_items    = pending.get("cake_items", [])
    method_   = pending.get("delivery_method")
    time_str_ = pending.get("delivery_time")
    location_ = pending.get("location")

    if bread_items:
        save_b2b_order(chat_id, business_name, bread_items, delivery_date)
        if any(it["item"] in INSTANT_BREAD_ITEMS for it in bread_items):
            await _notify_urgent_bread_order(
                context.bot, business_name, bread_items, method_, time_str_, location_, delivery_date,
            )
        if any(it["item"] in MINI_ITEMS for it in bread_items):
            await _notify_mini_order(
                context.bot, business_name, bread_items, method_, time_str_, location_, delivery_date,
            )
    if cake_items:
        save_b2b_cake_order(chat_id, business_name, cake_items, delivery_date)
        await _notify_cake_order(
            context.bot, business_name, cake_items, method_, time_str_, location_, delivery_date,
        )

    logger.info("B2B order confirmed for %s (%s) delivery %s", business_name, chat_id, delivery_date)
    await reply_fn("✓ Order confirmed.")


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def handle_group_message(update: Update, context) -> None:
    chat_id = update.effective_chat.id
    if not is_b2b_group(chat_id):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    # If the button menu is waiting for a qty and the filter missed (e.g. after restart),
    # route here instead of parsing as an order.
    from shared.database import get_qty_pending as _get_qty_pending
    if _get_qty_pending(chat_id):
        from b2b_bot.menu_flow import handle_qty_input
        await handle_qty_input(update, context)
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
        await _send_confirmation(
            update, chat_id,
            _build_confirmation(pending.get("bread_items", []), pending.get("cake_items", []), method, time_str, location, pending.get("delivery_date")),
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
            await _send_confirmation(
                update, chat_id,
                _build_confirmation(pending.get("bread_items", []), cake_items, m_, t_, l_, dd),
            )
        return

    # ── State: awaiting yes/cancel on "is this extra?" — customer typed instead ─
    if state.get("mode") == "awaiting_extra_confirm":
        _state.pop(chat_id, None)
        _pending.pop(chat_id, None)
        # fall through — re-parse the typed text as a fresh replacement order

    # ── State: awaiting edit corrections ─────────────────────────────────────
    if state.get("mode") == "awaiting_edit":
        pending = _pending.get(chat_id)
        if not pending:
            _state.pop(chat_id, None)
        else:
            new_bread, new_cake, new_unmatched = await _parse_order_ai(text)
            new_bread = _resolve_bread_history(chat_id, new_bread)
            new_cake, new_needs_spec = _resolve_cake_history(chat_id, new_cake)

            merged_bread = _merge_edit_bread(pending.get("bread_items", []), new_bread)
            merged_cake  = _merge_edit_cake(pending.get("cake_items", []), new_cake)

            delivery_date = pending.get("delivery_date")
            merged_bread, edit_rejected = _split_mini_items(merged_bread, delivery_date)

            pending["bread_items"]  = merged_bread
            pending["cake_items"]   = merged_cake
            pending["ai_unmatched"] = new_unmatched
            _pending[chat_id] = pending
            _state.pop(chat_id, None)

            if new_needs_spec:
                _state[chat_id] = {"mode": "awaiting_cake_spec", "needs_spec": new_needs_spec}
                await update.message.reply_text(
                    f"For the {', '.join(new_needs_spec)} — sliced or whole?\n"
                    "(If sliced, you can also tell me how many slices, e.g. 'sliced 10')"
                )
                return

            method   = pending.get("delivery_method")
            time_str = pending.get("delivery_time")
            location = pending.get("location")

            if not method:
                _state[chat_id] = {"mode": "awaiting_delivery"}
                upsert_b2b_customer(chat_id, business_name)
                await update.message.reply_text(
                    "Got it! One quick question — pickup or delivery, and what time?\n"
                    "Example: Delivery at 8am  |  Pickup at 7am"
                )
                return

            existing_bread = pending.get("existing_bread", [])
            existing_cake  = pending.get("existing_cake", [])

            if existing_bread or existing_cake:
                # Came from "No, change it" — show full picture: existing + corrected new
                ex_lines = [
                    "  • {}x {}{}*(existing)*".format(
                        ei.get("qty", 1), ei["item"],
                        f" — {ei['grams']}g " if ei.get("grams") else " "
                    )
                    for ei in existing_bread + existing_cake
                ]
                new_lines = ([_bread_line(it) + " *(new)*" for it in merged_bread] +
                             [_cake_line(it, show_edit_hint=True) + " *(new)*" for it in merged_cake])
                total = order_total(existing_bread + merged_bread, existing_cake + merged_cake)
                dl    = _delivery_line(method, time_str, location, delivery_date)
                body  = "Full updated order:\n\n" + "\n".join(ex_lines + new_lines)
                body += "\n\n" + price_summary(total).replace("Subtotal:", "New total:")
                if dl:
                    body += f"\n\n{dl}"
                body += "\n\nConfirm full order?"
                if new_unmatched:
                    unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in new_unmatched)
                    body = body.replace("Confirm full order?", f"Not recognised:\n{unknown_lines}\n\nPlease edit or let us know what these are.\n\nConfirm full order?")
                if edit_rejected:
                    body += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(edit_rejected)
                await _send_confirmation(update, chat_id, body)
            else:
                msg = _build_confirmation(merged_bread, merged_cake, method, time_str, location, delivery_date)
                if new_unmatched:
                    unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in new_unmatched)
                    msg = msg.replace("Is this correct?", f"Not recognised:\n{unknown_lines}\n\nPlease edit or let us know what these are.\n\nIs this correct?")
                if edit_rejected:
                    msg += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(edit_rejected)
                await _send_confirmation(update, chat_id, msg)
            return

    # ── Pending confirmation: accept typed yes/no/edit/delivery change ───────
    if _pending.get(chat_id) and not state:
        lower_text = text.lower().strip()
        pending = _pending[chat_id]

        if lower_text in _CONFIRM_WORDS:
            _pending.pop(chat_id, None)
            _state.pop(chat_id, None)
            _last_confirmation.pop(chat_id, None)
            await _do_confirm_order(chat_id, pending, context, update.message.reply_text)
            return

        if lower_text in _CANCEL_WORDS:
            _pending.pop(chat_id, None)
            _state.pop(chat_id, None)
            _last_confirmation.pop(chat_id, None)
            await update.message.reply_text("Order cancelled.")
            return

        if lower_text in _EDIT_WORDS:
            _state[chat_id] = {"mode": "awaiting_edit"}
            bread_items_ = pending.get("bread_items", [])
            cake_items_  = pending.get("cake_items", [])
            understood = "\n".join([_bread_line(it) for it in bread_items_] + [_cake_line(it) for it in cake_items_])
            await update.message.reply_text(
                f"We have:\n{understood}\n\nJust type what you'd like to change."
            )
            return

        method_t, time_str_t = _parse_delivery_text(text)
        if method_t and time_str_t:
            location_t = business_name if method_t == "delivery" else None
            upsert_b2b_customer(chat_id, business_name, method_t, time_str_t, location_t)
            pending.update(delivery_method=method_t, delivery_time=time_str_t, location=location_t)
            _pending[chat_id] = pending
            msg = _build_confirmation(
                pending.get("bread_items", []), pending.get("cake_items", []),
                method_t, time_str_t, location_t, pending.get("delivery_date"),
            )
            if pending.get("ai_unmatched"):
                unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in pending["ai_unmatched"])
                msg = msg.replace("Is this correct?", f"Not recognised:\n{unknown_lines}\n\nPlease edit or let us know what these are.\n\nIs this correct?")
            await _send_confirmation(update, chat_id, msg)
            return

    # ── Parse new order ───────────────────────────────────────────────────────
    _RESPONSE_WORDS = frozenset({
        "sliced", "slice", "whole", "yes", "no", "ok", "okay",
        "full", "piece", "tray", "confirm", "cancel",
    })

    bread_items, cake_items, unmatched = await _parse_order_ai(text)

    ai_unmatched = unmatched

    if not bread_items and not cake_items and not ai_unmatched:
        return

    if not bread_items and not cake_items and ai_unmatched:
        if all(u["item"].lower() in _RESPONSE_WORDS for u in ai_unmatched):
            await update.message.reply_text(
                "I don't have any order in memory — please resend your order from the beginning."
            )
            return

    is_today = bool(_TODAY_RE.search(text))
    delivery_date = date.today().isoformat() if is_today and not bread_items else (date.today() + timedelta(days=1)).isoformat()

    bread_items = _resolve_bread_history(chat_id, bread_items)
    cake_items, needs_spec = _resolve_cake_history(chat_id, cake_items)
    bread_items, rejected_minis = _split_mini_items(bread_items, delivery_date)

    if not bread_items and not cake_items and not ai_unmatched and not rejected_minis:
        return

    customer = get_b2b_customer(chat_id)
    method   = customer["delivery_method"] if customer else None
    time_str = customer["delivery_time"]   if customer else None
    location = customer["location"]        if customer else None

    # ── Re-order check ────────────────────────────────────────────────────────
    existing_bread = get_b2b_orders_for_date(chat_id, delivery_date)
    existing_cake  = get_b2b_cake_orders_for_date(chat_id, delivery_date)

    if existing_bread or existing_cake:
        # Nothing valid to add — only rejected minis or unmatched items
        if not bread_items and not cake_items:
            parts = []
            if rejected_minis:
                parts.append(_mini_rejection_note(rejected_minis))
            if ai_unmatched:
                unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in ai_unmatched)
                parts.append(f"Not recognised:\n{unknown_lines}")
            await update.message.reply_text("\n\n".join(parts) if parts else "Nothing new to add to your order.")
            return

        existing_items = [dict(r) for r in existing_bread]
        for ei in existing_items:
            ei["qty"] = ei.pop("quantity", 1)
        existing_items = _combine_bread(existing_items)

        existing_cake_items = [dict(r) for r in existing_cake]
        for ei in existing_cake_items:
            ei["qty"] = ei.pop("quantity", 1)
        existing_cake_items = _combine_cake(existing_cake_items)

        _pending[chat_id] = {
            "bread_items": bread_items,
            "cake_items": cake_items,
            "existing_bread": existing_items,
            "existing_cake": existing_cake_items,
            "delivery_method": method,
            "delivery_time": time_str,
            "location": location,
            "delivery_date": delivery_date,
            "rejected_minis": rejected_minis,
        }

        existing_lines = "\n".join(
            f"  • {ei['qty']}x {ei['item']}"
            + (f" — {ei.get('grams')}g" if ei.get("grams") else "")
            for ei in existing_items + existing_cake_items
        )
        extra_msg = (
            f"You already have an order for {_date_label(delivery_date)}:\n{existing_lines}\n\n"
            "Is this new order in addition to that?"
        )
        new_lines = [_bread_line(it) for it in bread_items] + [_cake_line(it) for it in cake_items]
        if new_lines:
            extra_msg += "\n" + "\n".join(new_lines)
        if rejected_minis:
            extra_msg += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(rejected_minis)
        _state[chat_id] = {"mode": "awaiting_extra_confirm"}
        await update.message.reply_text(
            extra_msg,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Yes, it's extra",  callback_data="b2b_extra_yes"),
                InlineKeyboardButton("No, change it",    callback_data="b2b_extra_no_change"),
                InlineKeyboardButton("Cancel",           callback_data="b2b_cancel"),
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
        "ai_unmatched": ai_unmatched,
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

    msg = _build_confirmation(bread_items, cake_items, method, time_str, location, delivery_date)
    if ai_unmatched:
        unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in ai_unmatched)
        msg = msg.replace("Is this correct?", f"Not recognised:\n{unknown_lines}\n\nPlease edit or let us know what these are.\n\nIs this correct?")
    if rejected_minis:
        msg += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(rejected_minis)
    await _send_confirmation(update, chat_id, msg)


async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    if query.data == "b2b_extra_yes":
        pending = _pending.get(chat_id)
        if not pending:
            await query.edit_message_text("No pending order found. Please send your order again.")
            return

        _state.pop(chat_id, None)
        bread_items = _resolve_bread_history(chat_id, pending["bread_items"])
        cake_items, _ = _resolve_cake_history(chat_id, pending["cake_items"])
        for it in cake_items:
            if it.get("order_type") is None:
                it["order_type"] = "full"
                it["order_type_source"] = "default"
        bread_items, extra_rejected = _split_mini_items(bread_items, pending.get("delivery_date", ""))
        all_rejected = pending.get("rejected_minis", []) + extra_rejected
        pending["bread_items"]   = bread_items
        pending["cake_items"]    = cake_items
        pending["rejected_minis"] = all_rejected
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
                    [_cake_line(it, show_edit_hint=True) + " *(new)*" for it in cake_items]

        total = order_total(existing_bread + bread_items, existing_cake + cake_items)
        dl    = _delivery_line(pending.get("delivery_method"), pending.get("delivery_time"), pending.get("location"), pending.get("delivery_date"))

        body = "Full updated order:\n\n" + "\n".join(ex_lines + new_lines)
        body += "\n\n" + price_summary(total).replace("Subtotal:", "New total:")
        if dl:
            body += f"\n\n{dl}"
        body += "\n\nConfirm full order?"
        if all_rejected:
            body += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(all_rejected)
        await query.edit_message_text(body, reply_markup=_confirm_keyboard())

    elif query.data == "b2b_confirm":
        pending = _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        _last_confirmation.pop(chat_id, None)
        if not pending:
            await query.edit_message_text("No pending order. Please send your order again.")
            return

        await _do_confirm_order(
            chat_id, pending, context,
            lambda txt: query.edit_message_text(txt, reply_markup=None),
        )

    elif query.data == "b2b_extra_no_change":
        pending = _pending.get(chat_id)
        if not pending:
            _state.pop(chat_id, None)
            await query.edit_message_text("No pending order found. Please send your order again.")
            return

        _state[chat_id] = {"mode": "awaiting_edit"}

        bread_items  = pending.get("bread_items", [])
        cake_items   = pending.get("cake_items", [])
        ai_unmatched = pending.get("ai_unmatched", [])

        if bread_items or cake_items:
            understood = "\n".join(
                [_bread_line(it) for it in bread_items] +
                [_cake_line(it) for it in cake_items]
            )
            understood_block = f"We have:\n{understood}\n\n"
        else:
            understood_block = ""

        not_found = ("Not recognised: " + ", ".join(f"{u['qty']}x {u['item']}" for u in ai_unmatched) + "\n\n") if ai_unmatched else ""

        await query.edit_message_text(
            f"{understood_block}{not_found}"
            "Just type the items to add or correct — no need to resend your photo or document."
        )

    elif query.data == "b2b_edit":
        pending = _pending.get(chat_id)
        if not pending:
            _state.pop(chat_id, None)
            await query.edit_message_text("No pending order found. Please send your order again.")
            return

        _state[chat_id] = {"mode": "awaiting_edit"}

        bread_items    = pending.get("bread_items", [])
        cake_items     = pending.get("cake_items", [])
        ai_unmatched   = pending.get("ai_unmatched", [])

        if bread_items or cake_items:
            understood = "\n".join(
                [_bread_line(it) for it in bread_items] +
                [_cake_line(it) for it in cake_items]
            )
            understood_block = f"We have:\n{understood}\n\n"
        else:
            understood_block = ""

        if ai_unmatched:
            not_found = "Not recognised: " + ", ".join(f"{u['qty']}x {u['item']}" for u in ai_unmatched) + "\n\n"
        else:
            not_found = ""

        await query.edit_message_text(
            f"{understood_block}{not_found}"
            "Just type the items to add or correct — no need to resend your photo or document."
        )

    elif query.data == "b2b_cancel":
        pending        = _pending.get(chat_id, {})
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

            lines.append("")
            lines.append("─" * 32)
            lines.append("")
            lines.append(f"Your existing order for {_date_label(delivery_date)} is still active:")
            for ei in existing_bread + existing_cake:
                ei_line = f"  • {ei['qty']}x {ei['item']}"
                if ei.get("grams"):
                    ei_line += f" — {ei['grams']}g"
                lines.append(ei_line)
            lines.append("")
            lines.append("Would you like to keep it or cancel everything?")

            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Confirm ✓",    callback_data="b2b_keep_existing"),
                    InlineKeyboardButton("Cancel all ✗", callback_data="b2b_cancel_all"),
                ]]),
            )
        else:
            _pending.pop(chat_id, None)
            _state.pop(chat_id, None)
            await query.edit_message_text("Order cancelled.")

    elif query.data == "b2b_keep_existing":
        _pending.pop(chat_id, None)
        _state.pop(chat_id, None)
        await query.edit_message_text("Your existing order remains active. ✓")

    elif query.data == "b2b_cancel_all":
        pending       = _pending.pop(chat_id, {})
        _state.pop(chat_id, None)
        delivery_date = pending.get("delivery_date")
        if delivery_date:
            delete_b2b_orders_for_date(chat_id, delivery_date)
            delete_b2b_cake_orders_for_date(chat_id, delivery_date)
        label = _date_label(delivery_date) if delivery_date else "this delivery"
        await query.edit_message_text(f"All orders for {label} have been cancelled.")


async def handle_order_photo(bot, chat_id: int, image_bytes: bytes, message_id: int, mime_type: str = "image/jpeg", ai_items: list = None) -> None:
    """Process an order photo. ai_items may be pre-supplied by the classifier to avoid a second API call."""
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

    if needs_spec:
        _state[chat_id] = {"mode": "awaiting_cake_spec", "needs_spec": needs_spec}
        await bot.send_message(
            chat_id,
            f"Got the order from your photo! For the {', '.join(needs_spec)} — sliced or whole?",
            reply_to_message_id=message_id,
        )
        return

    if not method:
        _state[chat_id] = {"mode": "awaiting_delivery"}
        upsert_b2b_customer(chat_id, business_name)
        await bot.send_message(
            chat_id,
            "Got the order from your photo! Pickup or delivery, and what time?\n"
            "Example: Delivery at 8am  |  Pickup at 7am",
            reply_to_message_id=message_id,
        )
        return

    msg = _build_confirmation(bread_items, cake_items, method, time_str, location, delivery_date,
                              heading="Order from your photo:")
    if unmatched:
        unknown_lines = "\n".join(f"  ⚠️ {u['qty']}x {u['item']} — not on our menu" for u in unmatched)
        msg = msg.replace("Is this correct?", f"Not recognised:\n{unknown_lines}\n\nPlease edit or let us know what these are.\n\nIs this correct?")
    if photo_rejected:
        msg += "\n\n" + "─" * 32 + "\n" + _mini_rejection_note(photo_rejected)

    await _send_confirmation(bot, chat_id, msg)
