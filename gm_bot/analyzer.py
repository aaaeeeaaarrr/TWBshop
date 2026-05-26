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
    gm_get_new_messages, gm_get_low_stock_history,
    gm_save_concern, gm_set_state, gm_get_state, gm_get_rules,
)
from shared.ai_client import _get_client, _encode

logger = logging.getLogger(__name__)

STOCK_CHECKS_CHAT = config.STOCK_CHECKS_CHAT_ID

LOW_STOCK_KW = ["almost out", "out of stock", "running low", "please buy", "please order", "no more", "finish"]
WASTE_KW = ["throw", "threw", "spoil", "expired", "expire", "cannot sale", "can't sell", "bad", "broken and looked", "wasted"]
MISTAKE_KW = ["apologize", "apologi", "mistake", "broke", "broken", "dropped", "drop", "accidentally", "accident", "sorry"]

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


def _detect_text_concerns(messages: list[dict], rules: list[dict]) -> list[dict]:
    """Detect waste, mistakes from text messages. Returns list of concern dicts."""
    concerns = []
    for msg in messages:
        text = msg.get("text") or ""
        if not text:
            continue
        sender = msg.get("sender_name") or "Unknown"
        key = "msg:%s:%s" % (msg["chat_id"] if "chat_id" in msg else STOCK_CHECKS_CHAT, msg["id"])
        t = text.lower()

        if any(kw in t for kw in WASTE_KW):
            if _matches_rules(text, "waste", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key + ":waste",
                    "concern_type": "waste",
                    "severity": "info",
                    "sender_name": sender,
                    "description": "%s reported waste/spoilage: %s" % (sender, text[:200]),
                })

        if any(kw in t for kw in MISTAKE_KW):
            if _matches_rules(text, "mistake", rules) != "ignore":
                concerns.append({
                    "source_msg_key": key + ":mistake",
                    "concern_type": "mistake",
                    "severity": "info",
                    "sender_name": sender,
                    "description": "%s reported a mistake: %s" % (sender, text[:200]),
                })

    return concerns


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

    new_messages = gm_get_new_messages(STOCK_CHECKS_CHAT, since)
    logger.info("GM analysis: %d new messages", len(new_messages))

    concerns = []

    # Text-based concerns
    concerns.extend(_detect_text_concerns(new_messages, rules))

    # Low-stock repeat detection (always runs, looks at last 14 days)
    concerns.extend(_detect_low_stock_concerns(rules))

    # Photo analysis — batch all new photos
    photo_msgs = [m for m in new_messages if m.get("media_type") == "photo"]
    if photo_msgs and config.ANTHROPIC_API_KEY:
        logger.info("GM analysis: analyzing %d photos", len(photo_msgs))
        # Group photos sent within 2 minutes of each other (same check session)
        # For now analyze individually but deduplicate by minute-bucket
        analyzed_buckets: set[str] = set()
        for msg in photo_msgs:
            sent_at = str(msg.get("sent_at", ""))[:16]  # YYYY-MM-DDTHH:MM
            bucket_key = "%s:%s" % (msg.get("sender_name", ""), sent_at)
            if bucket_key in analyzed_buckets:
                continue
            analyzed_buckets.add(bucket_key)

            # We don't have the actual photo bytes in the DB — skip vision for now
            # Photos from the Telethon listener will be downloadable once we wire that up
            # For imported HTML exports we don't have binary data in DB
            pass

    saved = 0
    for c in concerns:
        new_id = gm_save_concern(
            source_chat_id=STOCK_CHECKS_CHAT,
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
