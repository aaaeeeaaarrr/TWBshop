"""core.db — the platform's multi-tenant schema + persistence (entity + event log).

Reuses shared.database._db (same env-guarded Postgres pool) during the build/shadow phase; the tables
are NEW and additive, so they coexist with the live system and touch nothing it owns. Self-migrating.
"""
import base64
import hashlib
import hmac
import logging
import os

from shared.database import _db

_ENC_PREFIX = "enc:"   # marks an encrypted org-secret value (vs a legacy plaintext one)


def _org_secret_cipher():
    """A Fernet from ORG_SECRET_KEY (secrets.py or env) — or None (then secrets stay plaintext + a warning).
    SECURITY (PRODUCT SECURITY law): set ORG_SECRET_KEY before any public/multi-tenant exposure (W3 gate).
    Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'."""
    key = None
    try:
        import config
        key = getattr(config, "ORG_SECRET_KEY", None)
    except Exception:
        pass
    key = key or os.environ.get("ORG_SECRET_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        logging.getLogger("core.secrets").exception("bad ORG_SECRET_KEY")
        return None


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
                    config      JSONB NOT NULL DEFAULT '{}',  -- per-tenant knobs (grace/thresholds/channels/package)
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE orgs ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'")
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
            # the core's OWN representation of a day's modifiers (leave / redefine / swap) — what makes the
            # resolver SELF-DERIVE (post-cut-over there's no live to feed it). Populated natively, or synced
            # from live during the shadow phase. One row per (org, staff, day, kind); resolve() folds them.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_day_overrides (
                    org_id    TEXT NOT NULL,
                    staff_id  INTEGER NOT NULL,
                    day       DATE NOT NULL,
                    kind      TEXT NOT NULL,          -- al | sick | special | redefine | swap_off | swap_work
                    start_min INTEGER,                -- for redefine / swap_work
                    end_min   INTEGER,
                    source    TEXT NOT NULL DEFAULT 'native',  -- native | live_sync
                    PRIMARY KEY (org_id, staff_id, day, kind)
                )
            """)
            # AL balance + requests — deduct-at-approval ↔ refund-on-cancel (S1). The per-day deduction is
            # FROZEN on the request at creation, so refund reads the row and never recomputes.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_al_balance (
                    org_id         TEXT NOT NULL,
                    staff_id       INTEGER NOT NULL,
                    days_remaining NUMERIC(6,2) NOT NULL DEFAULT 0,
                    updated_at     TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, staff_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_al_requests (
                    req_id     BIGSERIAL PRIMARY KEY,
                    org_id     TEXT NOT NULL,
                    staff_id   INTEGER NOT NULL,
                    days       JSONB NOT NULL,
                    deduction  JSONB NOT NULL,                     -- the FROZEN per-day map (S1)
                    total      NUMERIC(6,2) NOT NULL,
                    status     TEXT NOT NULL DEFAULT 'pending',    -- pending | approved | cancelled
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Per-org SECRETS (bot tokens, listener sessions, integration keys) — kept OUT of orgs.config (the
            # readable blob the wizard renders) and NEVER returned to any page. ⚠ Values are plaintext today
            # (localhost / SSH-tunnel / owner-only stage); ENCRYPT AT REST before any public/multi-tenant
            # exposure (W3 hard gate — PRODUCT SECURITY law).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_org_secrets (
                    org_id   TEXT NOT NULL,
                    key      TEXT NOT NULL,
                    value    TEXT NOT NULL,
                    set_at   TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, key)
                )
            """)
            # Platform STAFF (org-scoped) — the discover-confirm onboarding produces these (docs/ONBOARDING_DESIGN.md).
            # shift_windows is a LIST of {day,start,end} → split shifts + overnight (end<start) by the interval model.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_staff (
                    staff_id      BIGSERIAL PRIMARY KEY,
                    org_id        TEXT NOT NULL,
                    name          TEXT NOT NULL,
                    call_name     TEXT,
                    role          TEXT,
                    is_senior     BOOLEAN DEFAULT FALSE,
                    expertises    JSONB DEFAULT '[]',
                    shift_windows JSONB DEFAULT '[]',
                    telegram_id   BIGINT,
                    google_id     TEXT,
                    day_off       TEXT,
                    consent       BOOLEAN DEFAULT FALSE,
                    status        TEXT DEFAULT 'active',
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_core_staff_org ON core_staff (org_id, status)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_core_staff_tg ON core_staff (org_id, telegram_id) "
                        "WHERE telegram_id IS NOT NULL")
            cur.execute("ALTER TABLE core_staff ADD COLUMN IF NOT EXISTS checkin_token TEXT")   # web check-in link
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_core_staff_token ON core_staff (checkin_token) "
                        "WHERE checkin_token IS NOT NULL")
            # Onboarding CANDIDATES — people the bot saw in a staff group, awaiting the owner's one-by-one confirm.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_onboarding_candidates (
                    org_id      TEXT NOT NULL,
                    tg_user_id  BIGINT NOT NULL,
                    chat_id     BIGINT,
                    tg_name     TEXT,
                    tg_username TEXT,
                    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | confirmed | skipped
                    seen_at     TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, tg_user_id)
                )
            """)
            cur.execute("ALTER TABLE core_onboarding_candidates ADD COLUMN IF NOT EXISTS consent BOOLEAN")
            # GROUPS the bot is in — auto-discovered; the owner tags each with a role (staff drives discover-confirm).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_org_groups (
                    org_id   TEXT NOT NULL,
                    chat_id  BIGINT NOT NULL,
                    title    TEXT,
                    role     TEXT,            -- staff | suppliers | management | expenses | reports | NULL
                    seen_at  TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, chat_id)
                )
            """)
            # WIZARD USERS — per-org logins (the W3 auth foundation). Passwords are HASHED, never plaintext.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_org_users (
                    org_id        TEXT NOT NULL,
                    username      TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role          TEXT DEFAULT 'owner',
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (org_id, username)
                )
            """)
            # CONFIG AUDIT — who changed what config knob, when (PRODUCT SECURITY law #5: auditability).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_config_audit (
                    id      BIGSERIAL PRIMARY KEY,
                    org_id  TEXT NOT NULL,
                    who     TEXT,
                    path    TEXT NOT NULL,
                    old_val TEXT,
                    new_val TEXT,
                    at      TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cfg_audit_org ON core_config_audit (org_id, at DESC)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_stock_items (
                    item_id    BIGSERIAL PRIMARY KEY,
                    org_id     TEXT NOT NULL,
                    name       TEXT NOT NULL,
                    unit       TEXT DEFAULT 'unit',
                    category   TEXT,
                    par_level  NUMERIC DEFAULT 0,
                    on_hand    NUMERIC DEFAULT 0,
                    active     BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_items_org ON core_stock_items (org_id, active)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS core_stock_counts (
                    count_id   BIGSERIAL PRIMARY KEY,
                    org_id     TEXT NOT NULL,
                    item_id    BIGINT NOT NULL,
                    qty        NUMERIC NOT NULL,
                    note       TEXT,
                    counted_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_counts_item "
                        "ON core_stock_counts (org_id, item_id, counted_at DESC)")
            cur.execute("ALTER TABLE core_stock_items ADD COLUMN IF NOT EXISTS unit_cost NUMERIC DEFAULT 0")


def log_config_change(org_id: str, who: str, path: str, old_val, new_val) -> None:
    """Append a who-changed-what-when row for a config edit (auditability)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_config_audit (org_id, who, path, old_val, new_val) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (org_id, who or "?", path, None if old_val is None else str(old_val)[:200],
                         None if new_val is None else str(new_val)[:200]))


