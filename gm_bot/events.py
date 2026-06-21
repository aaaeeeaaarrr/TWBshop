"""gm_events — append-only audit log for the GM/attendance bot (owner, 2026-06-21).

Every staff-facing event gets ONE row — check-in/out, late/early, sick/AL/OT/payback action, a push
SENT, a button CLICKED, a points event, an FYI posted — so we can later answer "did the push send / did
he click / did the −15 fire" AND run anomaly checks that DM the owner the moment something didn't go as
it should (early-days visibility). `log_event` is BEST-EFFORT: it must NEVER raise into a live flow —
logging can't be allowed to break attendance/payroll. Pure storage; the checks live in audit.py.
"""
import json
import logging

from shared.database import _db

logger = logging.getLogger(__name__)


def init_events_db() -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gm_events (
                    id       SERIAL PRIMARY KEY,
                    at       TIMESTAMPTZ DEFAULT NOW(),
                    kind     TEXT NOT NULL,      -- checkin|checkout|late|early|sick_filed|push_sent|click|
                                                 -- points|payback_book|fyi|... (free, but keep a small set)
                    staff_id INTEGER,
                    uid      BIGINT,             -- telegram user id (for clicks / messages)
                    detail   TEXT DEFAULT '{}',  -- JSON specifics (amounts, dates, the button data, etc.)
                    is_test  BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gm_events_kind_at ON gm_events (kind, at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gm_events_staff_at ON gm_events (staff_id, at)")


def log_event(kind, staff_id=None, uid=None, detail=None, is_test=False) -> None:
    """Append one audit event. BEST-EFFORT — swallows ALL errors so logging can never break a live flow."""
    try:
        payload = json.dumps(detail or {}, default=str)[:4000]
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO gm_events (kind, staff_id, uid, detail, is_test) "
                            "VALUES (%s,%s,%s,%s,%s)", (kind, staff_id, uid, payload, is_test))
    except Exception:
        logger.exception("gm_events log_event failed (non-fatal): kind=%s staff=%s", kind, staff_id)


def recent_events(kind=None, staff_id=None, limit=100, is_test=None) -> list:
    """Read recent events (for the anomaly checks + forensics). Newest first."""
    where, params = [], []
    if kind is not None:
        where.append("kind=%s")
        params.append(kind)
    if staff_id is not None:
        where.append("staff_id=%s")
        params.append(staff_id)
    if is_test is not None:
        where.append("is_test=%s")
        params.append(is_test)
    sql = "SELECT * FROM gm_events" + ((" WHERE " + " AND ".join(where)) if where else "")
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]
