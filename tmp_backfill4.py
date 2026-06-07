"""Find Supervisors/Management dialogs by title, show their telethon ids, backfill."""
import asyncio
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.types import User

import config
from shared.database import save_ops_message

START = datetime(2026, 5, 27, 17, 0, tzinfo=timezone.utc)
END = datetime(2026, 5, 30, 0, 0, tzinfo=timezone.utc)
SAVE_AS = {"supervisor": -4980513319, "management": -865916135}


def _media(m):
    if m.photo:
        return "photo"
    return "document" if m.document else ("video" if m.video else None)


async def main():
    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.connect()
    targets = []
    async for d in client.iter_dialogs():
        t = (d.title or "").lower()
        if "supervisor" in t or "management" in t:
            print("dialog: id=%s title=%r" % (d.id, d.title))
            targets.append(d)
    for d in targets:
        key = "supervisor" if "supervisor" in (d.title or "").lower() else "management"
        cid = SAVE_AS[key]
        saved = 0
        async for m in client.iter_messages(d.entity, offset_date=END, reverse=False):
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
            save_ops_message(cid, m.id, d.title, sid, sname or None, m.text or "",
                             _media(m), m.date.replace(tzinfo=timezone.utc).isoformat())
            saved += 1
        print("%s (saved as %s): backfilled %d" % (d.title, cid, saved))
    await client.disconnect()

asyncio.run(main())
