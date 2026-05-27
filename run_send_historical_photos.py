"""
Send historical gm_concerns to owner with matched local photos.

Runs LOCALLY (not on server) because the export photos live on this PC.
For each unsent concern:
  1. Parse ops_messages.id from source_msg_key
  2. Look up sender_name + sent_at from ops_messages
  3. Find local photo files from same sender within ±10 min
  4. Send photos + concern card (with review buttons) to owner
  5. Mark concern as sent in DB

Usage: python run_send_historical_photos.py [--dry-run] [--limit N] [--sender NAME]
"""
import sys, os, re, asyncio, argparse, io
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Papa\TWBshop")

import config
from secrets import GM_BOT_TOKEN
from shared.database import _db, gm_mark_sent

from telegram import Bot, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup

PHOTO_DIR = r"C:\Users\Papa\Downloads\Telegram Desktop\StockGroupNew\Stock Group Nov1 to May27 2026\photos"
HTML_DIR  = r"C:\Users\Papa\Downloads\Telegram Desktop\StockGroupNew\Stock Group Nov1 to May27 2026"
HTML_FILES = [f"messages{'' if i == 1 else i}.html" for i in range(1, 7)]
WINDOW_SECS = 600   # 10-minute photo window each side
RATE_DELAY  = 0.5   # seconds between Telegram API calls


def _safe_print(s: str) -> None:
    print(s, flush=True)


# ─── HTML parsing ─────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    import html as _html
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return _html.unescape(text).strip()


def build_photo_sender_map() -> dict[str, str]:
    """
    Parse all HTML export files and return {photo_basename: sender_name}.
    Carries sender forward for consecutive (joined) messages that lack from_name.
    """
    photo_sender: dict[str, str] = {}
    current_sender = "Unknown"

    for fname in HTML_FILES:
        path = os.path.join(HTML_DIR, fname)
        if not os.path.exists(path):
            print(f"  [skip] {fname} not found")
            continue

        with open(path, encoding="utf-8") as f:
            html = f.read()

        for block in re.split(r"(?=<div class=\"message default)", html):
            sender_m = re.search(r'<div class="from_name">\s*(.*?)\s*</div>', block, re.DOTALL)
            if sender_m:
                current_sender = _strip_html(sender_m.group(1))

            for m in re.finditer(r'photos/(photo_[^"\'<>\s]+\.jpg)', block):
                basename = m.group(1)
                if "_thumb" not in basename:
                    photo_sender[basename] = current_sender

    return photo_sender


# ─── Photo timestamp parsing ──────────────────────────────────────────────────

def photo_utc(basename: str) -> datetime | None:
    """Parse UTC datetime from photo filename (local time is UTC+7)."""
    m = re.search(r"@(\d{2})-(\d{2})-(\d{4})_(\d{2})-(\d{2})-(\d{2})\.jpg$", basename)
    if not m:
        return None
    day, month, year, hour, minute, sec = (int(x) for x in m.groups())
    local_dt = datetime(year, month, day, hour, minute, sec)
    return (local_dt - timedelta(hours=7)).replace(tzinfo=timezone.utc)


# ─── Database helpers ─────────────────────────────────────────────────────────

def get_unsent_concerns(sender_filter: str | None = None) -> list[dict]:
    with _db() as conn:
        with conn.cursor() as cur:
            if sender_filter:
                cur.execute("""
                    SELECT id, source_chat_id, source_msg_key, concern_type,
                           severity, sender_name, description, detected_at
                    FROM gm_concerns
                    WHERE sent_msg_id IS NULL AND review_action IS NULL
                      AND sender_name ILIKE %s
                    ORDER BY detected_at ASC
                """, (f"%{sender_filter}%",))
            else:
                cur.execute("""
                    SELECT id, source_chat_id, source_msg_key, concern_type,
                           severity, sender_name, description, detected_at
                    FROM gm_concerns
                    WHERE sent_msg_id IS NULL AND review_action IS NULL
                    ORDER BY detected_at ASC
                """)
            return [dict(r) for r in cur.fetchall()]


