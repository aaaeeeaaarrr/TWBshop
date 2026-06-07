"""One-time (server): backfill the May 28-29 outage window for the non-REPORT GM chats.
Run with the listener STOPPED."""
import asyncio
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.types import PeerChat, User

import config
from shared.database import save_ops_message

START = datetime(2026, 5, 27, 17, 0, tzinfo=timezone.utc)
END = datetime(2026, 5, 30, 0, 0, tzinfo=timezone.utc)

CHATS = [
    ("Stock Checks", -1003952029131),
    ("Supervisors", -4980513319),
    ("Management", -865916135),
    ("COMMS", getattr(config, "COMMS_CHAT_ID", None) or getattr(config, "COMMS_TRANSFERS_CHAT_ID", 0)),
]


def _media(m):
    if m.photo:
        return "photo"
    if m.video:
        return "video"
    if m.document:
        return "document"
    return None


async def _entity(client, cid):
    try:
        return await client.get_entity(cid)
    except Exception:
        return await client.get_entity(PeerChat(abs(cid)))


async def main():
    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("NOT AUTHORISED")
        return
    for label, cid in CHATS:
        if not cid:
            print(label, "no id")
            continue
        try:
            entity = await _entity(client, cid)
        except Exception as e:
            print(label, "entity failed:", e)
            continue
        saved = photos = 0
        async for m in client.iter_messages(entity, offset_date=END, reverse=False):
            if m.date < START:
                break
            if m.date > END:
                continue
            sender = await m.get_sender()
            if isinstance(sender, User):
                sid = sender.id
                sname = " ".join(p for p in [sender.first_name or "", sender.last_name or ""] if p).strip()
            else:
                sid, sname = (getattr(sender, "id", None), getattr(sender, "title", None))
            save_ops_message(cid, m.id, label, sid, sname or None, m.text or "",
                             _media(m), m.date.replace(tzinfo=timezone.utc).isoformat())
            saved += 1
            if m.photo:
                photos += 1
        print("%s: backfilled %d messages (%d photos)" % (label, saved, photos))
    await client.disconnect()

asyncio.run(main())
