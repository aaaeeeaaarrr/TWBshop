"""One-time (server): backfill May 28-29 REPORT history + parse the 4 missing daily
reports + dedupe the GM-bot/listener double-written chats. Run with listener STOPPED."""
import asyncio
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.types import PeerChat, User

import config
from gm_bot import finance
from shared.database import (
    dedupe_ops_messages,
    gm_daily_report_message_ids,
    save_daily_report,
    save_ops_message,
)

CHAT = -5136886404
START = datetime(2026, 5, 27, 23, 0, tzinfo=timezone.utc)
END = datetime(2026, 5, 29, 23, 30, tzinfo=timezone.utc)

GM_CHATS = [
    ("REPORT", -5136886404),
    ("Stock Checks", -1003952029131),
    ("Supervisors", config.SUPERVISORS_CHAT_ID),
    ("Management", config.MANAGEMENT_CHAT_ID),
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


async def main():
    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("NOT AUTHORISED")
        return
    entity = await client.get_entity(PeerChat(5136886404))

    saved = reports = 0
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
        save_ops_message(CHAT, m.id, "TWB REPORT", sid, sname or None,
                         m.text or "", _media(m),
                         m.date.replace(tzinfo=timezone.utc).isoformat())
        saved += 1
        text = m.text or ""
        parsed = finance.parse_report_text(text)
        if finance.is_daily_report(parsed):
            computed = finance.recompute(parsed)
            rid = save_daily_report(
                business_day=finance.business_day_for(m.date).isoformat(),
                report_kind=finance.classify_report(m.date),
                source_chat_id=CHAT,
                source_message_id=m.id,
                posted_at=m.date.isoformat(),
                raw_text=text,
                raw=parsed,
                computed=computed,
            )
            reports += 1
            print("report stored: id=%s day=%s kind=%s math_ok=%s" % (
                rid, finance.business_day_for(m.date), finance.classify_report(m.date),
                computed.get("math_ok")))
    print("backfilled %d messages, %d reports" % (saved, reports))
    await client.disconnect()

    for label, cid in GM_CHATS:
        if not cid:
            print("skip", label, "(no chat id)")
            continue
        prefer = gm_daily_report_message_ids(cid)
        dry = dedupe_ops_messages(cid, prefer_message_ids=prefer, dry_run=True)
        if dry["groups"]:
            res = dedupe_ops_messages(cid, prefer_message_ids=prefer, dry_run=False)
            print("dedupe %s: %d groups -> deleted %d" % (label, res["groups"], res["deleted"]))
        else:
            print("dedupe %s: clean" % label)

asyncio.run(main())
