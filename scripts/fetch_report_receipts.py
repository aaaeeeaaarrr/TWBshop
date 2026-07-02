"""Download photo media from a chat using the read-only ops_listener session.

Reuses the proven, documented-safe price_list_fetcher pattern (same session,
read-only). Run ON THE SERVER while the listener is up — it is short-lived and
only reads.

Usage:
    python scripts/fetch_report_receipts.py [LIMIT]
        LIMIT omitted or 0  -> ALL photos in the chat (newest first)
        LIMIT n             -> the n most recent photos (sample)

It is idempotent: a photo already on disk is skipped, never re-downloaded.
Prints a per-file size line and a total footprint summary at the end.
"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, "/root/TWBshop")

import config
from telethon import TelegramClient

SESSION_LIVE = "/root/TWBshop/ops_listener.session"  # the live listener's session (read-only source)
CHAT_ID = -5136886404  # TWB REPORT (the daily-report group)
OUTPUT_DIR = "/root/TWBshop/receipts_archive/TWB_REPORT"


async def run(limit: int):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Work off a COPY of the live session so we never lock the SQLite file the running
    # listener writes to (a direct concurrent open raises 'database is locked'). Same
    # auth key, brief read-only connection — Telegram allows it, no logout.
    n = total = skipped = 0
    work = f"/tmp/report_archiver_{os.getpid()}"
    shutil.copyfile(SESSION_LIVE, work + ".session")
    client = TelegramClient(work, config.TELETHON_API_ID, config.TELETHON_API_HASH)
    try:
        await client.start(phone=config.TELETHON_PHONE)

        # Iterate the FULL message history (no server-side photo filter — that filter
        # undercounts older history) and grab every photo Telegram still serves.
        # Truly-deleted messages are unrecoverable (bytes were never stored).
        async for msg in client.iter_messages(CHAT_ID, limit=(limit or None)):
            if not msg.photo:
                continue
            day = str(msg.date)[:10]
            path = os.path.join(OUTPUT_DIR, f"{day}_{msg.id}.jpg")
            if os.path.exists(path):
                skipped += 1
            else:
                await client.download_media(msg, file=path)
            sz = os.path.getsize(path)
            n += 1
            total += sz
            print(f"  {os.path.basename(path)}  {sz // 1024} KB")

        await client.disconnect()
    finally:
        for ext in (".session", ".session-journal"):
            try:
                os.remove(work + ext)
            except OSError:
                pass
    avg = total / n / 1024 if n else 0
    print(
        f"\n{n} photos ({skipped} already on disk), "
        f"{total / 1024 / 1024:.1f} MB total, avg {avg:.0f} KB/photo"
    )


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    # observability law: the daily receipt-archive cron beats so a silent stop alarms via the sweep
    try:
        from core.heartbeat import beat, init_heartbeats_db
        init_heartbeats_db()
        beat("twb", "cron:fetch_report_receipts", 1560, phase="start")
    except Exception as e:
        print("heartbeat unavailable (non-fatal):", e)
    asyncio.run(run(limit))
    try:
        from core.heartbeat import beat
        beat("twb", "cron:fetch_report_receipts", 1560, phase="ok")
    except Exception:
        pass
