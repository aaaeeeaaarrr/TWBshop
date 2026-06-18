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
            # additive detail columns (read off the receipt; cheap to capture, valuable for the books)
            for _col, _typ in (("invoice_no", "TEXT"), ("receipt_date", "TEXT"),
                               ("tax_cents", "INTEGER"), ("supplier_account", "TEXT"),
                               ("bank_name", "TEXT")):
                cur.execute(f"ALTER TABLE acc_receipts ADD COLUMN IF NOT EXISTS {_col} {_typ}")

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

            # ── acc_receipt_lines — per-line detail (design §E11): math check now, stock lane later ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_receipt_lines (
                    id               SERIAL PRIMARY KEY,
                    receipt_id       INTEGER REFERENCES acc_receipts(id),
                    raw_name         TEXT,
                    item_id          INTEGER,            -- → acc_items (stock lane); NULL for now
                    qty              NUMERIC,
                    unit             TEXT,
                    unit_price_cents INTEGER,
                    line_total_cents INTEGER,
                    created_at       TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acc_lines_receipt ON acc_receipt_lines (receipt_id)")


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


def vendor_by_name(name: str) -> dict | None:
    """Vendor-learning (lite): match a printed receipt name to a seeded vendor by case-insensitive
    substring (either direction), e.g. read 'SONG HENG' → seeded 'Song Heng Gas'. None if no match.
    (Full printed-name learning — storing each receipt's exact spelling — comes later.)"""
    if not name:
        return None
    n = " ".join(name.strip().lower().split())
    if len(n) < 3:
        return None
    for v in list_vendors(active_only=False):
        vn = " ".join((v["name"] or "").lower().split())
        if vn and (vn in n or n in vn):
            return v
    return None


def list_vendors(active_only: bool = True) -> list[dict]:
    """All vendors (for an owner overview / the payable run)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM acc_vendors %s ORDER BY name" % ("WHERE active" if active_only else ""))
            return list(cur.fetchall())


# ── P1 / P2 interface (build-the-interface-first, Arch-Rule-2; implemented in later phases) ──

def add_receipt(vendor_id=None, amount_cents=None, pay_method=None, orig_currency="USD",
                orig_amount=None, category=None, items_text=None, is_handwritten=False,
                photo_file_id=None, photo_sha=None, tg_chat_id=None, tg_msg_id=None,
                captured_by=None, is_test=False, invoice_no=None, receipt_date=None,
                tax_cents=None, supplier_account=None, bank_name=None) -> int:
    """P1 — capture a numbered receipt row. status='captured' (DRAFT); pay_method/paid are set
    later from the living card. Dedup on photo_sha: the same photo returns the EXISTING row's id
    (S2 — one photo, one row; the uq_acc_receipts_sha index is the structural backstop)."""
    with _db() as conn:
        with conn.cursor() as cur:
            if photo_sha:
                cur.execute("SELECT id FROM acc_receipts WHERE photo_sha=%s", (photo_sha,))
                row = cur.fetchone()
                if row:
                    return row["id"]
            cur.execute("""
                INSERT INTO acc_receipts
                    (vendor_id, amount_cents, pay_method, orig_currency, orig_amount, category,
                     items_text, is_handwritten, status, photo_file_id, photo_sha, tg_chat_id,
                     tg_msg_id, captured_by, is_test, invoice_no, receipt_date, tax_cents,
                     supplier_account, bank_name)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'captured',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (vendor_id, amount_cents, pay_method, orig_currency, orig_amount, category,
                  items_text, is_handwritten, photo_file_id, photo_sha, tg_chat_id, tg_msg_id,
                  captured_by, is_test, invoice_no, receipt_date, tax_cents, supplier_account,
                  bank_name))
            return cur.fetchone()["id"]


def get_receipt(rid: int) -> dict | None:
    """A receipt row joined to its vendor name (for the card)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.*, v.name AS vendor_name FROM acc_receipts r
                           LEFT JOIN acc_vendors v ON v.id = r.vendor_id WHERE r.id = %s""", (rid,))
            return cur.fetchone()


