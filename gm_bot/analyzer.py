"""
Scans ops_messages for operational concerns and saves them to gm_concerns.
Runs on a schedule; re-entrant — already-flagged concerns are skipped.
"""
import asyncio
import base64
import logging
import re
from collections import defaultdict
from datetime import datetime, timezone

import config
from shared.database import (
    gm_get_new_messages, gm_get_new_messages_multi, gm_get_low_stock_history,
    gm_save_concern, gm_set_state, gm_get_state, gm_get_rules,
)
from shared.ai_client import _get_client, _encode, detect_concern_semantic

logger = logging.getLogger(__name__)

STOCK_CHECKS_CHAT = config.STOCK_CHECKS_CHAT_ID

# Groups scanned for operational concerns (stock/waste/mistakes/photos)
OPS_CHATS = [
    config.STOCK_CHECKS_CHAT_ID,
    config.DAILY_REPORT_CHAT_ID,
]

# Groups scanned for attendance concerns (AL, lateness, absences)
ATTENDANCE_CHATS = [
    config.SUPERVISORS_CHAT_ID,
    config.MANAGEMENT_CHAT_ID,
]

# Human-readable labels for each chat
CHAT_LABELS = {
    config.STOCK_CHECKS_CHAT_ID:  "Stock Checks",
    config.SUPERVISORS_CHAT_ID:   "Supervisors",
    config.MANAGEMENT_CHAT_ID:    "Management",
    config.COMMS_CHAT_ID:         "COMMS",
    config.DAILY_REPORT_CHAT_ID:  "Daily Report",
}

LOW_STOCK_KW = ["almost out", "out of stock", "running low", "please buy", "please order", "no more", "finish"]
WASTE_KW     = ["throw", "threw", "spoil", "expired", "expire", "cannot sale", "can't sell", "bad", "broken and looked", "wasted"]
MISTAKE_KW   = ["apologize", "apologi", "mistake", "broke", "broken", "dropped", "drop", "accidentally", "accident", "sorry"]
ATTENDANCE_KW = [
    "late", "lateness", "tardy", "annual leave", "day off", "off today", "off tomorrow",
    "coming late", "can't come", "cannot come", "sick", "not feeling well",
    "permission", "absent", "absence", "emergency leave", "won't come", "half day",
    "want off", "need off", " al ", "take al", "taking al", "use al",
]
PAYBACK_KW = ["pay back", "payback", "pay-back", "make up time", "compensate", "owe time"]

_PHOTO_SYSTEM = (
    "You analyze photos from a bakery/restaurant operations group called 'Stock Checks +Cleans +Mistakes'. "
    "Assess cleanliness, safety, and operational quality. Be specific and concise. "
    "Return JSON: {\"concern\": true/false, \"severity\": \"info\"|\"warning\"|\"critical\", "
    "\"summary\": \"one sentence\", \"details\": \"specific observations\"}"
)


def _matches_rules(text: str, concern_type: str, rules: list[dict]) -> str | None:
    """Return 'ignore' if a rule suppresses this concern, else None."""
    text_lower = text.lower()
    for rule in rules:
        if rule["concern_type"] and rule["concern_type"] != concern_type:
            continue
        if rule["pattern"].lower() in text_lower and rule["action"] == "ignore":
            return "ignore"
    return None


def _extract_low_stock_items(text: str) -> str:
    """Pull the item list from a low-stock message."""
    text = re.sub(r"dear boss.*?inform.*?(you that|that)\s*", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"(we are|we're|i am|i'm)?\s*almost out\s*(of)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(please\s*(help us\s*)?(buy|order)\s*more.*|thank.*)", "", text, flags=re.IGNORECASE)
    return text.strip()[:200]


async def _analyze_photo(image_bytes: bytes) -> dict:
    try:
        resp = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=_PHOTO_SYSTEM,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(image_bytes)}},
                {"type": "text", "text": "Assess this photo."},
            ]}],
        )
        import json as _json
        text = resp.content[0].text
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end != -1:
            return _json.loads(text[start:end+1])
    except Exception as e:
        logger.error("Photo analysis failed: %s", e)
    return {"concern": False}


