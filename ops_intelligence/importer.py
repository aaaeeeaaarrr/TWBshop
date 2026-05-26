"""One-time historical message importer — pulls all history from all chats into ops_messages."""

import asyncio
import logging

from telethon import TelegramClient
from telethon.tl.types import User, Channel, Chat

import config
from shared.database import init_ops_db, save_ops_message

logger = logging.getLogger(__name__)

SESSION_PATH = "ops_importer"


def _classify_media(msg) -> str | None:
    if msg.photo:
        return "photo"
    if msg.sticker:
        return "sticker"
    if msg.voice:
        return "voice"
    if msg.video_note:
        return "video_note"
    if msg.video:
        return "video"
    if msg.document:
        return "document"
    return None


async def run_import() -> None:
    init_ops_db()

    client = TelegramClient(SESSION_PATH, config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.start(phone=config.TELETHON_PHONE)

    me = await client.get_me()
    logger.info("Importing as %s (id=%s)", me.username or me.first_name, me.id)

    dialogs = await client.get_dialogs()
    logger.info("Found %d dialogs to import", len(dialogs))

    for dialog in dialogs:
        entity = dialog.entity
        chat_id = dialog.id
        chat_title = (
            getattr(entity, "title", None)
            or getattr(entity, "username", None)
            or getattr(entity, "first_name", None)
            or str(chat_id)
        )

        count = 0
        try:
            async for msg in client.iter_messages(entity, reverse=True, limit=None):
                if not msg or not msg.date:
                    continue

                sender = await msg.get_sender()
                if isinstance(sender, User):
                    sender_id = sender.id
                    sender_name = " ".join(
                        p for p in [sender.first_name or "", sender.last_name or ""] if p
                    ).strip() or sender.username
                elif sender is not None:
                    sender_id = sender.id
                    sender_name = getattr(sender, "title", None) or getattr(sender, "username", None)
                else:
                    sender_id = None
                    sender_name = None

                from datetime import timezone
                sent_at = msg.date.replace(tzinfo=timezone.utc).isoformat()

                save_ops_message(
                    chat_id=chat_id,
                    message_id=msg.id,
                    chat_title=chat_title,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    text=msg.text or "",
                    media_type=_classify_media(msg),
                    sent_at=sent_at,
                )
                count += 1
                if count % 500 == 0:
                    logger.info("[%s] imported %d messages so far...", chat_title, count)

            logger.info("[%s] done — %d messages imported", chat_title, count)
        except Exception:
            logger.exception("[%s] failed, skipping", chat_title)

    logger.info("Import complete")
    await client.disconnect()