def _num(v):
    """Coerce a model value ('1', 1, '1.5', '1,200', 'x2') to float, else None."""
    try:
        return float(str(v).replace(",", "").replace("x", "").strip())
    except (ValueError, TypeError, AttributeError):
        return None


def save_receipt_lines(receipt_id, line_items, currency="USD") -> None:
    """Store the structured per-line detail (design §E11). Prices → USD cents; all best-effort."""
    rows = []
    for li in (line_items or []):
        if not isinstance(li, dict):
            continue
        name = (li.get("name") or "").strip() or None
        up, lt = _num(li.get("unit_price")), _num(li.get("line_total"))
        if name is None and up is None and lt is None:
            continue
        rows.append((receipt_id, name, _num(li.get("qty")),
                     to_usd_cents(up, currency) if up is not None else None,
                     to_usd_cents(lt, currency) if lt is not None else None))
    if not rows:
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO acc_receipt_lines
                (receipt_id, raw_name, qty, unit_price_cents, line_total_cents)
                VALUES (%s,%s,%s,%s,%s)""", rows)


def get_receipt_lines(receipt_id) -> list[dict]:
    """The structured lines for a receipt (for the card + the math check)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_receipt_lines WHERE receipt_id=%s ORDER BY id", (receipt_id,))
            return list(cur.fetchall())


def confirm_receipt(rid: int) -> None:
    """Staff confirmed paper == bot → DRAFT(captured) to CONFIRMED."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_receipts SET status='confirmed' "
                        "WHERE id=%s AND status='captured'", (rid,))


def set_payment(rid: int, method: str) -> bool:
    """Cash → paid at capture (S2: flip status FIRST + idempotent — a re-tap can't double-anything).
    ABA → stays unpaid, joins the open list (the slip flips it paid in P2). True if this call changed it."""
    with _db() as conn:
        with conn.cursor() as cur:
            if method == "cash":
                cur.execute("UPDATE acc_receipts SET pay_method='cash', status='paid' "
                            "WHERE id=%s AND status<>'paid' RETURNING id", (rid,))
            else:  # aba
                cur.execute("UPDATE acc_receipts SET pay_method='aba', status='confirmed' "
                            "WHERE id=%s AND status IN ('captured','confirmed') RETURNING id", (rid,))
            return cur.fetchone() is not None


def edit_receipt(rid: int, **fields) -> None:
    """Apply a correction from ✏️ Fix. Whitelisted columns only."""
    allowed = {"amount_cents", "vendor_id", "category", "items_text", "orig_currency",
               "orig_amount", "pay_method"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    cols = ", ".join(f"{k}=%s" for k in sets)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE acc_receipts SET {cols} WHERE id=%s", (*sets.values(), rid))


def delete_receipt(rid: int) -> None:
    """Remove a receipt row (+ any allocations) — correcting a mis-capture or clearing a test row so
    the same photo can be re-captured (the photo_sha dedup otherwise returns the existing row)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM acc_payment_allocations WHERE receipt_id=%s", (rid,))
            cur.execute("DELETE FROM acc_receipt_lines WHERE receipt_id=%s", (rid,))
            cur.execute("DELETE FROM acc_receipts WHERE id=%s", (rid,))


def list_open_receipts(is_test=False) -> list[dict]:
    """Unpaid ABA receipts — the open list / carry-forward (design §B4)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.*, v.name AS vendor_name FROM acc_receipts r
                           LEFT JOIN acc_vendors v ON v.id = r.vendor_id
                           WHERE r.status <> 'paid' AND r.pay_method = 'aba' AND r.is_test = %s
                           ORDER BY r.id""", (is_test,))
            return list(cur.fetchall())


def open_receipts_for_vendor(vendor_id: int):
    """P2 — unpaid (status in captured/confirmed, pay_method='aba') receipts for a vendor, FIFO order.
    Powers the payable run + the subset-sum matcher."""
    raise NotImplementedError("accountant P2 — payable run")


def record_payment_and_match(*args, **kwargs):
    """P2 (HEART) — record a lump ABA slip (vendor from its group) → subset-sum / FIFO match to open
    receipts → flip them paid (status FIRST, atomic CAS) → write allocations. Confirm, never infer."""
    raise NotImplementedError("accountant P2 — lump matcher")
