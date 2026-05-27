"""One-time script: scan recent TWB REPORT photos and reply to unclear receipts.

Run AFTER stopping twbshop-listener (shares the Telethon session).
Restarts listener automatically when done.

Usage: python run_check_report_photos.py
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
from shared.ai_client import assess_receipt_photo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPORT_CHAT_ID = config.DAILY_REPORT_CHAT_ID
LOOKBACK = 100   # scan last N messages in the group


async def main():
    logger.info("Stopping listener service...")
    subprocess.run(["systemctl", "stop", "twbshop-listener"], check=False)
    await asyncio.sleep(2)

    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.start(phone=config.TELETHON_PHONE)

    checked = replied = skipped = 0

    logger.info("Scanning last %d messages in TWB REPORT (chat_id=%s)...", LOOKBACK, REPORT_CHAT_ID)

    async for msg in client.iter_messages(REPORT_CHAT_ID, limit=LOOKBACK):
        if not msg.photo:
            continue

        photo_bytes = await client.download_media(msg, file=bytes)
        if not photo_bytes:
            skipped += 1
            continue

        result = await assess_receipt_photo(photo_bytes)
        checked += 1

        sender = ""
        if msg.sender:
            sender = getattr(msg.sender, "first_name", "") or ""
            last = getattr(msg.sender, "last_name", "") or ""
            if last:
                sender = f"{sender} {last}".strip()

        if not result["is_receipt"]:
            logger.info("  msg %s (%s) — not a receipt, skip", msg.id, sender)
            continue

        if result["is_clear"]:
            logger.info("  msg %s (%s) — receipt OK", msg.id, sender)
            continue

        # Build a short, simple reply
        partial = result.get("readable_partial", "")
        if result.get("is_handwritten") and partial:
            reply = f"Can you tell me what this says? I can see \"{partial}\" but hard to read."
        else:
            issues = result.get("issues", [])
            if issues:
                issue_text = " and ".join(i.lower().rstrip(".") for i in issues[:2])
                reply = f"Please send this photo again — {issue_text}."
            else:
                reply = "Please send this photo again — not clear enough to record."

        # Use Telethon to reply — its IDs match, no mismatch with Bot API
        await client.send_message(REPORT_CHAT_ID, reply, reply_to=msg.id)
        replied += 1
        logger.info("  msg %s (%s) — replied: %s", msg.id, sender, reply)

        await asyncio.sleep(1)  # avoid flood wait

    await client.disconnect()

    logger.info("\nDone. Checked %d receipts, replied to %d, skipped %d.", checked, replied, skipped)

    logger.info("Restarting listener service...")
    subprocess.run(["systemctl", "start", "twbshop-listener"], check=False)
    logger.info("Listener restarted.")


asyncio.run(main())
