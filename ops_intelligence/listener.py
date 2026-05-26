"""Telethon user-account listener — streams all Telegram messages into ops_messages."""

import logging
from datetime import timezone

from telethon import TelegramClient, events
from telethon.tl.types import User

import config
from shared.database import init_ops_db, save_ops_message

logger = logging.getLogger(__name__)

SESSION_PATH = "ops_listener"


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


async def run() -> None:
    init_ops_db()

    client = TelegramClient(SESSION_PATH, config.TELETHON_API_ID, config.TELETHON_API_HASH)
    await client.start(phone=config.TELETHON_PHONE)

    me = await client.get_me()
    logger.info("Listener started as %s (id=%s)", me.username or me.first_name, me.id)

    @client.on(events.NewMessage)
    async def _on_message(event):
        try:
            msg = event.message
            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_title = (
                getattr(chat, "title", None)
                or getattr(chat, "username", None)
                or str(event.chat_id)
            )

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

            sent_at = msg.date.replace(tzinfo=timezone.utc).isoformat() if msg.date else None

            save_ops_message(
                chat_id=event.chat_id,
                message_id=msg.id,
                chat_title=chat_title,
                sender_id=sender_id,
                sender_name=sender_name,
                text=msg.text or "",
                media_type=_classify_media(msg),
                sent_at=sent_at,
            )
            logger.info("[%s] %s: %s", chat_title, sender_name or "?", (msg.text or "")[:80])
        except Exception:
            logger.exception("Error processing message from chat %s", event.chat_id)

    logger.info("Listening — Ctrl+C to stop")
    await client.run_until_disconnected()
