"""gm_bot.alarms — the durable ALARM SINK + mirror-to-Claude (B1, session 58, 2026-06-28).

Owner ask: "find a way where all these Telegram alarms (the ones the GM bot DMs me — day-1 and current)
find their way to you [Claude] too, in case I missed an alarm or an error." So every PROACTIVE owner-
alarm the GM raises (live watchdog, send-resilience outage, escalations, the missing-report alert, the
error-handler) is written HERE FIRST, then DM'd to the owner — an alarm is never lost even if the
Telegram DM fails, and Claude (+ the B3 nightly agent) can read every alarm on demand via
`scripts/alarms.py`, including ones the owner missed.

Mirrors gm_bot/events.py: `_db`, dict rows, no explicit commit (the `_db()` ctx commits on exit), and
log_alarm/mark_delivered/ack_alarm are BEST-EFFORT — they must NEVER raise into a live flow. The DM
itself + routing live the existing alarm sites through this sink is the chokepoint `_alarm()` in
gm_bot/bot.py (B1b)."""
import logging

from shared.database import _db

logger = logging.getLogger(__name__)

SEVERITIES = ("info", "warn", "money")   # money = page-worthy (a balance / impossible-state alarm)


def init_alarms_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_alarms (
                    id        SERIAL PRIMARY KEY,
                    at        TIMESTAMPTZ DEFAULT NOW(),
                    severity  TEXT NOT NULL DEFAULT 'warn',   -- info|warn|money
                    kind      TEXT NOT NULL,                  -- watchdog|send_failure|escalation|error|...
                    body      TEXT NOT NULL,
                    delivered BOOLEAN DEFAULT FALSE,          -- did the owner's Telegram DM go through?
                    acked     BOOLEAN DEFAULT FALSE,          -- handled (by owner or Claude)?
                    is_test   BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gm_alarms_at ON gm_alarms (at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gm_alarms_open ON gm_alarms (acked, at DESC)")


def log_alarm(kind, body, severity="warn", is_test=False):
    """Persist an alarm; return its id (or None). BEST-EFFORT — never raises into a live flow."""
    try:
        sev = severity if severity in SEVERITIES else "warn"
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO gm_alarms (severity, kind, body, is_test) "
                            "VALUES (%s,%s,%s,%s) RETURNING id", (sev, kind, str(body)[:8000], is_test))
                return cur.fetchone()["id"]
    except Exception:
        logger.exception("log_alarm failed (non-fatal): kind=%s", kind)
        return None


def mark_delivered(alarm_id) -> None:
    """Flag that the owner's Telegram DM for this alarm went through. BEST-EFFORT."""
    if not alarm_id:
        return
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE gm_alarms SET delivered=TRUE WHERE id=%s", (alarm_id,))
    except Exception:
        logger.exception("mark_delivered failed (non-fatal): id=%s", alarm_id)


def ack_alarm(alarm_id) -> None:
    """Mark an alarm handled (by the owner or Claude). BEST-EFFORT."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE gm_alarms SET acked=TRUE WHERE id=%s", (alarm_id,))
    except Exception:
        logger.exception("ack_alarm failed (non-fatal): id=%s", alarm_id)


def ack_open_of_kinds(kinds, include_test=False) -> int:
    """Auto-ACK all OPEN (unacked) alarms whose kind is in `kinds` — to SELF-CLOSE integrity alarms once
    the underlying issue is verifiably resolved (e.g. the audit/watchdog is clean again), so the open-alarm
    list always reflects the REAL current state, never stale entries. Returns the count acked. BEST-EFFORT."""
    if not kinds:
        return 0
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                sql = ("UPDATE gm_alarms SET acked=TRUE WHERE acked=FALSE AND kind = ANY(%s)"
                       + ("" if include_test else " AND is_test=FALSE") + " RETURNING id")
                cur.execute(sql, (list(kinds),))
                return len(cur.fetchall())
    except Exception:
        logger.exception("ack_open_of_kinds failed (non-fatal)")
        return 0


def recent_alarms(limit=50, include_test=False, severity=None) -> list:
    """Recent alarms, newest first (for scripts/alarms.py + the B3 nightly agent)."""
    where, params = [], []
    if not include_test:
        where.append("is_test=FALSE")
    if severity:
        where.append("severity=%s")
        params.append(severity)
    sql = "SELECT * FROM gm_alarms" + ((" WHERE " + " AND ".join(where)) if where else "")
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]


def open_alarms(limit=100) -> list:
    """Unacked, non-test alarms — the 'still needs attention' list."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM gm_alarms WHERE acked=FALSE AND is_test=FALSE "
                        "ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]
