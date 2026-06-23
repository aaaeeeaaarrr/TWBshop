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
import difflib
import json

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
            # additive: a staff-proposed vendor is usable at once but awaits a one-tap owner confirm (§G7, A);
            # kind = supplier(AP) | oneoff(throwaway market buy) | internal(Homemade/Delis, not paid); §G9.
            # channel_kind labels the linked paid-signal chat (group | dm) the listener sees it in.
            for _col, _typ in (("needs_review", "BOOLEAN DEFAULT FALSE"), ("created_by", "BIGINT"),
                               ("kind", "TEXT DEFAULT 'supplier'"), ("channel_kind", "TEXT")):
                cur.execute(f"ALTER TABLE acc_vendors ADD COLUMN IF NOT EXISTS {_col} {_typ}")
            # F6 (bedrock audit): make duplicate-vendor-name a STRUCTURAL impossibility — a partial UNIQUE on
            # the ACTIVE vendors' lower(name). propose_vendor then resolves a race to the existing row instead
            # of minting a duplicate. (Inactive/merged names may repeat, so the index is partial on `active`.)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_vendors_name_active "
                        "ON acc_vendors (lower(name)) WHERE active")

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
                               ("bank_name", "TEXT"), ("dup_suspect_of", "INTEGER"),
                               ("read_vendor", "TEXT")):   # the vendor NAME the model read (seeds the §G7 picker)
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
            cur.execute("ALTER TABLE acc_receipt_lines ADD COLUMN IF NOT EXISTS orig_name TEXT")

            # ── acc_item_aliases — the bot's learned item names (model translation + staff corrections) ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_item_aliases (
                    id           SERIAL PRIMARY KEY,
                    vendor_key   INTEGER NOT NULL DEFAULT 0,  -- vendor_id, or 0 for unknown/global
                    orig_name    TEXT NOT NULL,               -- as written on the receipt (e.g. Khmer)
                    english_name TEXT NOT NULL,               -- learned / staff-corrected English
                    updated_at   TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (vendor_key, orig_name)
                )
            """)

            # ── acc_vendor_merges — audit trail for vendor merges (§G7 V4). Records the moved ids so a
            # merge is traceable AND reversible (undo_vendor_merge repoints them back). ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_vendor_merges (
                    id            SERIAL PRIMARY KEY,
                    dup_id        INTEGER NOT NULL,
                    canonical_id  INTEGER NOT NULL,
                    merged_by     BIGINT,
                    receipt_ids   TEXT DEFAULT '[]',   -- JSON: acc_receipts.id moved dup→canonical
                    payment_ids   TEXT DEFAULT '[]',
                    candidate_ids TEXT DEFAULT '[]',
                    undone        BOOLEAN DEFAULT FALSE,
                    merged_at     TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ── acc_receipt_candidates — the "Received Yet?" forward flow (design §E3) ──
            # A photo a supplier posts in THEIR group is forwarded to the Expense group as a
            # CANDIDATE (never auto-numbered). The owner forks it: New&received → promote to a
            # numbered receipt · Already-logged → link to an existing # · Not-yet → park expected ·
            # Ignore. Kept OUT of acc_receipts so the numbered ledger means "a real logged receipt".
            cur.execute("""
                CREATE TABLE IF NOT EXISTS acc_receipt_candidates (
                    id             SERIAL PRIMARY KEY,
                    vendor_id      INTEGER REFERENCES acc_vendors(id),  -- from the supplier group (zero-read)
                    src_chat_id    BIGINT,         -- the supplier group it was posted in
                    src_msg_id     BIGINT,
                    src_chat_title TEXT,           -- group title → the card's "name + group" header
                    photo_file_id  TEXT,
                    photo_sha      TEXT,           -- dedup (same supplier photo twice = one candidate)
                    status         TEXT DEFAULT 'open',  -- open|promoting|promoted|linked|expected|ignored
                    receipt_id     INTEGER REFERENCES acc_receipts(id),  -- set on promote / link
                    card_chat_id   BIGINT,         -- the Expense-group card (edited in place)
                    card_msg_id    BIGINT,
                    posted_by      BIGINT,
                    note           TEXT,
                    created_at     TIMESTAMPTZ DEFAULT NOW(),
                    resolved_at    TIMESTAMPTZ,
                    resolved_by    BIGINT,
                    is_test        BOOLEAN DEFAULT FALSE
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acc_cand_status ON acc_receipt_candidates (status)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_cand_sha ON acc_receipt_candidates (photo_sha) WHERE photo_sha IS NOT NULL")


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


def _vnorm(s: str) -> str:
    """Normalise a vendor/alias string for matching: lowercase, collapse whitespace."""
    return " ".join((s or "").strip().lower().split())


def _vendor_aliases(v: dict) -> list[str]:
    """A vendor row's saved alternate spellings (the `aliases` JSON TEXT '[]'), normalised; [] on junk."""
    try:
        items = json.loads(v.get("aliases") or "[]")
    except (ValueError, TypeError):
        items = []
    return [_vnorm(a) for a in items if str(a).strip()]


def vendor_by_name(name: str) -> dict | None:
    """Auto-resolve a printed/typed name to an existing vendor by case-insensitive SUBSTRING (either
    direction) on the vendor name OR any saved alias — e.g. 'SONG HENG' → 'Song Heng Gas', or a
    learned alias 'atlas beer' → Atlas. DETERMINISTIC, no fuzzy guessing: this silently attributes a
    receipt's vendor (and its money), so it must never mis-match (project no-silent-guess rule).
    Typo/transposition matching is HUMAN-confirmed in find_similar_vendors, not here. None if no match."""
    n = _vnorm(name)
    if len(n) < 3:
        return None
    for v in list_vendors(active_only=True):       # never resolve/suggest a deactivated (e.g. merged) vendor
        for c in [_vnorm(v["name"])] + _vendor_aliases(v):
            if c and (c in n or n in c):
                return v
    return None


def find_similar_vendors(name: str, limit: int = 3, cutoff: float = 0.6) -> list[dict]:
    """Ranked 'did you mean?' candidates for a typed supplier name — the DEDUP GATE shown before a
    staffer creates a NEW vendor, so a typo can't birth a duplicate of the key everything keys on
    (design §G7). Fuzzy (difflib) over each vendor's name + aliases; looser than vendor_by_name because
    a HUMAN confirms the pick. Best score per vendor, highest first."""
    n = _vnorm(name)
    if len(n) < 2:
        return []
    scored = []
    for v in list_vendors(active_only=True):       # never resolve/suggest a deactivated (e.g. merged) vendor
        best = 0.0
        for c in [_vnorm(v["name"])] + _vendor_aliases(v):
            if not c:
                continue
            r = 1.0 if (c in n or n in c) else difflib.SequenceMatcher(None, n, c).ratio()
            best = max(best, r)
        if best >= cutoff:
            scored.append((best, v))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [v for _, v in scored[:limit]]


def add_vendor_alias(vendor_id: int, alias: str) -> None:
    """Remember an alternate spelling for a vendor (SELF-HEALING: a corrected wrong spelling becomes an
    alias, so the next receipt that prints it auto-resolves via vendor_by_name). Case-insensitive dedup;
    no-op if it already equals the vendor's name or an existing alias."""
    a = _vnorm(alias)
    if not vendor_id or len(a) < 2:
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, aliases FROM acc_vendors WHERE id=%s", (vendor_id,))
            row = cur.fetchone()
            if not row or a == _vnorm(row["name"]):
                return
            try:
                aliases = json.loads(row["aliases"] or "[]")
            except (ValueError, TypeError):
                aliases = []
            if any(_vnorm(x) == a for x in aliases):
                return
            aliases.append(alias.strip())
            cur.execute("UPDATE acc_vendors SET aliases=%s WHERE id=%s", (json.dumps(aliases), vendor_id))


def get_vendor(vendor_id: int) -> dict | None:
    """A vendor row by id (None if gone)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_vendors WHERE id=%s", (vendor_id,))
            return cur.fetchone()


def propose_vendor(name: str, created_by: int | None = None) -> int:
    """Staff create a NEW supplier on the spot (design §G7, decision A): usable IMMEDIATELY but flagged
    needs_review=TRUE for a one-tap owner confirm. The caller runs find_similar_vendors FIRST (the dedup
    gate) so this only fires on a genuinely new name. Returns the new vendor id (0 on an empty name)."""
    nm = (name or "").strip()
    if not nm:
        return 0
    with _db() as conn:
        with conn.cursor() as cur:
            # F6: atomic claim-by-UNIQUE — a concurrent duplicate loses the race and resolves to the existing
            # active vendor (no duplicate minted), instead of the old check-then-insert.
            cur.execute("INSERT INTO acc_vendors (name, created_by, needs_review) VALUES (%s,%s,TRUE) "
                        "ON CONFLICT (lower(name)) WHERE active DO NOTHING RETURNING id", (nm, created_by))
            r = cur.fetchone()
            if r:
                return r["id"]
            cur.execute("SELECT id FROM acc_vendors WHERE lower(name)=lower(%s) AND active "
                        "ORDER BY id LIMIT 1", (nm,))
            row = cur.fetchone()
            return row["id"] if row else 0


def confirm_vendor(vendor_id: int) -> None:
    """Owner accepts a staff-proposed vendor's name → clears needs_review (§G7). Idempotent."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_vendors SET needs_review=FALSE WHERE id=%s", (vendor_id,))


def list_unconfirmed_vendors() -> list[dict]:
    """Staff-proposed vendors still awaiting the owner's one-tap confirm (the interim ❗ list, §G7)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_vendors WHERE needs_review ORDER BY created_at")
            return list(cur.fetchall())


def vendor_item_history(vendor_id) -> list[dict]:
    """Per-item price/frequency for a vendor, from acc_receipt_lines ⋈ acc_receipts (design §G). Returns
    [{name, price_cents, n}] — `price_cents` = the most-recent known unit price (fallback the line total),
    `n` = how many times seen. Read-only. Powers the vendor priors (the read) + the Fix did-you-mean."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT l.raw_name AS name, l.unit_price_cents, l.line_total_cents
                           FROM acc_receipt_lines l JOIN acc_receipts r ON r.id = l.receipt_id
                           WHERE r.vendor_id=%s AND l.raw_name IS NOT NULL AND l.raw_name <> ''
                           ORDER BY l.id DESC""", (vendor_id,))
            rows = cur.fetchall()
    agg: dict = {}
    for x in rows:
        name = x["name"]
        price = x["unit_price_cents"] if x["unit_price_cents"] is not None else x["line_total_cents"]
        if name not in agg:                       # first seen (id DESC) = newest → its price is the latest
            agg[name] = {"name": name, "price_cents": price, "n": 0}
        agg[name]["n"] += 1
    return list(agg.values())


def vendor_priors_for(vendor_id, max_items=12) -> dict:
    """Soft priors for the read (design §G, mechanism A): the vendor's name + learned aliases (orig→english)
    + the items we usually buy from them (most-frequent first, with a typical price). Read-only; {} when the
    vendor is unknown. Fed to extract_receipt so it reads TOWARD plausible — a hint, never an anchor."""
    v = get_vendor(vendor_id)
    if not v:
        return {}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT orig_name, english_name FROM acc_item_aliases WHERE vendor_key=%s",
                        (vendor_id,))
            aliases = [{"orig": r["orig_name"], "english": r["english_name"]} for r in cur.fetchall()]
    items = sorted(vendor_item_history(vendor_id), key=lambda h: h["n"], reverse=True)[:max_items]
    return {"vendor_name": v["name"], "aliases": aliases, "items": items}


def _parse_json_list(j):
    try:
        return json.loads(j or "[]")
    except (ValueError, TypeError):
        return []


def rename_vendor(vendor_id, new_name) -> bool:
    """Correct a vendor's display name (§G7 V4). The OLD name is kept as an alias so receipts that still
    print it keep resolving (self-healing). Returns True if renamed."""
    nm = (new_name or "").strip()
    v = get_vendor(vendor_id)
    if not v or not nm or _vnorm(v["name"]) == _vnorm(nm):
        return False
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_vendors SET name=%s WHERE id=%s", (nm, vendor_id))
    add_vendor_alias(vendor_id, v["name"])             # old spelling → alias (name is now the new one)
    return True


def merge_vendors(dup_id, canonical_id, by=None) -> dict:
    """Merge a DUPLICATE vendor into the CANONICAL one (§G7 V4, OWNER action). ONE transaction (all-or-
    nothing): repoint receipts/payments/candidates + item-aliases dup→canonical, fold the dup's name +
    spelling-aliases into canonical's, move the dup's group if canonical has none, deactivate the dup, and
    write an audit row with the moved ids (traceable + reversible by undo_vendor_merge)."""
    if dup_id == canonical_id:
        return {"ok": False, "reason": "same vendor"}
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, tg_group_id, aliases, active FROM acc_vendors WHERE id IN (%s,%s)",
                        (dup_id, canonical_id))
            rows = {r["id"]: r for r in cur.fetchall()}
            if dup_id not in rows or canonical_id not in rows:
                return {"ok": False, "reason": "vendor not found"}
            dup, canon = rows[dup_id], rows[canonical_id]
            if not dup["active"] or not canon["active"]:   # F5: never re-merge an already-merged/inactive vendor
                return {"ok": False, "reason": "dup or canonical is inactive (already merged)"}
            cur.execute("UPDATE acc_receipts SET vendor_id=%s WHERE vendor_id=%s RETURNING id",
                        (canonical_id, dup_id))
            receipt_ids = [r["id"] for r in cur.fetchall()]
            cur.execute("UPDATE acc_payments SET vendor_id=%s WHERE vendor_id=%s RETURNING id",
                        (canonical_id, dup_id))
            payment_ids = [r["id"] for r in cur.fetchall()]
            cur.execute("UPDATE acc_receipt_candidates SET vendor_id=%s WHERE vendor_id=%s RETURNING id",
                        (canonical_id, dup_id))
            candidate_ids = [r["id"] for r in cur.fetchall()]
            # item-aliases: move where canonical has none for that orig; drop the rest (canonical wins)
            cur.execute("""UPDATE acc_item_aliases a SET vendor_key=%s WHERE a.vendor_key=%s
                           AND NOT EXISTS (SELECT 1 FROM acc_item_aliases b
                                           WHERE b.vendor_key=%s AND lower(b.orig_name)=lower(a.orig_name))""",
                        (canonical_id, dup_id, canonical_id))
            cur.execute("DELETE FROM acc_item_aliases WHERE vendor_key=%s", (dup_id,))
            # vendor-name spelling aliases: dup name + its aliases → canonical (dedup; skip == canonical name)
            canon_aliases = _parse_json_list(canon["aliases"])
            have = {_vnorm(x) for x in canon_aliases}
            for cand in [dup["name"]] + _parse_json_list(dup["aliases"]):
                if cand and _vnorm(cand) not in have and _vnorm(cand) != _vnorm(canon["name"]):
                    canon_aliases.append(cand.strip())
                    have.add(_vnorm(cand))
            # move the dup's group to canonical if canonical has none (one group = one vendor)
            if dup.get("tg_group_id") and not canon.get("tg_group_id"):
                g = dup["tg_group_id"]
                cur.execute("UPDATE acc_vendors SET tg_group_id=NULL WHERE id=%s", (dup_id,))  # free first (UNIQUE)
                cur.execute("UPDATE acc_vendors SET tg_group_id=%s, channel_kind=%s WHERE id=%s",
                            (g, "dm" if g > 0 else "group", canonical_id))
            cur.execute("UPDATE acc_vendors SET aliases=%s WHERE id=%s",
                        (json.dumps(canon_aliases), canonical_id))
            cur.execute("UPDATE acc_vendors SET active=FALSE WHERE id=%s", (dup_id,))    # deactivate the dup
            cur.execute("""INSERT INTO acc_vendor_merges (dup_id, canonical_id, merged_by, receipt_ids,
                           payment_ids, candidate_ids) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (dup_id, canonical_id, by, json.dumps(receipt_ids), json.dumps(payment_ids),
                         json.dumps(candidate_ids)))
            merge_id = cur.fetchone()["id"]
    return {"ok": True, "merge_id": merge_id, "receipts": len(receipt_ids), "payments": len(payment_ids),
            "candidates": len(candidate_ids), "dup_name": dup["name"], "canonical_id": canonical_id}


