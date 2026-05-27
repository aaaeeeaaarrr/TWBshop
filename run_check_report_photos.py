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

import httpx
from telethon import TelegramClient

import config
from shared.ai_client import assess_receipt_photo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPORT_CHAT_ID = config.DAILY_REPORT_CHAT_ID
LOOKBACK = 100   # scan last N messages in the group
BOT_API  = f"https://api.telegram.org/bot{config.GM_BOT_TOKEN}"


async def main():
    logger.info("Stopping listener service...")
    subprocess.run(["systemctl", "stop", "twbshop-listener"], check=False)
    await asyncio.sleep(2)

    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.start(phone=config.TELETHON_PHONE)

    checked = unclear = skipped = 0

    logger.info("Scanning last %d messages in TWB REPORT (chat_id=%s)...", LOOKBACK, REPORT_CHAT_ID)

    async with httpx.AsyncClient(timeout=15) as http:
        async for msg in client.iter_messages(REPORT_CHAT_ID, limit=LOOKBACK):
            if not msg.photo:
                continue

            photo_bytes = await client.download_media(msg, file=bytes)
            if not photo_bytes:
                skipped += 1
                continue

            result = await assess_receipt_photo(photo_bytes)
            checked += 1

            if not result["is_receipt"]:
                logger.info("  msg %s — not a receipt, skip", msg.id)
                continue

            if result["is_clear"]:
                logger.info("  msg %s — receipt OK", msg.id)
                continue

            # Unclear receipt — reply in the group
            issues = ", ".join(result["issues"]) if result["issues"] else "photo not clear"
            reply_text = f"📷 Please resend — {issues}. Need a clear photo to record this expense."

            resp = await http.post(f"{BOT_API}/sendMessage", json={
                "chat_id": REPORT_CHAT_ID,
                "text": reply_text,
                "reply_to_message_id": msg.id,
            })
            if resp.status_code == 200:
                unclear += 1
                logger.info("  msg %s — unclear receipt, replied: %s", msg.id, issues)
            else:
                logger.warning("  msg %s — reply failed: %s", msg.id, resp.text[:200])

    await client.disconnect()

    logger.info("\nDone. Checked %d receipts, replied to %d unclear, skipped %d.", checked, unclear, skipped)

    logger.info("Restarting listener service...")
    subprocess.run(["systemctl", "start", "twbshop-listener"], check=False)
    logger.info("Listener restarted.")


asyncio.run(main())
