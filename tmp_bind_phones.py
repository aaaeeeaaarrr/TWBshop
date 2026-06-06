"""One-time (server): bind Chuch Pisey + Sao Visal via phone->Telegram-ID (import_contacts).

Run with the listener STOPPED:
  PYTHONPATH=/root/TWBshop /root/venv/bin/python /root/TWBshop/tmp_bind_phones.py
"""
import asyncio
import json

from telethon import TelegramClient
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

import config
from shared.database import _db

PEOPLE = [
    ("Chuch Pisey", "+85586573466"),
    ("Sao Visal", "+855887829248"),
]


async def main():
    client = TelegramClient("ops_listener", config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION NOT AUTHORISED — aborting")
        return

    for name, phone in PEOPLE:
        res = await client(ImportContactsRequest([
            InputPhoneContact(client_id=0, phone=phone, first_name=name, last_name="")
        ]))
        uid = res.users[0].id if res.users else None
        print(f"{name} {phone} -> uid={uid}"
              + (f" username={getattr(res.users[0], 'username', None)}" if res.users else " (NOT ON TELEGRAM / hidden)"))
        with _db() as conn:
            with conn.cursor() as cur:
                if uid:
                    cur.execute(
                        "UPDATE staff_registry SET telegram_ids=%s, phone=%s, updated_at=NOW() "
                        "WHERE canonical_name=%s", (json.dumps([uid]), phone, name))
                else:
                    cur.execute(
                        "UPDATE staff_registry SET phone=%s, updated_at=NOW() WHERE canonical_name=%s",
                        (phone, name))

    await client.disconnect()

asyncio.run(main())