def recent_config_audit(org_id: str, limit: int = 100) -> list:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT who, path, old_val, new_val, at FROM core_config_audit "
                        "WHERE org_id=%s ORDER BY at DESC LIMIT %s", (org_id, int(limit)))
            return [dict(r) for r in cur.fetchall()]


def ensure_org(org_id: str, name: str = None, timezone: str = "Asia/Phnom_Penh") -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO orgs (org_id, name, timezone) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id) DO NOTHING", (org_id, name or org_id, timezone))


# ── per-org SECRETS — bot tokens, listener sessions, integration keys ─────────────────────────────────
# SECURITY (CLAUDE.md ▶▶ PRODUCT SECURITY & IP): these live OUTSIDE orgs.config and NEVER reach a page.
# The wizard may SET a secret and ASK whether one is set; only the server-side connector reads the value.
def set_org_secret(org_id: str, key: str, value: str) -> None:
    """Store/replace a secret (write-only from the wizard's perspective). Encrypted at rest when
    ORG_SECRET_KEY is set; otherwise stored plaintext with a one-time warning. Empty value is ignored."""
    if not value:
        return
    c = _org_secret_cipher()
    if c:
        stored = _ENC_PREFIX + c.encrypt(value.encode()).decode()
    else:
        stored = value
        logging.getLogger("core.secrets").warning(
            "ORG_SECRET_KEY not set — storing secret %s/%s UNENCRYPTED. Set the key before public exposure.",
            org_id, key)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_org_secrets (org_id, key, value) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id, key) DO UPDATE SET value=EXCLUDED.value, set_at=NOW()",
                        (org_id, key, stored))