def _detect_attendance_concerns(messages: list[dict], rules: list[dict]) -> list[dict]:
    """Detect AL requests, lateness, absences from Supervisors/Management messages."""
    concerns = []
    for msg in messages:
        text = msg.get("text") or ""
        if not text or len(text) < 5:
            continue
        sender = msg.get("sender_name") or "Unknown"
        chat_id = msg.get("chat_id", 0)
        chat_label = CHAT_LABELS.get(chat_id, "Group")
        key = "msg:%s:%s" % (chat_id, msg["id"])
        t = text.lower()

        if any(kw in t for kw in ATTENDANCE_KW):
            if _matches_rules(text, "staffing", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key + ":staffing",
                    "concern_type": "staffing",
                    "severity": "info",
                    "sender_name": sender,
                    "source_chat_id": chat_id,
                    "description": "[%s] %s — attendance/leave: %s" % (chat_label, sender, text[:200]),
                })

        if any(kw in t for kw in PAYBACK_KW):
            if _matches_rules(text, "staffing", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key + ":payback",
                    "concern_type": "staffing",
                    "severity": "info",
                    "sender_name": sender,
                    "source_chat_id": chat_id,
                    "description": "[%s] %s — pay-back time: %s" % (chat_label, sender, text[:200]),
                })

    return concerns


# Human label per concern type for the concern card description.
_CONCERN_VERB = {
    "waste":     "reported waste/spoilage",
    "mistake":   "reported a mistake",
    "low_stock": "flagged low stock",
}


def _keyword_text_concerns(messages: list[dict], rules: list[dict]) -> list[dict]:
    """Free fallback: detect waste/mistakes by keyword. Used when the API key is
    empty, semantic detection is disabled, or an AI call errors out."""
    concerns = []
    for msg in messages:
        text = msg.get("text") or ""
        if not text:
            continue
        sender = msg.get("sender_name") or "Unknown"
        chat_id = msg.get("chat_id", STOCK_CHECKS_CHAT)
        chat_label = CHAT_LABELS.get(chat_id, "")
        prefix = "[%s] " % chat_label if chat_label else ""
        key = "msg:%s:%s" % (chat_id, msg["id"])
        t = text.lower()

        if any(kw in t for kw in WASTE_KW):
            if _matches_rules(text, "waste", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key + ":waste",
                    "concern_type": "waste",
                    "severity": "info",
                    "sender_name": sender,
                    "source_chat_id": chat_id,
                    "description": "%s%s reported waste/spoilage: %s" % (prefix, sender, text[:200]),
                })

        if any(kw in t for kw in MISTAKE_KW):
            if _matches_rules(text, "mistake", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key + ":mistake",
                    "concern_type": "mistake",
                    "severity": "info",
                    "sender_name": sender,
                    "source_chat_id": chat_id,
                    "description": "%s%s reported a mistake: %s" % (prefix, sender, text[:200]),
                })

    return concerns


def _worth_checking(text: str) -> bool:
    """Cheap free pre-gate: skip messages not worth an AI call (empty, numbers-only,
    or trivial one-word noise). Everything else is judged by meaning."""
    t = (text or "").strip()
    if len(t) < 6:
        return False
    # Numbers / prices / counts only — stock-sheet rows, not prose
    if not re.search(r"[A-Za-zក-៿]", t):
        return False
    words = re.findall(r"\w+", t)
    if len(words) < 2:
        return False
    return True


def _semantic_concern_dict(msg: dict, result: dict) -> dict | None:
    """Shape an AI result into a concern dict, or None if it should be dropped."""
    ctype = result.get("concern_type")
    if not result.get("is_concern") or ctype not in ("waste", "mistake", "low_stock"):
        return None
    text = msg.get("text") or ""
    sender = msg.get("sender_name") or "Unknown"
    chat_id = msg.get("chat_id", STOCK_CHECKS_CHAT)
    chat_label = CHAT_LABELS.get(chat_id, "")
    prefix = "[%s] " % chat_label if chat_label else ""
    verb = _CONCERN_VERB.get(ctype, "flagged an issue")
    return {
        "source_msg_key": "msg:%s:%s:%s" % (chat_id, msg["id"], ctype),
        "concern_type": ctype,
        "severity": result.get("severity", "info"),
        "sender_name": sender,
        "source_chat_id": chat_id,
        "description": "%s%s %s: %s" % (prefix, sender, verb, text[:200]),
    }


async def _semantic_text_concerns(messages: list[dict], rules: list[dict],
                                  detector=None) -> list[dict]:
    """Meaning-based waste/mistake/low-stock detection. `detector` is injectable
    for tests; defaults to the Haiku semantic detector. Per-message AI errors fall
    back to the keyword scan so a concern is never silently dropped."""
    detect = detector or detect_concern_semantic
    concerns = []
    for msg in messages:
        text = msg.get("text") or ""
        if not _worth_checking(text):
            continue
        result = await detect(text)
        if result.get("_error"):
            concerns.extend(_keyword_text_concerns([msg], rules))
            continue
        concern = _semantic_concern_dict(msg, result)
        if concern is None:
            continue
        if _matches_rules(text, concern["concern_type"], rules) == "ignore":
            continue
        concerns.append(concern)
    return concerns


