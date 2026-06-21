"""core.db — the platform's multi-tenant schema + persistence (entity + event log).

Reuses shared.database._db (same env-guarded Postgres pool) during the build/shadow phase; the tables
are NEW and additive, so they coexist with the live system and touch nothing it owns. Self-migrating.
"""
from shared.database import _db


def init_core_db() -> None:
    """Create the platform's tables (additive, idempotent). Safe to run on every startup."""
    with _db() as conn:
        with conn.cursor() as cur:
            # Tenants. org_id is a short stable slug ('twb' = TWBshop, customer #1).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orgs (
                    org_id      TEXT PRIMARY KEY,
                    name        TEXT,
                    timezone    TEXT NOT NULL DEFAULT 'Asia/Phnom_Penh',
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # A shift = one work interval for one person. The IDENTITY is shift_id; start_dt/end_dt are the
            # real (UTC) interval and the ONLY basis for time logic; business_day is a derived label.
            # UNIQUE(org_id, staff_id, start_dt) is the atomic-claim anchor — no duplicate instance.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shifts (
                    shift_id     BIGSERIAL PRIMARY KEY,
                    org_id       TEXT NOT NULL REFERENCES orgs(org_id),
                    staff_id     INTEGER NOT NULL,
                    start_dt     TIMESTAMPTZ NOT NULL,
                    end_dt       TIMESTAMPTZ NOT NULL,
                    business_day DATE NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'scheduled',
                    origin       TEXT NOT NULL DEFAULT 'regular',
                    created_at   TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (org_id, staff_id, start_dt)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_shifts_window "
                        "ON shifts (org_id, staff_id, start_dt, end_dt)")
            # Append-only event log — the audit + integration backbone. Never updated in place.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS attendance_events (
                    event_id   BIGSERIAL PRIMARY KEY,
                    org_id     TEXT NOT NULL,
                    shift_id   BIGINT REFERENCES shifts(shift_id),
                    staff_id   INTEGER NOT NULL,
                    type       TEXT NOT NULL,
                    at         TIMESTAMPTZ NOT NULL,
                    detail     JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attevents_shift ON attendance_events (shift_id, type)")
            # One check-in / one check-out per shift — the idempotency claim (no double-event).
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_attevent_shift_type "
                        "ON attendance_events (shift_id, type) WHERE type IN ('checked_in','checked_out')")
            # Shadow comparisons: the new core's answer vs what live TWB did, for the SAME real event.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shadow_comparisons (
                    id         BIGSERIAL PRIMARY KEY,
                    org_id     TEXT,
                    staff_id   INTEGER,
                    kind       TEXT,
                    agree      BOOLEAN,
                    live       JSONB,
                    new        JSONB,
                    note       TEXT,
                    at         TIMESTAMPTZ DEFAULT NOW()
                )
            """)


def ensure_org(org_id: str, name: str = None, timezone: str = "Asia/Phnom_Penh") -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO orgs (org_id, name, timezone) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id) DO NOTHING", (org_id, name or org_id, timezone))
