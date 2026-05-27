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

    checked = skipped = 0
    # List of (sender_name, issues_str) for unclear receipts
    unclear_receipts: list[tuple[str, str]] = []

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
        if not sender:
            sender = "Someone"

        if not result["is_receipt"]:
            logger.info("  msg %s (%s) — not a receipt, skip", msg.id, sender)
            continue

        if result["is_clear"]:
            logger.info("  msg %s (%s) — receipt OK", msg.id, sender)
            continue

        issues = ", ".join(result["issues"]) if result["issues"] else "photo not clear"
        logger.info("  msg %s (%s) — unclear: %s", msg.id, sender, issues)
        unclear_receipts.append((sender, issues))

    await client.disconnect()

    logger.info("\nDone. Checked %d receipts, %d unclear, skipped %d.", checked, len(unclear_receipts), skipped)

    if unclear_receipts:
        # Build one general message — no reply_to_message_id (avoids Telethon/Bot API ID mismatch)
        lines = ["Some receipt photos were not clear enough to record:"]
        seen = set()
        for sender, issues in unclear_receipts:
            key = f"{sender}:{issues}"
            if key not in seen:
                lines.append(f"• {sender} — {issues}")
                seen.add(key)
        lines.append("\nPlease check your recent photos and send again if not clear. Thank you.")
        message = "\n".join(lines)

        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.post(f"{BOT_API}/sendMessage", json={
                "chat_id": REPORT_CHAT_ID,
                "text": message,
            })
        if resp.status_code == 200:
            logger.info("Sent group summary message for %d unclear receipts.", len(unclear_receipts))
        else:
            logger.warning("Failed to send group message: %s", resp.text[:200])
    else:
        logger.info("All receipts were clear — no message needed.")

    logger.info("Restarting listener service...")
    subprocess.run(["systemctl", "start", "twbshop-listener"], check=False)
    logger.info("Listener restarted.")


asyncio.run(main())
