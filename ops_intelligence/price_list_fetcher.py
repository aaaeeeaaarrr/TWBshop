"""
Downloads the most recent price list files (PDFs, docs, photos) from each supplier group.
Run once; re-run any time to refresh. Uses ops_listener session (read-only, safe).
"""
import asyncio
import os
import sys
sys.path.insert(0, '/root/TWBshop')

import config
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename, MessageMediaDocument, MessageMediaPhoto

SESSION_PATH = "ops_listener"
OUTPUT_DIR = "/root/TWBshop/pricelists"
MAX_FILE_MB = 30
MAX_DOCS = 6     # per chat — covers drinks/food/alcohol splits
MAX_PHOTOS = 10  # per chat — price lists sent as photo pages

# chat_id → folder name. Add new suppliers here.
SUPPLIER_CHATS = {
    -514657145:      "Lees",
    -771475820:      "LSH",
    -680277978:      "Indoguna",
    -598194187:      "Makro",
    -593114368:      "The_Warehouse_Wine",
    -777054775:      "Grand_Place_Chocolate",
    -766343069:      "AMN_Belle_France",
    -1001670757206:  "Packaging_Supply_Store",
    -575036689:      "Dan_Meat",
    -556644892:      "Koh_Kong_Smoked_Chicken",
    -580139431:      "Drink_Shop",
    -740456627:      "Tiger_Beer",
    -436441225:      "Auskhmer_Dairy",
    -610951371:      "SHG_Mozarella",
    -4200448600:     "Flour_Supplier",
    -4229214115:     "Khmer_Ingredients",
    -4718285919:     "ThaiHuot",
    -4026357686:     "Melbourne_Coffee",
    -510737793:      "Annam_Cambodia",
    -430839748:      "OSTRA_Fine_Foods",
    -659134937:      "LIM_Pasta_Boxes",
    -4695033653:     "Betagro",
    -949802815:      "Chicken_pfoods",
    843614398:       "Coffee_Bean",
    -605607029:      "SOMA_Eggs",
    -1001580490615:  "C_Bakery_Store",
    1018669211:      "Choronai",
    1138296296:      "Choronai_Hotline",
    6332752724:      "VVC_Chocolate",
    -711904445:      "FPC_Packaging",
    5278321965:      "Supply_Lees_Personal",
    -4132634268:     "POSFlow_Support",
}


def _safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s)


async def _fetch_chat(client, chat_id: int, label: str):
    out = os.path.join(OUTPUT_DIR, label)
    os.makedirs(out, exist_ok=True)

    try:
        entity = await client.get_entity(chat_id)
    except Exception as e:
        print(f"  SKIP {label}: {e}")
        return

    docs, photos = 0, 0
    saved = []

    async for msg in client.iter_messages(entity, limit=800):
        if not msg.media:
            continue

        if isinstance(msg.media, MessageMediaDocument) and docs < MAX_DOCS:
            doc = msg.media.document
            if doc.size > MAX_FILE_MB * 1024 * 1024:
                continue
            fname = None
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    fname = attr.file_name
                    break
            if not fname:
                ext = (doc.mime_type or "application/octet-stream").split("/")[-1]
                fname = f"doc_{msg.id}.{ext}"
            fname = f"{str(msg.date)[:10]}_{_safe_name(fname)}"
            path = os.path.join(out, fname)
            if not os.path.exists(path):
                await client.download_media(msg, file=path)
            saved.append(fname)
            docs += 1

        elif isinstance(msg.media, MessageMediaPhoto) and photos < MAX_PHOTOS:
            fname = f"{str(msg.date)[:10]}_photo_{msg.id}.jpg"
            path = os.path.join(out, fname)
            if not os.path.exists(path):
                await client.download_media(msg, file=path)
            saved.append(fname)
            photos += 1

        if docs >= MAX_DOCS and photos >= MAX_PHOTOS:
            break

    if saved:
        preview = ", ".join(saved[:3]) + ("..." if len(saved) > 3 else "")
        print(f"  {label}: {len(saved)} files — {preview}")
    else:
        print(f"  {label}: no files")


async def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = TelegramClient(SESSION_PATH, config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.start(phone=config.TELETHON_PHONE)
    print(f"Fetching from {len(SUPPLIER_CHATS)} supplier chats → {OUTPUT_DIR}\n")
    for chat_id, label in SUPPLIER_CHATS.items():
        print(f"  {label}...")
        await _fetch_chat(client, chat_id, label)
    await client.disconnect()
    print("\nDone.")
