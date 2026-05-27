"""One-time script: scan TWB REPORT for already-sent clarification questions and
import any staff replies into the receipt_clarifications DB table.

The historical scan sent questions via Telethon (personal account), so those
clarifications were never registered in the DB. This script finds them and
backfills the answers so the GM bot can learn from them going forward.

Run AFTER stopping twbshop-listener (shares the Telethon session).
Restarts listener automatically when done.

Usage: python run_backfill_clarifications.py
"""
import asyncio
import logging
import os
import subprocess
import sys
if not os.path.exists("secrets.py"):
    sys.exit("Secrets missing — say 'pull' to Claude Code")

sys.path.insert(0, "/root/TWBshop")

from telethon import TelegramClient

import config
from shared.database import receipt_upsert_answered

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPORT_CHAT_ID = config.DAILY_REPORT_CHAT_ID
LOOKBACK = 200   # scan last N messages to find questions + replies
QUESTION_MARKER = "Can you tell me what this says?"


async def main():
    logger.info("Stopping listener service...")
    subprocess.run(["systemctl", "stop", "twbshop-listener"], check=False)
    await asyncio.sleep(2)

    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.start(phone=config.TELETHON_PHONE)

    # First pass: collect all clarification question messages (sent by the personal account)
    questions: dict[int, dict] = {}  # msg_id → {question, photo_msg_id}

    logger.info("Scanning last %d messages for clarification questions...", LOOKBACK)
    async for msg in client.iter_messages(REPORT_CHAT_ID, limit=LOOKBACK):
        text = msg.message or ""
        if QUESTION_MARKER in text:
            # This is a clarification question; the photo it was replying to is msg.reply_to_msg_id
            questions[msg.id] = {
                "question": text,
                "photo_msg_id": msg.reply_to_msg_id or msg.id,
                "question_msg_id": msg.id,
            }
            logger.info("  Found question msg %s: %s", msg.id, text[:80])

    if not questions:
        logger.info("No clarification questions found in last %d messages.", LOOKBACK)
    else:
        logger.info("Found %d clarification question(s). Looking for replies...", len(questions))

    # Second pass: find replies to those question messages
    saved = 0
    async for msg in client.iter_messages(REPORT_CHAT_ID, limit=LOOKBACK):
        if not msg.reply_to_msg_id:
            continue
        if msg.reply_to_msg_id not in questions:
            continue
        text = (msg.message or "").strip()
        if not text:
            continue

        q = questions[msg.reply_to_msg_id]
        sender = ""
        if msg.sender:
            sender = getattr(msg.sender, "first_name", "") or ""
            last = getattr(msg.sender, "last_name", "") or ""
            if last:
                sender = f"{sender} {last}".strip()

        receipt_upsert_answered(
            chat_id=REPORT_CHAT_ID,
            photo_msg_id=q["photo_msg_id"],
            bot_msg_id=q["question_msg_id"],
            question=q["question"],
            answer=text,
            sender_name=sender,
        )
        saved += 1
        logger.info("  Saved: Q msg %s ← reply '%s' from %s", msg.reply_to_msg_id, text[:60], sender)

    await client.disconnect()

    logger.info("\nDone. Saved %d answered clarification(s) to DB.", saved)

    logger.info("Restarting listener service...")
    subprocess.run(["systemctl", "start", "twbshop-listener"], check=False)
    logger.info("Listener restarted.")


asyncio.run(main())