def has_org_secret(org_id: str, key: str) -> bool:
    """Is a secret set? For the wizard's 'set ✓ / not set' — NEVER reveals the value."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM core_org_secrets WHERE org_id=%s AND key=%s", (org_id, key))
            return cur.fetchone() is not None


def get_org_secret(org_id: str, key: str) -> str | None:
    """BACKEND ONLY — the connector reads the token to actually connect. NEVER call from a render/response path."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM core_org_secrets WHERE org_id=%s AND key=%s", (org_id, key))
            r = cur.fetchone()
    if not r:
        return None
    v = r["value"]
    if v and v.startswith(_ENC_PREFIX):
        c = _org_secret_cipher()
        if not c:
            return None                              # encrypted but the key is gone → can't decrypt (fail safe)
        try:
            return c.decrypt(v[len(_ENC_PREFIX):].encode()).decode()
        except Exception:
            return None
    return v                                          # legacy plaintext


def clear_org_secret(org_id: str, key: str) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM core_org_secrets WHERE org_id=%s AND key=%s", (org_id, key))


# ── WIZARD USERS (per-org logins) — passwords HASHED (pbkdf2-sha256), never plaintext ──────────────────
# NOTE: we hash with hashlib (NOT werkzeug) on purpose — the repo's secrets.py shadows the stdlib `secrets`
# module that werkzeug's hashing imports, which would crash it. os.urandom + pbkdf2 + hmac avoid that.
def _hash_pw(password: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return "pbkdf2_sha256$200000$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def _check_pw(stored: str, password: str) -> bool:
    try:
        _algo, iters, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(base64.b64decode(dk_b64), dk)   # constant-time
    except Exception:
        return False


def create_user(org_id: str, username: str, password: str, role: str = "owner") -> bool:
    """Create/replace a wizard login. Returns False on empty input."""
    if not username or not password:
        return False
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO core_org_users (org_id, username, password_hash, role)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (org_id, username) DO UPDATE
                             SET password_hash=EXCLUDED.password_hash, role=EXCLUDED.role""",
                        (org_id, username, _hash_pw(password), role))
    return True


def verify_user(org_id: str, username: str, password: str) -> str | None:
    """Return the user's role if username+password match, else None."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash, role FROM core_org_users WHERE org_id=%s AND username=%s",
                        (org_id, username))
            r = cur.fetchone()
    if not r:
        return None
    return r["role"] if _check_pw(r["password_hash"], password or "") else None


def user_count(org_id: str) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM core_org_users WHERE org_id=%s", (org_id,))
            return cur.fetchone()["n"]
