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
                    source     TEXT NOT NULL DEFAULT 'live',  -- 'live' (real-time hook) | 'replay' (backfill)
                    reconciled BOOLEAN NOT NULL DEFAULT FALSE,-- a mismatch we've understood/fixed/accepted
                    at         TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # self-migrate (table may predate these columns)
            cur.execute("ALTER TABLE shadow_comparisons ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'live'")
            cur.execute("ALTER TABLE shadow_comparisons ADD COLUMN IF NOT EXISTS reconciled BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_shadow_open "
                        "ON shadow_comparisons (org_id, agree, reconciled)")
            # ── the money ledger (org-scoped) — atomic-claim-at-the-write, the cure for the over-book /
            # double-bank bug-class. The CHECK constraints enforce the invariants STRUCTURALLY: the DB
            # itself refuses an over-credit (paid>owed) or an over-debit (balance<0) — not the caller. ──
            cur.execute("ALTER TABLE shifts ADD COLUMN IF NOT EXISTS settled_at TIMESTAMPTZ")  # settle-once claim
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_ot_bank (
                    org_id      TEXT NOT NULL,
                    staff_id    INTEGER NOT NULL,
                    balance_min INTEGER NOT NULL DEFAULT 0 CHECK (balance_min >= 0),
                    updated_at  TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, staff_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_payback_debts (
                    debt_id    BIGSERIAL PRIMARY KEY,
                    org_id     TEXT NOT NULL,
                    staff_id   INTEGER NOT NULL,
                    owed_min   INTEGER NOT NULL CHECK (owed_min >= 0),
                    paid_min   INTEGER NOT NULL DEFAULT 0 CHECK (paid_min >= 0 AND paid_min <= owed_min),
                    status     TEXT NOT NULL DEFAULT 'open',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_core_debts_open "
                        "ON core_payback_debts (org_id, staff_id, status)")


def ensure_org(org_id: str, name: str = None, timezone: str = "Asia/Phnom_Penh") -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO orgs (org_id, name, timezone) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id) DO NOTHING", (org_id, name or org_id, timezone))
