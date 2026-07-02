"""core.sends — the durable SEND LEDGER: intent → sent | failed (observability law, 2026-07-02).

"Delivery ≠ done" starts with "attempted ≠ delivered": a proactive message (a ladder rung, a group post,
a builder notify) that dies mid-send — process restart, silent Telegram rejection, a swallowed except —
leaves no trace today. The ledger is the outbox record: the chokepoint writes an 'intent' row BEFORE
attempting, then marks 'sent' (with the Telegram message_id = the max verifiable delivery proof for a
bot) or 'failed'. A row stuck at 'intent' means a send died mid-flight; a 'failed' row means every retry
lost. core.sentinel.detect_stuck_sends turns both into alarms on the 30-min sweep.

SCOPE (deliberate): PROACTIVE sends only — the two chokepoints are gm's `_att_send` (attendance
ladders/posts/DMs) and `shared.monitor_notify` (every builder DM from any process). Handler replies are
request/response (the user re-taps); they stay out. Writes are BEST-EFFORT — the ledger must never
break the send it records.
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.database import _db

logger = logging.getLogger(__name__)

_TZ = "Asia/Phnom_Penh"


def _now() -> datetime:
    return datetime.now(ZoneInfo(_TZ))


def init_send_ledger_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_send_ledger (
                    id         SERIAL PRIMARY KEY,
                    org_id     TEXT NOT NULL,
                    at         TIMESTAMPTZ DEFAULT NOW(),
                    channel    TEXT NOT NULL,          -- gm | monitor | ...
                    kind       TEXT NOT NULL,          -- role / alert kind
                    target     TEXT,                   -- chat id (or 'none' when unresolvable)
                    ref        TEXT,                   -- optional correlation (staff id, alarm id, ...)
                    status     TEXT NOT NULL DEFAULT 'intent',   -- intent | sent | failed
                    message_id TEXT,
                    err        TEXT,
                    updated    TIMESTAMPTZ,
                    is_test    BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_send_ledger_status ON core_send_ledger (org_id, status, at DESC)")


def record(org_id: str, channel: str, kind: str, target, ref=None, is_test=False):
    """Write the intent row BEFORE attempting the send; returns its id (or None). Never raises."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO core_send_ledger (org_id, channel, kind, target, ref, is_test) "
                            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                            (org_id, channel, str(kind)[:64], str(target)[:64] if target is not None else None,
                             str(ref)[:64] if ref is not None else None, bool(is_test)))
                return cur.fetchone()["id"]
    except Exception:
        logger.exception("sends.record failed (non-fatal): %s/%s", channel, kind)
        return None


def mark(sid, ok: bool, message_id=None, err=None) -> None:
    """Close the intent: 'sent' with the Telegram message_id, or 'failed' with the error. Never raises."""
    if not sid:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE core_send_ledger SET status=%s, message_id=%s, err=%s, updated=NOW() "
                            "WHERE id=%s",
                            ("sent" if ok else "failed",
                             str(message_id)[:32] if message_id is not None else None,
                             str(err)[:300] if err else None, sid))
    except Exception:
        logger.exception("sends.mark failed (non-fatal): id=%s", sid)


def stuck(org_id: str, now: datetime = None, intent_min: int = 15, failed_hours: int = 24) -> list:
    """Sends that never completed — READ-ONLY, for the sentinel detector.
    'intent' older than intent_min (bounded to 7d)  = a send died mid-flight (process death / crash).
    'failed' updated within failed_hours            = every retry lost; a human should know."""
    now = now or _now()
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM core_send_ledger WHERE org_id=%s AND is_test=FALSE AND ("
                "  (status='intent' AND at < %s AND at > %s)"
                "  OR (status='failed' AND updated > %s)"
                ") ORDER BY id DESC LIMIT 50",
                (org_id, now - timedelta(minutes=intent_min), now - timedelta(days=7),
                 now - timedelta(hours=failed_hours)))
            return [dict(r) for r in cur.fetchall()]