def get_ops_message(ops_id: int) -> dict | None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, message_id, sender_name, sent_at, text, media_type FROM ops_messages WHERE id = %s",
                (ops_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def parse_ops_id(source_msg_key: str) -> int | None:
    """Extract ops_messages.id from 'msg:{chat_id}:{ops_id}:{type}'."""
    if not source_msg_key.startswith("msg:"):
        return None
    parts = source_msg_key.split(":")
    if len(parts) >= 3:
        try:
            return int(parts[2])
        except ValueError:
            pass
    return None


def parse_ref_time(sent_at) -> datetime | None:
    """Convert ops_messages.sent_at (TEXT or datetime) to aware UTC datetime."""
    if sent_at is None:
        return None
    if isinstance(sent_at, datetime):
        return sent_at if sent_at.tzinfo else sent_at.replace(tzinfo=timezone.utc)
    s = str(sent_at)
    for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z"]:
        try:
            return datetime.strptime(s[:32], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# ─── Photo matching ───────────────────────────────────────────────────────────

def find_photos(concern: dict, photo_sender: dict[str, str],
                photo_timestamps: dict[str, datetime]) -> list[str]:
    """
    Return local photo paths (up to 10) for a concern, matched by sender+timestamp.
    Falls back to timestamp-only if nothing found with sender match.
    """
    sender = (concern.get("sender_name") or "").strip().lower()
    ops_id = parse_ops_id(concern["source_msg_key"])

    # For low_stock concerns that have no ops_id, use detected_at
    if ops_id is not None:
        ops_msg = get_ops_message(ops_id)
        ref_dt = parse_ref_time(ops_msg["sent_at"]) if ops_msg else None
    else:
        ref_dt = parse_ref_time(concern.get("detected_at"))

    if ref_dt is None:
        return []

    candidates_sender: list[tuple[float, str]] = []
    candidates_time:   list[tuple[float, str]] = []

    for basename, utc_dt in photo_timestamps.items():
        if utc_dt is None:
            continue
        diff = abs((utc_dt - ref_dt).total_seconds())
        if diff > WINDOW_SECS:
            continue
        # Timestamp match — log regardless
        candidates_time.append((diff, basename))
        # Sender match
        photo_s = (photo_sender.get(basename) or "").strip().lower()
        if sender and photo_s == sender:
            candidates_sender.append((diff, basename))

    if candidates_sender:
        best = sorted(candidates_sender)[:10]
    elif candidates_time:
        # fallback: no sender filter — include all in window
        best = sorted(candidates_time)[:10]
    else:
        return []

    return [os.path.join(PHOTO_DIR, b) for _, b in best if os.path.exists(os.path.join(PHOTO_DIR, b))]


# ─── Telegram formatting ──────────────────────────────────────────────────────

ICONS = {"mistake": "❌", "waste": "♻️", "low_stock": "📉",
         "cleanliness": "🧹", "staffing": "👥"}


def format_concern(c: dict) -> str:
    icon = ICONS.get(c["concern_type"], "⚠️")
    ts = c["detected_at"]
    if hasattr(ts, "strftime"):
        date_str = ts.strftime("%b %d")
    else:
        date_str = str(ts)[:10]
    ctype = c["concern_type"].upper().replace("_", " ")
    return (
        f"{icon} {ctype} — {c['sender_name']}\n"
        f"{c['description']}\n"
        f"─────────\n"
        f"{date_str} • Concern #{c['id']}"
    )


def concern_keyboard(concern_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ All good",    callback_data=f"gm_ok:{concern_id}"),
        InlineKeyboardButton("🚨 Real issue", callback_data=f"gm_real:{concern_id}"),
        InlineKeyboardButton("📚 Teach bot",  callback_data=f"gm_teach:{concern_id}"),
    ]])


async def send_concern(bot: Bot, concern: dict, photo_paths: list[str]) -> int:
    """Send concern card (+ photos if any) to owner. Returns Telegram message_id."""
    text = format_concern(concern)
    kb   = concern_keyboard(concern["id"])
    existing = [p for p in photo_paths if os.path.exists(p)]

    if len(existing) == 1:
        with open(existing[0], "rb") as fh:
            msg = await bot.send_photo(
                chat_id=config.OWNER_TELEGRAM_ID,
                photo=fh,
                caption=text,
                reply_markup=kb,
            )
        return msg.message_id

    elif len(existing) > 1:
        handles = [open(p, "rb") for p in existing[:10]]
        media   = [InputMediaPhoto(fh) for fh in handles]
        try:
            await bot.send_media_group(chat_id=config.OWNER_TELEGRAM_ID, media=media)
        finally:
            for fh in handles:
                fh.close()
        msg = await bot.send_message(
            chat_id=config.OWNER_TELEGRAM_ID,
            text=text,
            reply_markup=kb,
        )
        return msg.message_id

    else:
        msg = await bot.send_message(
            chat_id=config.OWNER_TELEGRAM_ID,
            text=text,
            reply_markup=kb,
        )
        return msg.message_id


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main(dry_run: bool, limit: int | None, sender_filter: str | None) -> None:
    print("Building photo index from HTML exports...")
    photo_sender = build_photo_sender_map()
    print(f"  {len(photo_sender)} non-thumb photos indexed from HTML")

    # Build timestamp map from filenames
    photo_timestamps: dict[str, datetime] = {}
    for basename in photo_sender:
        photo_timestamps[basename] = photo_utc(basename)

    concerns = get_unsent_concerns(sender_filter)
    print(f"Found {len(concerns)} unsent concerns" +
          (f" matching '{sender_filter}'" if sender_filter else ""))

    if not concerns:
        print("Nothing to send.")
        return

    if limit:
        concerns = concerns[:limit]
        print(f"Limiting to first {limit}")

    bot = Bot(token=GM_BOT_TOKEN)

    sent = skipped = with_photos = no_photos = 0
    for i, concern in enumerate(concerns):
        photos = find_photos(concern, photo_sender, photo_timestamps)
        if dry_run:
            tag = f" [{len(photos)} photos]" if photos else " [no photos]"
            _safe_print(f"  [dry-run] #{concern['id']} {concern['sender_name']} -- {concern['concern_type']}{tag}")
            continue

        try:
            tg_msg_id = await send_concern(bot, concern, photos)
            gm_mark_sent(concern["id"], tg_msg_id)
            sent += 1
            if photos:
                with_photos += 1
            else:
                no_photos += 1
        except Exception as e:
            _safe_print(f"  ERROR concern #{concern['id']}: {e}")
            skipped += 1

        if (i + 1) % 20 == 0:
            _safe_print(f"  {i + 1}/{len(concerns)} sent...")

        await asyncio.sleep(RATE_DELAY)

    if dry_run:
        print("\nDry run complete — nothing sent.")
    else:
        print(f"\nDone: {sent} sent ({with_photos} with photos, {no_photos} without), {skipped} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--limit",  type=int, default=None, help="Send at most N concerns")
    parser.add_argument("--sender", type=str, default=None, help="Filter by sender name substring")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.limit, args.sender))