def undo_vendor_merge(merge_id) -> dict:
    """Reverse a merge's FINANCIAL repoint (§G7 V4): move the recorded receipts/payments/candidates back to
    the dup and reactivate it. (The alias/group folds are minor + not auto-reversed — redo by hand if
    needed.) Idempotent: an already-undone merge is a no-op."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_vendor_merges WHERE id=%s", (merge_id,))
            m = cur.fetchone()
            if not m or m["undone"]:
                return {"ok": False, "reason": "not found or already undone"}
            rids, pids, cids = (_parse_json_list(m["receipt_ids"]), _parse_json_list(m["payment_ids"]),
                                _parse_json_list(m["candidate_ids"]))
            dup_id, canon = m["dup_id"], m["canonical_id"]
            # F5: only move back rows that are STILL on the canonical — ones a LATER merge moved onward stay
            # with their newest owner (never strand them on the reactivated dup).
            if rids:
                cur.execute("UPDATE acc_receipts SET vendor_id=%s WHERE id = ANY(%s) AND vendor_id=%s",
                            (dup_id, rids, canon))
            if pids:
                cur.execute("UPDATE acc_payments SET vendor_id=%s WHERE id = ANY(%s) AND vendor_id=%s",
                            (dup_id, pids, canon))
            if cids:
                cur.execute("UPDATE acc_receipt_candidates SET vendor_id=%s WHERE id = ANY(%s) AND vendor_id=%s",
                            (dup_id, cids, canon))
            # reactivate the dup ONLY if it won't collide with an active same-name vendor (the F6 invariant)
            cur.execute("UPDATE acc_vendors SET active=TRUE WHERE id=%s AND NOT EXISTS "
                        "(SELECT 1 FROM acc_vendors v WHERE v.active AND v.id<>%s "
                        " AND lower(v.name)=(SELECT lower(name) FROM acc_vendors WHERE id=%s))",
                        (dup_id, dup_id, dup_id))
            reactivated = cur.rowcount == 1
            cur.execute("UPDATE acc_vendor_merges SET undone=TRUE WHERE id=%s", (merge_id,))
    return {"ok": True, "receipts": len(rids), "payments": len(pids), "candidates": len(cids),
            "dup_id": dup_id, "reactivated": reactivated}


def set_vendor_kind(vendor_id: int, kind: str) -> None:
    """Tag a vendor (§G9): 'supplier' (AP, default) · 'oneoff' (throwaway market buy — kept OFF the
    payable run / recurring views, still on the books) · 'internal' (Homemade/Delis — not an AP vendor
    we pay). Unknown kinds are ignored."""
    if kind not in ("supplier", "oneoff", "internal"):
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_vendors SET kind=%s WHERE id=%s", (kind, vendor_id))


def attach_vendor_channel(vendor_id: int, chat_id: int) -> None:
    """Link a vendor to the chat the listener sees it in — a supplier GROUP or a 1:1 DM (§G9), the
    paid-signal channel. Reuses tg_group_id (any listener-visible chat_id); channel_kind is inferred
    from the id sign (Telegram: users > 0 = DM, groups/channels < 0). Owner action, non-blocking
    (a vendor works fine groupless)."""
    kind = "dm" if (chat_id or 0) > 0 else "group"
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_vendors SET tg_group_id=%s, channel_kind=%s WHERE id=%s",
                        (chat_id, kind, vendor_id))


def _rank_channels(name, channels, limit=4, cutoff=0.4):
    """Pure: rank listener channels [{chat_id, title}] by fuzzy title-match to `name`, best first
    (substring = strong). Powers the §G9 'link the right group/DM with a tap' suggestion. Looser cutoff
    than auto-resolve because the owner confirms the pick."""
    n = _vnorm(name)
    if len(n) < 2:
        return []
    scored = []
    for c in channels or []:
        t = _vnorm(c.get("title"))
        if not t:
            continue
        r = 1.0 if (t in n or n in t) else difflib.SequenceMatcher(None, n, t).ratio()
        if r >= cutoff:
            scored.append((r, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def listener_channels_matching(name, limit=4):
    """Suggest the listener's chats (groups + DMs) whose title matches `name`, so a vendor's existing
    channel links with a TAP instead of scrolling hundreds (§G9). Reads the listener's ops_messages
    (latest title per chat); DEFENSIVE — returns [] if that table isn't present/populated yet."""
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT ON (chat_id) chat_id, chat_title AS title "
                            "FROM ops_messages ORDER BY chat_id, sent_at DESC")
                chans = list(cur.fetchall())
    except Exception:
        return []
    return _rank_channels(name, chans, limit=limit)


