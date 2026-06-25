# POSBusiness → Platform Harvest Plan

> **What this is.** POSBusiness (`C:\Users\Papa\POSbusiness`, repo `aaaeeeaaarrr/POSbusiness`) is a near-production
> Cambodia-first restaurant/bakery POS — FastAPI + SQLAlchemy + alembic backend (652 tests), React 19 + Vite +
> Tailwind 4 + Dexie frontend (60 Playwright), 12 migrations, go-live-ready for a cash-first USD-only pilot.
> Its POS depth dwarfs our platform's sales-log POS. This plan harvests its hard-won *rules and code* into our
> config-driven `core/` — **audit hash-chain first**.

## Governing principles (read before touching anything)

1. **Harvest, don't merge.** Do NOT fold the FastAPI/SQLAlchemy app into the platform — two stacks fight our
   PLATFORM_VISION rule ("reuse the hard-won RULES, rebuild the single-tenant Telegram-fused PLUMBING clean").
   We port *pieces* into `core/` (psycopg2, `orgs.config`, channel-agnostic), one bounded slice at a time.
2. **The external design is a REFERENCE, not gospel.** POSBusiness was *planned by an external advisor
   (ChatGPT)*. It is well-tested **for its own stack**, but we re-derive each piece against OUR architecture and
   invariants, change what doesn't fit (UUID→text org ids, JSON→JSONB, SQLAlchemy→psycopg2, the NULL-hash
   retrofit dance), and **re-test from scratch — we do not import its tests or trust its green CI**. A passing
   POSBusiness suite proves *their* port; ours must prove *ours*.
3. **Money & audit are HIGH-RISK.** Every money slice (shifts/Z/drawer/refunds, PayWay) gets staging proof on a
   real row + a second-opinion pass before it's called done (CLAUDE.md Real-Path Standard + State-Integrity Laws).
4. **One slice = one PR = its own gate + deploy.** No big-bang. Each phase ships behind a flag, inert until proven.
5. **Alternative kept open:** instead of porting POS internals, the platform could *tap POSBusiness as a service*
   ("be the POS, or tap an existing POS" — PLATFORM_VISION). This plan assumes harvest-into-core for audit + the
   money model; the tap-as-a-service option stays on the table for the full POS surface if the timeline favors it.

## Harvest order (value × independence × risk)

| # | Slice | Why this order | Risk | Effort |
|---|---|---|---|---|
| **1** | **Audit hash-chain** | **FIRST** — high value (upgrades our security/auditability LAW), fully self-contained, **no money**, no UI, no external creds | LOW | ~½ day |
| 2 | POS money model (shifts · Z-report · drawer reconcile · refunds/voids) | The expensive, months-of-correctness core; our POS is a toy without it | HIGH (money) | days |
| 3 | Offline-first idempotency (queue · idempotency key · safe retry) | Makes a real POS channel possible; pattern, not money | MED | 1–2 days |
| 4 | PayWay / KHQR payments | Real money + external creds; our POS card's "Accept KHQR" is only a planned toggle today | HIGH (money, owner-gated) | days |
| 5 | ESC/POS printing | Hardware; lowest urgency for a platform | LOW–MED | 1 day |
| — | RBAC depth | Fold into whichever slice needs it; we already have basic auth | LOW | as-needed |

---

## ▶ PHASE 1 + 1b — Audit hash-chain + external anchor (✅ SHIPPED 2026-06-25)

