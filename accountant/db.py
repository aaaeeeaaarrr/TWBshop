"""Accounting ledger — schema + data layer for the Accountant bot.

P0 = the spine: vendor master / group map + the receipt (Accounts Payable) ledger + the
lump-payment matcher tables. Design: docs/REPORT_SYSTEM_DESIGN.md §D (reviewed draft).

Conventions (match the rest of the project):
  - tables prefixed `acc_` (greppable finance package)
  - money = INTEGER **USD cents** (`amount_cents`) — one canonical unit, no float drift;
    Riel converted at the fixed books rate 4000៛ = $1, ORIGINAL currency/amount kept for audit
  - SERIAL PK · status TEXT with an inline enum comment · TIMESTAMPTZ DEFAULT NOW() · `is_test` flag
  - `CREATE TABLE IF NOT EXISTS` + additive `ALTER … ADD COLUMN IF NOT EXISTS` (idempotent init)
  - connections reuse the shared pool (`shared.database._db`) — one DB, fail-closed env switch.

State-integrity (STATE_INTEGRITY_LAWS / design §D4): paid-flip is idempotent (flip status FIRST,
atomically) with `slip_sha` / `photo_sha` UNIQUE as structural dedup backstops; the matcher
CAS-claims a receipt before allocating; the `#` shown in chat IS `acc_receipts.id` (shown == true).
"""
from shared.database import _db

# Fixed books conversion (design §D / §B4). Riel amounts convert to USD cents at this rate.
KHR_PER_USD = 4000


def to_usd_cents(amount, currency: str) -> int | None:
    """Canonicalise a written amount to integer USD cents. Riel at the fixed 4000៛=$1 books rate.
    Returns None if amount is None (a row with no readable total is the only thing that blocks)."""
    if amount is None:
        return None
    cur = (currency or "USD").strip().upper()
    if cur in ("KHR", "RIEL", "៛"):
        return round((float(amount) / KHR_PER_USD) * 100)
    return round(float(amount) * 100)