def list_vendors(active_only: bool = True) -> list[dict]:
    """All vendors (for an owner overview / the payable run)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM acc_vendors %s ORDER BY name" % ("WHERE active" if active_only else ""))
            return list(cur.fetchall())


# ── "Received Yet?" candidate flow — supplier-group photos (design §E3) ──
# A candidate is NOT a numbered receipt: it carries no money and never auto-pays. Every fork
# CLAIMS the row atomically from 'open' (S2/S3: flip-status-first) so a double-tap can't double-act
# — critically, can't create two numbered receipts from one supplier photo.

def add_candidate(vendor_id=None, src_chat_id=None, src_msg_id=None, src_chat_title=None,
                  photo_file_id=None, photo_sha=None, posted_by=None, is_test=False) -> int:
    """Log a supplier-posted photo as an OPEN candidate. Dedup on photo_sha: the same image
    re-posted returns the EXISTING candidate id (one supplier photo, one candidate)."""
    with _db() as conn:
        with conn.cursor() as cur:
            if photo_sha:
                cur.execute("SELECT id FROM acc_receipt_candidates WHERE photo_sha=%s", (photo_sha,))
                row = cur.fetchone()
                if row:
                    return row["id"]
            cur.execute("""
                INSERT INTO acc_receipt_candidates
                    (vendor_id, src_chat_id, src_msg_id, src_chat_title, photo_file_id, photo_sha,
                     posted_by, is_test)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (vendor_id, src_chat_id, src_msg_id, src_chat_title, photo_file_id, photo_sha,
                  posted_by, is_test))
            return cur.fetchone()["id"]