> **Phase 1b also done:** `core/audit_anchor.py` (`anchor_head` + `verify_anchors`) appends each org's chain head
> to a JSONL file **outside Postgres** (HMAC-signed if `ANCHOR_HMAC_KEY` set) + `scripts/anchor_audit.py` (cron) +
> `verify_audit_core.py --anchors` + `tests/test_audit_anchor.py` (3: anchor+verify PASS · a full DB-admin
> **re-chain → anchor FAIL** (the one thing the in-DB chain can't catch) · HMAC detects file tampering). **Ops to
> finish it for production:** set `ANCHOR_DIR` (off the DB host) + `ANCHOR_HMAC_KEY` (secrets), schedule
> `anchor_audit.py` nightly, and copy the anchor file offsite. Both tamper layers now exist.


> **Done:** `core/audit.py` (`write` + `_canonical` + `verify_chain` + `recent`; per-org chain; **per-org advisory
> lock** so concurrent writers can't fork) · `core_audit` table (NOT NULL hashes from row 1) · `log_config_change`
> now writes the chained mirror · `/audit` shows **🔗 Tamper-check: PASS/FAIL** · `scripts/verify_audit_core.py`
> CLI · `tests/test_audit_chain.py` (6: chain-links · content-tamper→FAIL · deletion→FAIL · genesis · per-org
> isolation · NOT-NULL · `log_config_change` round-trip). Adversarial pass: added the advisory lock + documented
> two honest limits (changes must be JSON-safe; a full DB-admin re-chain is caught only by the **anchor = Phase
> 1b**, deferred). Additive/inert — adds tamper-evidence to the existing log, no live behavior change.

Original plan below (kept for the record):

### Goal
Replace our flat `core_config_audit` (a plain who/what/when log, no tamper-evidence) with a **tamper-evident
hash-chained audit** — directly serving our PRODUCT-SECURITY law (#5 auditability) and the multi-tenant trust story.

### What POSBusiness gives us (the 3 tamper layers — reference)
- **`entry_hash`** = `SHA-256(canonical)` where `canonical = id|user|action|resource_type|resource_id|json(changes,sort_keys)|created_at`. → detects **content tampering** (edit any field, hash won't recompute).
- **`previous_hash`** = the prior row's `entry_hash` for that org (genesis = `"0"*64`). → detects **row deletion** (a gap leaves a dangling `previous_hash`).
- **anchor** (`audit_anchor_service.py`) = append-only JSONL file *outside Postgres*, optionally HMAC-signed, holding the chain head per close. → defends against a **DB-admin who rewrites rows AND recomputes hashes** (can't match the external record). This is the strongest layer.

Source files to read while porting: `backend/app/services/audit_service.py` · `backend/app/models/audit.py` ·
`backend/scripts/verify_audit_chain.py` · `backend/app/services/audit_anchor_service.py`.

### Target in our repo
- **New `core/audit.py`** — the writer + canonical + verifier helpers (channel-free, psycopg2).
- **New table `core_audit`** (additive migration via `init_core_db`): `id TEXT PK` (uuid4 string, generated
  Python-side so the hash is set *before* INSERT — no NULL-hash window, cleaner than their migration-0012 retrofit),
  `org_id TEXT`, `who TEXT`, `action TEXT`, `resource_type TEXT`, `resource_id TEXT`, `changes JSONB`,
  `at TIMESTAMPTZ DEFAULT NOW()`, `previous_hash CHAR(64) NOT NULL`, `entry_hash CHAR(64) NOT NULL`; indexes on
  `(org_id, at)`, `(resource_type, resource_id)`.
- **Route the existing audit through it:** `core.db.log_config_change` (and the wizard's config edits / card
  toggles / packaging / `/card/*/save`) call `core.audit.write(...)` so **config changes become hash-chained**.
  Keep `recent_config_audit` reading from the new table (or a view) so `/audit` is unchanged for the user.

### Concrete steps
1. **Schema** — add `core_audit` to `core/db.py::init_core_db` (NOT NULL hashes from row 1 — we have no legacy
   rows to backfill, so we *skip the whole 0012 nullable→not-null saga*).
2. **`core/audit.py::_canonical(id, who, action, resource_type, resource_id, changes, at)`** — exact field order,
   `json.dumps(changes or {}, sort_keys=True)`, `at.isoformat()`. Deterministic.
3. **`core/audit.py::write(org_id, who, action, resource_type, resource_id, changes=None)`** — in ONE psycopg2
   transaction: `SELECT entry_hash FROM core_audit WHERE org_id=%s ORDER BY at DESC LIMIT 1` → `previous_hash`
   (genesis `"0"*64` if none); generate `id=uuid4()`; compute `entry_hash`; single `INSERT` with both hashes.
   Per-org chain (org-scoped — matches our tenant model).
4. **Re-point writers** — `log_config_change` becomes a thin wrapper over `audit.write(action="config.update",
   resource_type="config", resource_id=path, changes={"old":…,"new":…})`. Grep every caller (config apply, card
   toggles, package switch, salary set, etc.) — they already flow through `log_config_change`, so this is one edit.
5. **`scripts/verify_audit_core.py`** — port `verify_audit_chain.py`: recompute each `entry_hash`; assert each
   non-genesis `previous_hash` exists as a real `entry_hash` in that org; print `PASS`/`FAIL` + the first break.
   Wire it into `/audit` (a "chain: PASS ✓" line) and the nightly digest.
6. **(Phase 1b, optional) anchor** — `core/audit_anchor.py`: append `{org_id, head_hash, row_count, at}` (HMAC if
   `AUDIT_HMAC_KEY` set) to `ANCHOR_DIR/core_audit_anchors.jsonl` on a cadence (nightly digest or a daily close) +
   `scripts/verify_audit_anchors.py`. Best-effort (never blocks the action; warns on failure).

### Re-test from scratch (our own tests — ignore theirs)
- `write` returns a row with **non-null 64-char** `entry_hash` + `previous_hash`.
- **Chain links:** row N's `previous_hash` == row N-1's `entry_hash` (same org).
- **Content-tamper:** mutate a row's `changes`/`action` in the DB → `verify_audit_core` returns FAIL at that row.
- **Deletion:** delete a middle row → FAIL (dangling `previous_hash`).
- **Genesis:** first row in an org has `previous_hash == "0"*64` and verifies.
- **Per-org isolation:** two orgs interleaved → two independent chains, each verifies.
- **No NULL ever:** an information_schema check that both hash columns are `NOT NULL`.
- **Round-trip through `log_config_change`:** a real config edit produces a chained row; `/audit` shows it; chain PASS.

### Adaptations from the ChatGPT/POSBusiness version (deliberate diffs)
- `org_id` is our **text tenant slug**, not a UUID FK — canonical + scoping use text.
- **psycopg2 + JSONB**, not async SQLAlchemy + JSON; one explicit transaction, no `flush` dance.
- **Start NOT NULL** (no nullable history) → no migration-0012 backfill, no genesis-NULL exemption in the verifier.
- `id` is a uuid4 **string** PK (stable, hash computed before INSERT) — same intent, simpler storage.

### Done = (Real-Path evidence block)
files · `init_core_db` migration applied on staging (independent `information_schema` read) · `core.audit.write`
chains proven (separate-process re-read) · `verify_audit_core` PASS on a real chain + FAIL on a planted tamper +
FAIL on a planted deletion · `log_config_change` round-trip · suite green · second-opinion pass · inert/no live
behavior change (it only *adds* tamper-evidence to an existing log). Then flip `/audit` to show the chain status.

---

## ▶ PHASE 2 — POS money model (sketch; HIGH-RISK, own session)
Port the **rules** (not the SQLAlchemy): shift open/close, **Z-report**, **cash-drawer reconciliation +
variance-reason gate**, **refunds/voids/credit-notes** (single-full-refund DB constraint), tax in/exclusive.
Source: `services/{shift_service,refund_service,tax_service,order_service}.py` + `models/{shift,order,refund}.py`.
Target: deepen `core/pos.py` + new `core/shifts_pos.py` / `core/till.py`. **State-Integrity Laws apply**
(flip-status-first, atomic claim, reversible). Staging proof on real rows + second-opinion. Replaces our toy
sales-log with real till handling. This is the big, valuable, dangerous one — its own focused arc.

## ▶ PHASE 3 — Offline-first idempotency (sketch)
Port the pattern: an **idempotency key** per order + a client queue (their Dexie/IndexedDB; ours could be the
web/Telegram adapter) + **safe retry** that never double-charges (server dedups on the key). Source:
`frontend/src/offline/*` + the order endpoint's idempotency handling. Target: an idempotency column/guard in
`core/pos.record_sale` + an adapter-side queue. Makes a *real* POS channel possible (current channels are online-only).

## ▶ PHASE 4 — PayWay / KHQR (sketch; HIGH-RISK, owner-gated)
Real ABA PayWay: generate-QR + check-transaction + callback signature verify. Source: `services/payway_service.py`
(has `!! UNCONFIRMED` markers on the callback sig — they never observed a real sandbox payment). Needs **owner
credentials** (never in chat — `.env`/secrets only) and a real sandbox/prod callback to confirm the HMAC scheme.
Target: a real implementation behind our POS "Accept KHQR" toggle. Defer until the money model (Phase 2) lands.

## ▶ PHASE 5 — ESC/POS printing (sketch)
Port `services/{escpos_service,printer_service,receipt_service}.py` — raw TCP ESC/POS to port 9100, receipt +
kitchen-ticket rendering. Hardware-bound (never tested on a real Epson/Sunmi). Lower priority for a platform;
pick up when a tenant needs physical receipts.

---

## What we are NOT taking (at least not as-is)
- **The frontend GUI** — the owner's own verdict (advisor-round §5): *"clean but shallow — an average POS."* It's
  the cheap, replaceable layer. Take its *flows*, rebuild the surface in our card/dashboard style (or deepen per
  the POSBusiness Phase-4 vision: per-item notes, configurable modifier UX, channel/tier price-matrix).
- **The FastAPI/SQLAlchemy/alembic plumbing** — we rebuild clean in `core/` per the vision.
- **Its test suite / green CI** — evidence for *their* stack; we re-prove on ours.

## Recommended first action
Execute **Phase 1** (audit hash-chain) end-to-end — it's self-contained, no money, high-value, and it upgrades a
standing security LAW. One PR, its own gate + staging proof, inert (adds tamper-evidence to the existing audit log,
changes no live behavior). Everything else is sequenced behind it.
