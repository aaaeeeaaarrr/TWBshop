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


def _mentioned_ids(msg) -> list:
    """Telegram user ids @-mentioned via a TAP-mention (MessageEntityMentionName carries .user_id — it pings a
    person even with no @username). A plain @username mention has no id here, so it's skipped. Best-effort —
    never raises (a parse hiccup must not drop the message)."""
    out = []
    try:
        for e in (getattr(msg, "entities", None) or []):
            uid = getattr(e, "user_id", None)
            if uid:
                out.append(int(uid))
    except Exception:
        pass
    return out


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


_ERR_TIMES: list = []          # recent processing-error timestamps
_ERR_LAST_ALERT = 0.0


def _alert_owner(text: str) -> None:
    """Throttled owner DM via the GM bot token (Bot API works regardless of any polling process —
    same pattern as the collection watchdog). The listener is a Telethon userbot, so the shared
    PTB error handler can't cover it; this closes the per-message blind spot: errors used to be
    log-only and invisible (the gm_save_concern lesson)."""
    global _ERR_LAST_ALERT
    import time as _t
    import urllib.parse
    import urllib.request
    now = _t.time()
    if now - _ERR_LAST_ALERT < 1800:
        return
    token = getattr(config, "GM_BOT_TOKEN", "") or config.BOT_TOKEN
    try:
        data = urllib.parse.urlencode({"chat_id": config.OWNER_TELEGRAM_ID,
                                       "text": "⚠ Listener: " + text}).encode()
        urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage" % token,
                               data=data, timeout=15)
        _ERR_LAST_ALERT = now
    except Exception:
        logger.exception("owner alert failed")


def _note_processing_error(chat_id) -> None:
    """Track error bursts: one transient failure is just logged; 3+ within 10 minutes means
    message COLLECTION is degrading (DB down, schema break, API change) → tell the owner."""
    import time as _t
    now = _t.time()
    _ERR_TIMES.append(now)
    del _ERR_TIMES[:-20]
    recent = [t for t in _ERR_TIMES if now - t < 600]
    if len(recent) >= 3:
        _alert_owner("%d message-processing errors in the last 10 min (latest chat %s) — "
                     "messages may not be recorded. Full tracebacks in the listener log."
                     % (len(recent), chat_id))


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
            reply_to_msg_id = getattr(getattr(msg, "reply_to", None), "reply_to_msg_id", None)

            save_ops_message(
                chat_id=event.chat_id,
                message_id=msg.id,
                chat_title=chat_title,
                sender_id=sender_id,
                sender_name=sender_name,
                text=msg.text or "",
                media_type=_classify_media(msg),
                sent_at=sent_at,
                reply_to_msg_id=reply_to_msg_id,
                mentioned_ids=_mentioned_ids(msg),
            )
            logger.info("[%s] %s: %s", chat_title, sender_name or "?", (msg.text or "")[:80])
        except Exception:
            logger.exception("Error processing message from chat %s", event.chat_id)
            _note_processing_error(event.chat_id)

    logger.info("Listening — Ctrl+C to stop")
    await client.run_until_disconnected()