def get_candidate(cid: int) -> dict | None:
    """A candidate row joined to its vendor name (for the card)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT c.*, v.name AS vendor_name FROM acc_receipt_candidates c
                           LEFT JOIN acc_vendors v ON v.id = c.vendor_id WHERE c.id = %s""", (cid,))
            return cur.fetchone()


def get_candidate_by_sha(photo_sha: str) -> dict | None:
    """The candidate already logged for this exact supplier photo (dedup), or None."""
    if not photo_sha:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_receipt_candidates WHERE photo_sha = %s", (photo_sha,))
            return cur.fetchone()


def set_candidate_card(cid: int, card_chat_id: int, card_msg_id: int) -> None:
    """Remember where the candidate's card lives (the Expense group) so forks edit it in place."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_receipt_candidates SET card_chat_id=%s, card_msg_id=%s WHERE id=%s",
                        (card_chat_id, card_msg_id, cid))


def resolve_candidate(cid: int, status: str, resolved_by=None, note=None) -> bool:
    """Terminal fork (expected / ignored) — atomically claim from 'open'. True if THIS call resolved
    it (a double-tap returns False, never re-resolves)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE acc_receipt_candidates
                           SET status=%s, resolved_by=%s, note=COALESCE(%s, note), resolved_at=NOW()
                           WHERE id=%s AND status='open' RETURNING id""",
                        (status, resolved_by, note, cid))
            return cur.fetchone() is not None


def link_candidate(cid: int, receipt_id: int, resolved_by=None) -> bool:
    """'Already logged' fork — point the candidate at an existing receipt #, atomically from 'open'.
    No money moves (just records that this supplier photo == receipt #N). True if it claimed."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE acc_receipt_candidates
                           SET status='linked', receipt_id=%s, resolved_by=%s, resolved_at=NOW()
                           WHERE id=%s AND status='open' RETURNING id""",
                        (receipt_id, resolved_by, cid))
            return cur.fetchone() is not None


def claim_candidate(cid: int) -> bool:
    """Begin a promote — atomically move 'open' → 'promoting' (the claim). Only the winner of a
    double-tap gets True, so exactly one numbered receipt is ever created from one candidate."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE acc_receipt_candidates SET status='promoting'
                           WHERE id=%s AND status='open' RETURNING id""", (cid,))
            return cur.fetchone() is not None


def finalize_promote(cid: int, receipt_id: int, resolved_by=None) -> None:
    """Finish a promote — 'promoting' → 'promoted', stamping the numbered receipt it became."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE acc_receipt_candidates
                           SET status='promoted', receipt_id=%s, resolved_by=%s, resolved_at=NOW()
                           WHERE id=%s AND status='promoting'""", (receipt_id, resolved_by, cid))


def unclaim_candidate(cid: int) -> None:
    """Revert a claim back to 'open' if the promote failed (OCR/insert error) — no orphaned claim."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_receipt_candidates SET status='open' "
                        "WHERE id=%s AND status='promoting'", (cid,))


