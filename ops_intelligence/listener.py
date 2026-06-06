"""Telethon user-account listener — streams all Telegram messages into ops_messages."""

import logging
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events
from telethon.tl.types import User

import config
from shared.database import init_ops_db, save_ops_message

logger = logging.getLogger(__name__)

SESSION_PATH = "ops_listener"

# Self-healing catch-up (session 28): on every startup, backfill whatever was missed
# while the listener was down. Telegram keeps the history; we just re-read it.
CATCHUP_LOOKBACK_DAYS = 14
CATCHUP_MAX_PER_CHAT = 3000


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


def _sender_fields(sender) -> tuple[int | None, str | None]:
    if isinstance(sender, User):
        name = " ".join(p for p in [sender.first_name or "", sender.last_name or ""] if p).strip()
        return sender.id, (name or sender.username)
    if sender is not None:
        return sender.id, (getattr(sender, "title", None) or getattr(sender, "username", None))
    return None, None


async def _catch_up(client) -> None:
    """Backfill messages missed during downtime (session 28 — the May 28/29 lesson).
    For every chat we recorded in the lookback window, fetch anything newer than the
    last stored message id and save it. Idempotent (ON CONFLICT DO NOTHING), capped
    per chat so a long outage can't stall startup forever."""
    from shared.database import _db
    since = (datetime.utcnow() - timedelta(days=CATCHUP_LOOKBACK_DAYS)).isoformat()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT chat_id, MAX(message_id) AS last_id FROM ops_messages
                           WHERE sent_at >= %s GROUP BY chat_id""", (since,))
            targets = {r["chat_id"]: r["last_id"] for r in cur.fetchall()}
    if not targets:
        return
    n_chats = n_msgs = 0
    async for dialog in client.iter_dialogs():
        last_id = targets.get(dialog.id)
        if last_id is None:
            continue
        try:
            saved = 0
            async for m in client.iter_messages(dialog.entity, min_id=int(last_id),
                                                limit=CATCHUP_MAX_PER_CHAT):
                sender_id, sender_name = _sender_fields(await m.get_sender())
                save_ops_message(
                    chat_id=dialog.id,
                    message_id=m.id,
                    chat_title=getattr(dialog.entity, "title", None) or str(dialog.id),
                    sender_id=sender_id,
                    sender_name=sender_name,
                    text=m.text or "",
                    media_type=_classify_media(m),
                    sent_at=m.date.replace(tzinfo=timezone.utc).isoformat() if m.date else None,
                )
                saved += 1
            if saved:
                n_chats += 1
                n_msgs += saved
                logger.info("catch-up: %s -> %d messages backfilled", dialog.name, saved)
        except Exception:
            logger.exception("catch-up failed for chat %s", dialog.id)
    logger.info("catch-up complete: %d messages across %d chats", n_msgs, n_chats)


async def run() -> None:
    init_ops_db()

    client = TelegramClient(SESSION_PATH, config.TELETHON_API_ID, config.TELETHON_API_HASH)

    # Connect using the existing session first — no phone needed when already authorised.
    # Only fall back to an interactive phone login if the session is dead.
    await client.connect()
    if not await client.is_user_authorized():
        if not config.TELETHON_PHONE:
            raise RuntimeError(
                "Telethon session is not authorised and TELETHON_PHONE is empty. "
                "Set the phone in secrets.py and run an interactive login once."
            )
        await client.start(phone=config.TELETHON_PHONE)

    me = await client.get_me()
    logger.info("Listener started as %s (id=%s)", me.username or me.first_name, me.id)

    # heal any gap from downtime BEFORE streaming new messages (session 28)
    try:
        await _catch_up(client)
    except Exception:
        logger.exception("catch-up pass failed (continuing to live stream)")

    @client.on(events.NewMessage)
    async def _on_message(event):
        try:
            msg = event.message
            chat = await event.get_chat()
            sender_id, sender_name = _sender_fields(await event.get_sender())

            chat_title = (
                getattr(chat, "title", None)
                or getattr(chat, "username", None)
                or str(event.chat_id)
            )

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