def init_accounting_db() -> None:
    """Create the accounting schema (idempotent). Called at accountant-bot startup.
    Applied to whichever DB the TWBSHOP_ENV switch selects (staging in dev, prod on the server)."""
    with _db() as conn:
        with conn.cursor() as cur:
            # ── acc_vendors — master / supplier-group map (design §D1, the paid-signal §C1) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_vendors (
                    id                SERIAL PRIMARY KEY,
                    name              TEXT NOT NULL,
                    tg_group_id       BIGINT UNIQUE,
                    aliases           TEXT DEFAULT '[]',
                    category          TEXT,
                    aba_account       TEXT,
                    typical_min_cents INTEGER,
                    typical_max_cents INTEGER,
                    terms_days        INTEGER,
                    active            BOOLEAN DEFAULT TRUE,
                    created_at        TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acc_vendors_group ON acc_vendors (tg_group_id)")

            # ── acc_receipts — the spine: numbered AP rows (design §D2) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_receipts (
                    id             SERIAL PRIMARY KEY,
                    vendor_id      INTEGER REFERENCES acc_vendors(id),
                    biz_date       DATE,
                    amount_cents   INTEGER,
                    orig_currency  TEXT DEFAULT 'USD',
                    orig_amount    NUMERIC,
                    pay_method     TEXT,
                    category       TEXT,
                    items_text     TEXT,
                    is_handwritten BOOLEAN DEFAULT FALSE,
                    status         TEXT DEFAULT 'captured',
                    photo_file_id  TEXT,
                    photo_sha      TEXT,
                    tg_chat_id     BIGINT,
                    tg_msg_id      BIGINT,
                    captured_by    BIGINT,
                    created_at     TIMESTAMPTZ DEFAULT NOW(),
                    is_test        BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acc_receipts_vendor_status ON acc_receipts (vendor_id, status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acc_receipts_bizdate ON acc_receipts (biz_date)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_receipts_sha ON acc_receipts (photo_sha) WHERE photo_sha IS NOT NULL")

            # ── acc_payments + acc_payment_allocations — the lump matcher (design §D3) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_payments (
                    id            SERIAL PRIMARY KEY,
                    vendor_id     INTEGER REFERENCES acc_vendors(id),
                    amount_cents  INTEGER,
                    orig_currency TEXT DEFAULT 'USD',
                    orig_amount   NUMERIC,
                    paid_at       TIMESTAMPTZ,
                    aba_account   TEXT,
                    slip_file_id  TEXT,
                    slip_sha      TEXT,
                    tg_chat_id    BIGINT,
                    tg_msg_id     BIGINT,
                    status        TEXT DEFAULT 'pending',
                    confirmed_by  BIGINT,
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    is_test       BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_payments_sha ON acc_payments (slip_sha) WHERE slip_sha IS NOT NULL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_payment_allocations (
                    id            SERIAL PRIMARY KEY,
                    payment_id    INTEGER REFERENCES acc_payments(id),
                    receipt_id    INTEGER REFERENCES acc_receipts(id),
                    amount_cents  INTEGER,
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (payment_id, receipt_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acc_alloc_receipt ON acc_payment_allocations (receipt_id)")


# ── Vendor master / group map — P0 (`/vendor link <name>` run inside each supplier group) ──

def vendor_link(name: str, tg_group_id: int | None = None,
                category: str | None = None, aba_account: str | None = None) -> int:
    """Upsert a vendor and (optionally) link a Telegram supplier group → vendor (the paid-signal).
    Keyed on tg_group_id when given (one group = one vendor); returns the vendor id."""
    with _db() as conn:
        with conn.cursor() as cur:
            if tg_group_id is not None:
                cur.execute("""
                    INSERT INTO acc_vendors (name, tg_group_id, category, aba_account)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tg_group_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        category = COALESCE(EXCLUDED.category, acc_vendors.category),
                        aba_account = COALESCE(EXCLUDED.aba_account, acc_vendors.aba_account),
                        active = TRUE
                    RETURNING id
                """, (name, tg_group_id, category, aba_account))
            else:
                cur.execute("""
                    INSERT INTO acc_vendors (name, category, aba_account)
                    VALUES (%s, %s, %s) RETURNING id
                """, (name, category, aba_account))
            return cur.fetchone()["id"]


def vendor_by_group(tg_group_id: int) -> dict | None:
    """Resolve the vendor a message/payment-slip belongs to from the group it landed in
    (zero-read paid-signal, design §C1). None if the group isn't linked."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_vendors WHERE tg_group_id = %s AND active", (tg_group_id,))
            return cur.fetchone()


def list_vendors(active_only: bool = True) -> list[dict]:
    """All vendors (for an owner overview / the payable run)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM acc_vendors %s ORDER BY name" % ("WHERE active" if active_only else ""))
            return list(cur.fetchall())


# ── P1 / P2 interface (build-the-interface-first, Arch-Rule-2; implemented in later phases) ──

def add_receipt(*args, **kwargs):
    """P1 — capture a numbered receipt row from a photo (reuses ai_client.assess_receipt_photo +
    clarify.py). Cash → auto-paid at capture; ABA → unpaid, joins the open list. Dedup on photo_sha."""
    raise NotImplementedError("accountant P1 — receipt capture")


def open_receipts_for_vendor(vendor_id: int):
    """P2 — unpaid (status in captured/confirmed, pay_method='aba') receipts for a vendor, FIFO order.
    Powers the payable run + the subset-sum matcher."""
    raise NotImplementedError("accountant P2 — payable run")


def record_payment_and_match(*args, **kwargs):
    """P2 (HEART) — record a lump ABA slip (vendor from its group) → subset-sum / FIFO match to open
    receipts → flip them paid (status FIRST, atomic CAS) → write allocations. Confirm, never infer."""
    raise NotImplementedError("accountant P2 — lump matcher")