def recent_receipts_for_vendor(vendor_id: int, limit: int = 8, is_test: bool = False) -> list[dict]:
    """Recent receipts for a vendor — the 'Already logged → which #?' link picker (a read, no money).
    Distinct from the P2 payable-run open list (open_receipts_for_vendor)."""
    if vendor_id is None:
        return []
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, amount_cents, orig_currency, orig_amount, status, pay_method,
                                  created_at
                           FROM acc_receipts WHERE vendor_id=%s AND is_test=%s
                           ORDER BY id DESC LIMIT %s""", (vendor_id, is_test, limit))
            return list(cur.fetchall())


def find_lookalike_receipt(vendor_id, amount_cents, within_days: int = 7,
                           is_test: bool = False, exclude_id=None) -> dict | None:
    """Anti-double-pay look-alike (design §E3 layer 3): the most recent receipt with the SAME vendor
    and SAME amount within N days, or None. The owner confirms (Same / New) — never silent.
    exclude_id skips a given row (used on the direct path to ignore the just-created receipt)."""
    if vendor_id is None or amount_cents is None:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.*, v.name AS vendor_name FROM acc_receipts r
                           LEFT JOIN acc_vendors v ON v.id = r.vendor_id
                           WHERE r.vendor_id=%s AND r.amount_cents=%s AND r.is_test=%s
                             AND (%s IS NULL OR r.id <> %s)
                             AND r.created_at >= NOW() - make_interval(days => %s)
                           ORDER BY r.id DESC LIMIT 1""",
                        (vendor_id, amount_cents, is_test, exclude_id, exclude_id, within_days))
            return cur.fetchone()