def _semantic_enabled() -> bool:
    return bool(getattr(config, "GM_SEMANTIC_CONCERNS", True) and config.ANTHROPIC_API_KEY)


async def detect_text_concerns(messages: list[dict], rules: list[dict]) -> list[dict]:
    """Dispatch to semantic detection when enabled, else the free keyword scan."""
    if _semantic_enabled():
        return await _semantic_text_concerns(messages, rules)
    return _keyword_text_concerns(messages, rules)


async def analyze_live_message(chat_id: int, msg_id: int, sender: str, text: str) -> list[dict]:
    """Real-time analysis of a single group message. Returns concern dicts (text-based only)."""
    rules = gm_get_rules()
    fake_msg = {"id": str(msg_id), "chat_id": chat_id, "text": text, "sender_name": sender}
    return await detect_text_concerns([fake_msg], rules)


def _detect_low_stock_concerns(rules: list[dict]) -> list[dict]:
    """Detect items flagged as low stock for 3+ consecutive days."""
    threshold = config.GM_LOW_STOCK_THRESHOLD_DAYS
    history = gm_get_low_stock_history(STOCK_CHECKS_CHAT, since_days=14)

    # Group by sender
    by_sender = defaultdict(list)
    for row in history:
        by_sender[row["sender_name"]].append(row)

    concerns = []
    for sender, rows in by_sender.items():
        days = sorted(set(str(r["day"]) for r in rows))
        if len(days) >= threshold:
            # Take the most recent message text as the sample
            latest = sorted(rows, key=lambda r: str(r["day"]))[-1]
            items_text = _extract_low_stock_items(latest["text"] or "")
            key = "lowstock:%s:%s" % (sender, days[-1])
            desc = "%s flagged low stock for %d days in a row.\nItems: %s" % (sender, len(days), items_text or "(see photo)")
            if _matches_rules(desc, "low_stock", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key,
                    "concern_type": "low_stock",
                    "severity": "warning" if len(days) >= 5 else "info",
                    "sender_name": sender,
                    "description": desc,
                })
    return concerns


async def run_analysis() -> int:
    """Main entry point. Returns number of new concerns saved."""
    rules = gm_get_rules()
    since = gm_get_state("last_analyzed") or "2026-01-01T00:00:00+00:00"
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("GM analysis: scanning messages since %s", since[:16])

    # Ops groups: waste, mistakes, low stock, photos
    ops_messages = gm_get_new_messages_multi(OPS_CHATS, since)
    # Attendance groups: AL, lateness, absences
    attendance_messages = gm_get_new_messages_multi(ATTENDANCE_CHATS, since)

    total = len(ops_messages) + len(attendance_messages)
    logger.info("GM analysis: %d new messages (%d ops, %d attendance)",
                total, len(ops_messages), len(attendance_messages))

    concerns = []

    # Text-based ops concerns (waste, mistakes) — semantic when enabled, else keyword
    concerns.extend(await detect_text_concerns(ops_messages, rules))

    # Attendance concerns (AL, lateness, pay-back)
    concerns.extend(_detect_attendance_concerns(attendance_messages, rules))

    # Low-stock repeat detection (Stock Checks only, last 14 days)
    concerns.extend(_detect_low_stock_concerns(rules))

    # Photo analysis — ops groups only
    photo_msgs = [m for m in ops_messages if m.get("media_type") == "photo"]
    if photo_msgs and config.ANTHROPIC_API_KEY:
        logger.info("GM analysis: analyzing %d photos", len(photo_msgs))
        analyzed_buckets: set[str] = set()
        for msg in photo_msgs:
            sent_at = str(msg.get("sent_at", ""))[:16]
            bucket_key = "%s:%s" % (msg.get("sender_name", ""), sent_at)
            if bucket_key in analyzed_buckets:
                continue
            analyzed_buckets.add(bucket_key)
            # Vision analysis wired up once Telethon downloads photos to disk
            pass

    saved = 0
    for c in concerns:
        new_id = gm_save_concern(
            source_chat_id=c.get("source_chat_id", STOCK_CHECKS_CHAT),
            source_msg_key=c["source_msg_key"],
            concern_type=c["concern_type"],
            severity=c["severity"],
            sender_name=c.get("sender_name"),
            description=c["description"],
        )
        if new_id:
            saved += 1

    gm_set_state("last_analyzed", now_iso)
    logger.info("GM analysis: %d new concerns saved", saved)
    return saved
