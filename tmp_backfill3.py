"""One-time (server): backfill Supervisors + Management via dialog scan (basic groups)."""
import asyncio
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.types import User

import config
from shared.database import save_ops_message

START = datetime(2026, 5, 27, 17, 0, tzinfo=timezone.utc)
END = datetime(2026, 5, 30, 0, 0, tzinfo=timezone.utc)
WANT = {-4980513319: "Supervisors", -865916135: "Management"}


def _media(m):
    if m.photo:
        return "photo"
    if m.video:
        return "video"
    if m.document:
        return "document"
    return None


async def main():
    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("NOT AUTHORISED")
        return
    found = {}
    async for d in client.iter_dialogs():
        if d.id in WANT:
            found[d.id] = d.entity
        if len(found) == len(WANT):
            break
    for cid, label in WANT.items():
        ent = found.get(cid)
        if ent is None:
            print(label, "dialog not found")
            continue
        saved = 0
        async for m in client.iter_messages(ent, offset_date=END, reverse=False):
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
        print("%s: backfilled %d" % (label, saved))
    await client.disconnect()

asyncio.run(main())
