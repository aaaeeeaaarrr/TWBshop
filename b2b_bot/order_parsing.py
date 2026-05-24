"""B2B order parsing — text/image matching, history resolution, and confirmation formatting."""

import re
import difflib
import logging
from datetime import date, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from b2b_bot.menu import B2B_MENU, ALIAS_MAP, INSTANT_BREAD_ITEMS, MINI_ITEMS
from b2b_bot.cake_menu import B2B_CAKE_MENU, CAKE_ALIAS_MAP
from shared.ai_client import extract_b2b_order_from_image, parse_b2b_order_text
from b2b_bot.pricing import item_price, order_total, price_summary
from shared.database import get_b2b_last_order_item, get_b2b_cake_last_order_item

logger = logging.getLogger(__name__)

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
_SLICED_RE      = re.compile(r'\b(sliced?|cut|in\s+slices?)\b', re.IGNORECASE)
_WHOLE_RE       = re.compile(r'\b(whole|unsliced|full\s+cake|not\s+sliced)\b', re.IGNORECASE)
_TRAY_RE        = re.compile(r'\b(tray|full\s+tray)\b', re.IGNORECASE)
_SLICE_COUNT_RE = re.compile(r'(\d+)\s*(?:slices?|cuts?|pieces?|pcs?)', re.IGNORECASE)
_ITEM_CODE_RE   = re.compile(r'^[A-Z0-9][A-Z0-9\-]{2,}:\s*', re.IGNORECASE)
_PARENS_RE      = re.compile(r'\s*\([^)]*\)')

_CONFIRM_WORDS = frozenset({"yes", "confirm", "confirmed", "ok", "okay", "yep", "yeah", "correct", "good", "fine"})
_CANCEL_WORDS  = frozenset({"no", "cancel", "nope", "nah", "nevermind", "stop"})
_EDIT_WORDS    = frozenset({"edit", "change", "modify", "wrong", "incorrect", "fix"})

_ALL_MENU_ITEMS: list[str] = list(B2B_MENU.keys()) + list(B2B_CAKE_MENU.keys())


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
    if cake_category == "C":
        return "piece", None
    if cake_category == "B":
        return ("tray", None) if _TRAY_RE.search(text) else ("piece", None)
    if _WHOLE_RE.search(text):
        return "full", None
    slice_count_m = _SLICE_COUNT_RE.search(text)
    if slice_count_m:
        return "sliced", int(slice_count_m.group(1))
    if _SLICED_RE.search(text):
        return "sliced", None
    return None, None


def _parse_order(raw: str) -> tuple[list[dict], list[dict], list[dict]]:
    text = _strip_noise(raw.lower().strip())
    bread_items: list[dict] = []
    cake_items:  list[dict] = []
    unmatched:   list[dict] = []

    for part in re.split(r",|\band\b|\n", text):
        part = _strip_noise(part.strip())
        if not part:
            continue

        qty = 1
        m = re.match(r"^(\d+)\s+(.+)$", part)
        if m:
            qty, part = int(m.group(1)), m.group(2).strip()
        else:
            wm = re.match(r"^(" + "|".join(_WORD_NUMBERS) + r")\s+(.+)$", part)
            if wm:
                qty, part = _WORD_NUMBERS[wm.group(1)], wm.group(2).strip()

        grams, part_no_grams = _extract_grams(part)

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

        canonical, leftover = _match_cake(part_no_grams)
        if not canonical:
            canonical, leftover = _match_cake(part)

        if canonical:
            cake_def = B2B_CAKE_MENU[canonical]
            order_type, slices = _extract_cake_spec(part, cake_def["cake_category"])
            cake_items.append({
                "item": canonical, "qty": qty,
                "cake_category": cake_def["cake_category"],
                "order_type": order_type, "slices": slices,
            })
            continue

        logger.warning("B2B UNMATCHED: %s", part)
        _log_unmatched(part)
        unmatched.append({"item": part, "qty": qty})

    return bread_items, cake_items, unmatched


def _combine_bread(items: list[dict]) -> list[dict]:
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
    valid, rejected = [], []
    try:
        days_ahead = (date.fromisoformat(delivery_date) - date.today()).days
    except (ValueError, TypeError):
        days_ahead = 1
    for it in bread_items:
        item_def = B2B_MENU.get(it["item"], {})
        min_qty   = item_def.get("min_quantity")
        advance_h = item_def.get("advance_hours")
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
    bread, cake, unmatched = [], [], []
    for it in ai_items:
        raw = it.get("item", "").strip()
        qty = max(1, int(it.get("qty", 1)))

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


async def _parse_order_ai(text: str) -> tuple[list[dict], list[dict], list[dict]]:
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
        pass

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


def _build_confirmed_text(
    bread_items: list[dict],
    cake_items:  list[dict],
    method:        str | None,
    time_str:      str | None,
    location:      str | None,
    delivery_date: str | None,
    from_user=None,
) -> str:
    mention = from_user.mention_html() if from_user else "someone"
    parts = [f"✓ Order confirmed by {mention}", ""]
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
    return "\n".join(parts)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Confirm ✓", callback_data="b2b_confirm"),
        InlineKeyboardButton("Edit ✗",    callback_data="b2b_edit"),
        InlineKeyboardButton("Cancel",    callback_data="b2b_cancel"),
    ]])


async def _send_confirmation(update_or_bot, chat_id: int, text: str) -> None:
    from b2b_bot.order_handlers import _last_confirmation
    from shared.database import get_last_confirmation_msg, set_last_confirmation_msg
    bot = update_or_bot if not hasattr(update_or_bot, "message") else update_or_bot.message._bot
    old_msg_id = _last_confirmation.get(chat_id) or get_last_confirmation_msg(chat_id)
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
    set_last_confirmation_msg(chat_id, sent.message_id)


def _parse_delivery_text(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    method = None
    if "delivery" in lower:
        method = "delivery"
    elif any(w in lower for w in ("pickup", "pick up", "pick-up", "collect")):
        method = "pickup"
    m = _TIME_RE.search(text)
    return method, (m.group(1).strip() if m else None)