def flag_dup_suspect(rid: int, dup_of: int) -> None:
    """Mark a freshly-captured receipt as a possible duplicate of #dup_of (same vendor+amount,
    recent) — a heads-up surfaced on the card. Informational only; the owner decides (the real
    double-pay PREVENTION is the P2 paid-flip / txn-ref dedup). Distinct path so the candidate
    flow, which already asked, never re-flags."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_receipts SET dup_suspect_of=%s WHERE id=%s", (dup_of, rid))


# ── P1 / P2 interface (build-the-interface-first, Arch-Rule-2; implemented in later phases) ──

def add_receipt(vendor_id=None, amount_cents=None, pay_method=None, orig_currency="USD",
                orig_amount=None, category=None, items_text=None, is_handwritten=False,
                photo_file_id=None, photo_sha=None, tg_chat_id=None, tg_msg_id=None,
                captured_by=None, is_test=False, invoice_no=None, receipt_date=None,
                tax_cents=None, supplier_account=None, bank_name=None, read_vendor=None) -> int:
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
                     supplier_account, bank_name, read_vendor)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'captured',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (vendor_id, amount_cents, pay_method, orig_currency, orig_amount, category,
                  items_text, is_handwritten, photo_file_id, photo_sha, tg_chat_id, tg_msg_id,
                  captured_by, is_test, invoice_no, receipt_date, tax_cents, supplier_account,
                  bank_name, read_vendor))
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


def save_receipt_lines(receipt_id, line_items, currency="USD", vendor_id=None) -> None:
    """Store the structured per-line detail (design §E11). A LEARNED alias (the bot's own memory or a
    past staff correction) for this vendor + original name OVERRIDES the model's fresh translation."""
    rows = []
    for li in (line_items or []):
        if not isinstance(li, dict):
            continue
        name = (li.get("name") or "").strip() or None
        orig = (li.get("name_orig") or "").strip() or None
        learned = get_item_alias(vendor_id, orig) if orig else None
        if learned:
            name = learned
        up, lt = _num(li.get("unit_price")), _num(li.get("line_total"))
        if name is None and orig is None and up is None and lt is None:
            continue
        rows.append((receipt_id, name, orig, _num(li.get("qty")),
                     to_usd_cents(up, currency) if up is not None else None,
                     to_usd_cents(lt, currency) if lt is not None else None))
    if not rows:
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.executemany("""INSERT INTO acc_receipt_lines
                (receipt_id, raw_name, orig_name, qty, unit_price_cents, line_total_cents)
                VALUES (%s,%s,%s,%s,%s,%s)""", rows)


def get_receipt_lines(receipt_id) -> list[dict]:
    """The structured lines for a receipt (for the card + the math check)."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_receipt_lines WHERE receipt_id=%s ORDER BY id", (receipt_id,))
            return list(cur.fetchall())


def get_item_alias(vendor_id, orig_name):
    """The learned English name for this vendor's original (as-written) item name, or None."""
    if not orig_name:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT english_name FROM acc_item_aliases "
                        "WHERE vendor_key=%s AND lower(orig_name)=lower(%s)",
                        (vendor_id or 0, orig_name.strip()))
            row = cur.fetchone()
            return row["english_name"] if row else None


def learn_item_alias(vendor_id, orig_name, english_name) -> None:
    """Remember (or update) an item's English name for next time — the model's translation OR a staff
    ✏️ correction. Keyed on vendor + the original as-written name (so the bot teaches itself)."""
    if not orig_name or not english_name:
        return
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO acc_item_aliases (vendor_key, orig_name, english_name)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (vendor_key, orig_name)
                           DO UPDATE SET english_name=EXCLUDED.english_name, updated_at=NOW()""",
                        (vendor_id or 0, orig_name.strip(), english_name.strip()))


def rename_receipt_line(line_id, new_name) -> None:
    """Apply a staff correction to one line's English name."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE acc_receipt_lines SET raw_name=%s WHERE id=%s",
                        ((new_name or "").strip(), line_id))


def get_receipt_by_sha(photo_sha: str) -> dict | None:
    """The receipt already logged for this exact photo (the dedup key), or None."""
    if not photo_sha:
        return None
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM acc_receipts WHERE photo_sha = %s", (photo_sha,))
            return cur.fetchone()


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
