# Report / Expense / Payment System — Design Record (brainstorm, NOT built yet)

> **Status:** DESIGN / brainstorm only — nothing here is built. This is the next work item after the
> attendance go-live. Captured 2026-06-16 so the design survives across machines (chat is disposable).
> Owner is continuing this thread on another computer — **read this file first.**
>
> Two halves: (A) the owner's vision, (B) Claude's grounded analysis (what already exists vs the real
> gaps) + recommendations + the open decisions to make before building.

---

## A. The owner's vision (from the brainstorm message)

**Question 1 — where does it live?** Report done partly/nearly-all by the GM bot, or by a **new
"Accountant TWB" bot**? Pros & cons of a separate bot, considering updates/restarts and operational load.

**The flow the owner wants:**

**Expense Group** — receives photos of receipts (either already paid by **Cash**, or to-be-paid by **ABA**).
System auto-updates the DB on what's paid vs not paid before doing the report. Any unpaid ABAs are
reminded for the next report. Steps:
1. Photos of receipts.
2. Bot reads & **tags** the photo in a reply with all info. **Staff may correct** it.
3. Owner pays and shares the payment to the group.
4. Bot **recognises it's paid** — *how?* (the crux question).
5. Bot updates, tagging the payment in the group — and **confirms which receipt numbers** this payment
   is for. If there's a mistake in the payment, the bot messages the ABA Expense group to confirm.

**Report time** — the system just asks staff to **count the money** and tell us **how much Cash sales /
ABA sales**, then the bot does the rest and **types the normal report** we usually do (and we check it).
Maybe also continue the **photo of the POS terminal** (SambaPOS) so the bot can cross-check.
Owner asks: what am I missing, and what's the sequence?

**Other questions:**
- How will the bot **list receipt details in the Expense Group**? What if some info is missing
  (e.g. local handwritten receipts)?
- How to do this **as efficiently as possible — least API, mostly "Brain"** (rule-based)?

---

## B. Claude's analysis

### B0. THE KEY REFRAME — you're ~70% built already
This is not a from-scratch design. Verified in code (2026-06-16):

| Capability | Where it lives | What it does |
|---|---|---|
| **Receipt reading** | `ai_client.assess_receipt_photo` | ONE Haiku call: classifies *expense_sheet / pos_screen / receipt / other*, reads total (USD **or** Riel ៛), detects handwriting, reads vendor, extracts fields (expense-sheet day/night/ABA totals; POS `pos_kind`+`grand_total`). **Learns** per-vendor formats (`vendor_rules`) + uses past clarifications as few-shot. |
| **"Tag it, staff correct it" + escalation** | `gm_bot/clarify.py` | Pure ladder: unclear → ask in group → nudge every 10 min → back off 30 min if staff say "checking" (EN+KH phrases) → escalate to owner after 2 h. |
| **The typed report engine** | `gm_bot/finance.py` | PURE Brain: regex `parse_report_text` → `recompute()` (drawer = float + cash − cash expense; total sales = cash + ABA; Over/Lost = count − expected) → `format_correction()` (worked arithmetic). AI (`extract_daily_report_ai`, Sonnet) is **fallback only** when the free parser under-reads (≤2/day). Business day = 06:00→06:00 PP; mid vs final (dawn) classification. |
| **Photo ↔ report cross-check** | `gm_bot/reconcile.py` | expense-sheet totals == report cash/ABA expense; **POS grand total == report total sales**. |
| **Payment reading** | `ai_client.read_payment_amount` / `_pdf` | amount, currency, destination account, seller. |
| Groups | TWB REPORT (`-5136886404`); the GM bot already does REPORT receipt checks. | |

### B1. The GENUINE gaps (= the real new build)
1. **Per-receipt ledger** with **numbered rows + paid/unpaid state.** Today receipts feed *totals*
   (expense-sheet level), not individually tracked, numbered, payable items. **This is the spine.**
2. **Payment → receipt matching.** Reading an ABA transfer exists; *tying it to specific unpaid
   receipts and flipping them paid* does not.
3. **Unpaid-ABA carry-forward + reminder loop.**
4. **Report *generation* from minimal input** — today staff TYPE the whole report; the bot only
   parses/checks it. The owner wants: staff count cash + state sales → bot composes. Math engine exists;
   it's a re-org of inputs + a composer.
5. **A dedicated Expense Group workflow** (today the receipt role is in TWB REPORT).

### B2. Architecture — separate "Accountant TWB" bot vs keep in GM
**Recommendation: a separate Accountant bot — *because attendance went live 2026-06-16*.** The GM bot is
now a live, real-time, staff-facing service (check-ins, schedulers, location). Finance will be the
highest-churn build area. A separate bot means **finance deploys never blip live attendance.**

Pros (separate): deploy isolation from live attendance · clean code boundary (bot.py is ~7k lines) ·
independent failure · a clear "money" persona in only Expense+REPORT. 
Cons (separate): +1 token, systemd unit (`twbshop-accountant`), watchdog, log, error-handler wiring, a
one-time owner `/start`. 
**Integration cost is LOW** because the finance logic is already **pure + modular** (`finance.py`,
`reconcile.py`, `clarify.py` have no Telegram/DB coupling) — a new bot imports them, shares the Postgres
DB + shared modules (`ai_client`, `database`, `error_handler`). **The one gotcha: GM must HAND OFF its
REPORT receipt role** so two bots aren't talking in one group.

Timing is the only real question: **split now** (isolation is most valuable right when the other bot just
went live — Claude's lean) **vs build-in-GM-then-split** (the split is cheap *because* the logic is pure).
Either way: **keep all finance logic in a self-contained package so the move stays mechanical.**

### B3. "How does the bot know it's PAID?" — the crux
**Rule: never *infer* "paid" — always *confirm* it** (matches the project's no-silent-AI-guessing +
mandatory-confirmation-gate rules). Two mechanisms, cheapest first:
- **(a) Reply-to-receipt — ZERO API, zero ambiguity.** Every tagged receipt gets a **number** (`🧾 #14`).
  Owner pays by **replying** to that message with the ABA slip → Telegram gives `reply_to_message_id` →
  the bot knows the exact receipt. **Primary path.**
- **(b) Amount+vendor auto-match + ✅ tap.** Owner drops the ABA slip → `read_payment_amount` reads
  `$X → seller` (1 Haiku) → **Brain** finds unpaid receipt(s) for that vendor summing to $X → bot posts
  *"Looks like payment for #14 Atlas $138.60 — ✅ correct / ✏️ different."* The **match is arithmetic
  (free); the confirm is the gate.**
- **Mistake path** = the ✏️ branch → bot asks which receipt #s, or posts to the Expense group to confirm.
  A payment matching nothing stays **"pending match,"** never silently paid.
- The **receipt number is the spine** — humans + bot share one ID space (payments, corrections,
  disputes, reminders all reference `#14`).

### B4. Expense-Group flow (concrete)
```
1. Staff photo a receipt.
2. Bot (1 Haiku) → creates ledger row #14, replies:
     🧾 #14 · Atlas · $138.60 · ABA (unpaid)
     Items: beer keg ×2, soft drinks
     ✏️ reply to fix   ✅ looks right
3. Cash receipt → auto-PAID on the spot (cash = already paid).
   ABA receipt → stays UNPAID, joins the open list.
4. Owner pays → reply to #14 with the ABA slip → bot flips #14 PAID, tags it.
5. Report time → bot lists any still-UNPAID ABA → carries forward + reminds.
```
**Listing details / missing info / handwritten / Riel:** show what's read, `?` for what isn't, and
**only block on a missing AMOUNT** (the books need the number; vendor/items are best-effort).
`assess_receipt_photo` already returns `readable_partial` + `issues` + `is_handwritten` and handles Riel
(store currency per receipt; convert at the fixed **4000៛ = $1** the books already use). No clear total →
the **existing `clarify.py` ladder** asks staff to type it.

### B5. Report time
Math already exists — change the INPUTS. Minimal staff action: **count the cash** (only a human can) +
**snap the POS** (SambaPOS grand total = the *truth anchor* for sales; can even supply the cash/ABA
split so staff may not type sales at all). Then the bot: pulls **expenses from the ledger** (cash+ABA) +
the **float carried over** from yesterday's close → `recompute()` → **cross-checks total sales vs the POS
photo** → **types the standard report** → flags mismatches → asks to confirm. More trustworthy than today
because every number traces to a source (ledger / POS / carry-over), not hand-typing.

### B6. Efficiency — least API, mostly Brain
The right inversion (already your pattern): **the model converts pixels→numbers; the Brain decides
everything.** Keep it strict: ~1 Haiku per photo (receipt/payment/POS — `assess_receipt_photo` already
does classify+read+fields in one call); **matching, paid-state, report assembly, cross-checks, reminders,
dedup are pure Python (zero marginal API)**; reply-to-receipt = 0 API for the most common action; the
vendor-rule + few-shot **learning shrinks clarifications over time.** Net: the new system adds essentially
**no new API load.**

### B7. What the owner is missing / beyond
- **Float carry-over** — yesterday's close *is* today's float; never re-type it.
- **Idempotency / dedup** — same receipt photographed twice (mid+final, or two staff) = ONE row; same
  payment twice = one paid flip (OT-banking lesson: flip status FIRST, atomically).
- **Multi-currency** — store currency per receipt (Riel common on handwritten ones).
- **One transfer covering many receipts** — matching handles subset-sum, or the reply path sidesteps it.
- **Who can correct + audit trail** — log who edited what (the confirmation gate applies to corrections).
- **Cutoff** — a receipt at 11pm vs 2am = different business days (06:00→06:00 already defined — reuse).
- **Close-of-day invariant** — every receipt ends *cash-paid* or *ABA-matched*; anything "pending" is
  flagged. A `/audit`-style law (the pattern already exists).
- **POS digital export** — a file/export beats a photo read. There's already a "POS convergence, Postgres
  source-of-truth" strategy noted — check if SambaPOS can hand the numbers directly instead of a photo.

### B8. Suggested sequence
1. **Receipt ledger** (table + numbered intake + correct loop) — reuses `assess_receipt_photo` +
   `clarify.py`. Cash auto-paid.
2. **Payment matching** (reply-to-receipt first; amount+vendor + ✅ second; mistake → Expense group).
3. **Unpaid-ABA carry-forward + reminder.**
4. **Report assembly** (count cash + POS → ledger + float → `recompute` → cross-check → type → confirm).
5. **Close-of-day audit invariant.**
6. **(If not at step 0) split into the Accountant bot.**

---

## ▶ DECISIONS MADE (owner, 2026-06-16)
1. **Accountant bot — SEPARATE, NOW.** New `twbshop-accountant` service so finance churn never blips
   live attendance. Keep all finance logic in a self-contained package (`finance.py`/`reconcile.py`/
   `clarify.py` already pure) so the bot is a thin Telegram shell over them. GM hands off its REPORT
   receipt role at cutover.
2. **SambaPOS = DIGITAL access (photo is the fallback).** Owner's screenshot confirms SambaPOS 5.7.14
   runs on **Microsoft SQL Server**: instance `SERVER\SAMBASQL`, database **`WineBakery`**, `sa` login.
   So sales data (tickets, payments, cash/card split, grand total) is queryable from real SQL tables —
   the truth anchor, no photo read. CONSTRAINT: that MSSQL is on the shop's LAN PC; our bot is on the DO
   droplet. **Do NOT expose `sa`/MSSQL to the internet.** Pattern: a small **shop-PC agent** queries the
   local `WineBakery` DB and **pushes the day's numbers to our Postgres** (outbound only, no inbound
   ports); the bot reads from Postgres. POS photo + `assess_receipt_photo` stays as the cross-check /
   fallback when the agent is down. **Creds → `secrets.py` at build time, never in the repo.**
   OPEN SUB-CHECK before relying on it: confirm the shop PC can run a Python agent + reach the internet
   outbound (almost certainly yes), and map the exact `WineBakery` tables/columns for daily totals.

---

## C. DEEP DESIGN PASS (owner asked for "A→Z, deeper", 2026-06-16, max-effort brainstorm)

### C1. PAID-SIGNAL = pay into the SUPPLIER GROUP (owner's idea — ADOPT as PRIMARY)
Better than reply-to-receipt: it removes vendor-ID entirely. **The group IS the vendor** (group_id→vendor
map) → a payment slip in the "Atlas" group means vendor=Atlas with zero reading; only the AMOUNT must be
matched (subset-sum) to unpaid Atlas receipts. Receipt+payment co-locate if staff also snap receipts in
the supplier group. Matches what the owner already does (sends suppliers the ABA slip as proof) → no new
habit. **Guardrails:**
- **Bot is SILENT in supplier groups** (external-facing; suppliers are in them). It READS there, never
  posts. ALL confirms/flags go to a PRIVATE OWNER channel.
- **Confirm, never infer** (project rule): match → private "Atlas $138.60 → marks #14 paid ✅/✏️", one tap.
- Exact match easy; lump weekly payment = subset-sum over unpaid rows, flips the set; no subset matches →
  stays **"pending match"**, never silently paid, asks which.
- **Leak-detector:** payment into a group with NO unpaid receipt → "paid Atlas $X but nothing logged —
  missed a receipt?" (free control catching missing paperwork).
- Idempotent (slip seen twice = one flip, flip-status-first — attendance lesson).
- Fallbacks: payroll/rent/one-offs have no supplier group → private owner channel / "misc expense" group.

### C2. REFRAME — build the BOOKS, not just "the report"
The daily report is the tip. Real goal = the bot quietly becomes the accounting so the report + month-end
fall out free. Three always-current ledgers (all half-existing): **Accounts Payable** (what we owe each
supplier, per numbered receipt, paid/unpaid, aging) · **Cash book** (drawer: float + cash sales − cash
expenses − cash banked, reconciled to a physical count) · **Sales journal** (SambaPOS digital, truth
anchor). Then "report" = a render, and month-end = an export, not a reconstruction.

### C3. A→Z (stages + cross-cutting)
- **A. Ledger spine:** numbered row `#14`, state machine `captured→confirmed→(cash:paid | ABA:unpaid→
  matched:paid)` + `disputed/void`; each row tags **payment SOURCE** (cash drawer / which ABA acct) +
  **category** (drives cash recon AND expense reports).
- **B. Vendor master:** group_id→vendor, default category, their ABA acct, typical-amount range, terms,
  KH/EN aliases. Drives the group-signal + anomaly checks.
- **C. Capture effortless:** 1 Haiku/photo (`assess_receipt_photo`). In a supplier group vendor known →
  needs only **amount+date** (handwritten-KH gets easy). Block only on missing AMOUNT, rest `?`. Add
  **voice-note expenses** ("paid 20,000៛ for ice") for receiptless market/cash buys (1 transcription).
- **D. Recurring/expected:** rent/utilities/salary/standing orders pre-seeded as scheduled entries +
  reminded when due-and-unlogged (report covers the predictable, not just what got photographed).
- **E. Payment:** C1 supplier-group primary; reply-to-receipt/explicit "#14" secondary; cash auto-paid
  at capture (reduces drawer).
- **F. Reconciliation/controls (pure Python):** close-of-day invariant (every receipt cash-paid or
  ABA-matched; pending flagged) · cash recon (counted vs expected) · POS cross-check (SambaPOS total ==
  report sales) · anomaly flags (over-norm expense, new vendor, unreconciling round cash, dup
  receipt/payment).
- **G. Daily report generated:** human inputs shrink to **count cash** (+ optional sales, else from POS);
  bot pulls ledger expenses + float carry → `recompute()` → cross-check vs POS → compose standard report
  → flag → one-tap confirm. Every number traces to a source.
- **H. Period/insights:** AP aging (→reminders) · expense by category/vendor weekly/monthly · **supplier
  PRICE tracking** from receipts (free, ties to run_fetch_pricelists; "Atlas +8% this month") · cash-flow
  + gross-margin-lite (COGS vs sales) + payroll tie-in for P&L sketch · export to Google Sheet/CSV for the
  human accountant (Postgres stays source of truth).
- **I. Efficiency:** ~1 Haiku/photo; matching/aging/report/reminders/dedup/price/anomaly = pure Python;
  group-signal removes vendor-read, SambaPOS-digital removes POS-photo read; vendor-rules+few-shot shrink
  clarifications. Near-zero added API.
- **J. Channels (critical):** supplier groups = read-only/silent · internal expense group = staff capture
  + 1-tap corrections · private owner channel = all confirms/flags/report/month-end.
- **K. Failure modes:** payment-before-receipt · multiple ABA accts (store destination/payment) ·
  Riel/USD mismatch · lump/partial payments (track remainder) · blur/dup photos · new/unmapped supplier ·
  06:00→06:00 cutoff reuse · restart-safety (long-poll queue) · least-privilege SambaPOS agent · CAS/
  flip-first idempotency.

### C4. HIGHEST-LEVERAGE "make it easier" wins (least obvious)
1) pay-into-group (owner) · 2) voice-note cash expenses · 3) recurring-expense calendar · 4) payment-
without-receipt leak-detector · 5) supplier price alerts · 6) month-end becomes a non-event ·
7) FUTURE (pending Bakong): bot GENERATES the KHQR to PAY the supplier → knows AND executes payment.

### C5. SCOPE HONESTY — MVP vs dream
MVP (≈80% of the relief) = the SPINE: ledger + supplier-group paid-signal + daily report (SambaPOS sales
+ counted cash + ledger expenses + float). Aging, price tracking, exports, KHQR-pay, voice-notes are
valuable LATERS, not v1. Build the spine, prove on a week of real receipts, then layer.

### C6. OWNER ANSWERS (2026-06-16) → LOCKED design choices
**(a) Per-supplier Telegram groups ALREADY EXIST for most suppliers.** → group-signal works ~immediately;
P0 = map group_id→vendor (`/vendor link <name>` run inside each group). Bot joins/sits silent, reads.
**(b) Payments are ABA LUMP weekly/periodic** (one transfer clears several deliveries). → the matcher is
**subset-sum per vendor**, NOT 1:1.

**THE PAYABLE-RUN LOOP (the high-value win this style enables — bot runs the payment FOR the owner):**
1. Week: receipts pile per supplier group, numbered, unpaid (ABA).
2. Pay day: bot DMs a **payable run** — per supplier: "Atlas — #14 $138.60 + #17 $190 + #21 $83.70 =
   **$412.30** (oldest 6d)."
3. Owner pays that lump in ABA, drops slip in the Atlas group (existing habit).
4. Bot reads slip → vendor=Atlas (group), $412.30 → subset-sum/FIFO → flips #14/#17/#21 paid → private
   "✅ Atlas settled $412.30, 3 receipts."
Owner never computes "what do I owe Atlas this week" — bot hands the number, watches the pay, reconciles.

**MATCHER RULES (lump):** default **oldest-first (FIFO)**; **tolerance band** for Riel rounding
(~few-hundred-riel/0.5% = exact, else flag); exact/clean FIFO → auto-propose + owner ✅; ambiguous (fits
several combos) → propose oldest-first + show alternatives; < total owed → partial FIFO + remainder (flag
if it splits one receipt); > total owed → overpay OR missing receipt → leak-detector fires.

**AP AGING elevated** — because receipts sit ~a week unpaid, "what's outstanding per supplier" is core,
not a nice-to-have (it powers the payable run).

## ▶ REFINED PHASES (post-answers)
- **P0** — ledger schema + vendor↔group map (`/vendor link` in each group) [+ SambaPOS sub-check in parallel].
- **P1** — receipt capture in supplier groups (numbered, cash auto-paid, 1-tap correct; reuse
  `assess_receipt_photo`+`clarify.py`).
- **P2 (HEART)** — payable-run + lump subset-sum/FIFO matcher + private ✅ confirm + leak-detector.
- **P3** — AP aging + daily report (SambaPOS sales + counted cash + ledger expenses + float carry).
- **P4+** — supplier price tracking · Sheet/CSV export · voice-note expenses · KHQR-pay (pending Bakong).

## ▶ NEXT STEP (when work resumes)
Draft the **receipt-ledger schema** + **vendor master / group map** as the concrete P0 build (still
design until owner says build). SambaPOS sub-check in parallel: map `WineBakery` tables/columns for a
day's cash/ABA/grand-total + sketch the least-privilege shop-PC push agent.

---

## D. P0 SCHEMA DRAFT (2026-06-17 — DESIGN, not migrated; review before build)

> Proposed DDL for a new `init_accounting_db()` in `shared/database.py`, following the project's existing
> conventions (SERIAL PK · status TEXT with an inline enum comment · TIMESTAMPTZ DEFAULT NOW() · `is_test`
> flag · `IF NOT EXISTS` + additive `ALTER … ADD COLUMN IF NOT EXISTS`). Money is stored as **integer
> cents in USD** (`amount_cents`) — one canonical unit, no float drift; Riel is converted at the fixed
> **4000៛=$1** the books already use, with the *original* currency/amount kept for the audit trail.
> Three tables map to the three ledgers in §C2: **vendors** (master) → **receipts** (Accounts Payable
> spine) → **payments** + **payment_allocations** (the lump→receipt matcher, §C6).

### D1. `vendors` — the master / group map (§B-vendor, C3-B)
```sql
CREATE TABLE IF NOT EXISTS acc_vendors (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,            -- canonical display name ("Atlas")
    tg_group_id   BIGINT UNIQUE,            -- the supplier Telegram group → THE paid-signal (C1); NULL = no group
    aliases       TEXT DEFAULT '[]',        -- JSON list, KH/EN spellings for matching
    category      TEXT,                     -- default expense category (drives cash-recon + reports)
    aba_account   TEXT,                     -- their usual ABA destination (anomaly check)
    typical_min_cents INTEGER,              -- typical-amount band low  (anomaly / new-vendor flags)
    typical_max_cents INTEGER,              -- typical-amount band high
    terms_days    INTEGER,                  -- payment terms (powers AP aging / payable run)
    active        BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_acc_vendors_group ON acc_vendors (tg_group_id);
```
P0 populate: `/vendor link <name>` run *inside* each supplier group (captures `tg_group_id` from the
chat) — owner-only, mirrors the existing `/joined` / link-style admin commands.

### D2. `acc_receipts` — the spine (numbered AP rows, §B1, C3-A)
```sql
CREATE TABLE IF NOT EXISTS acc_receipts (
    id            SERIAL PRIMARY KEY,       -- THIS is the human-facing "#14" (one shared ID space)
    vendor_id     INTEGER REFERENCES acc_vendors(id),
    biz_date      DATE,                     -- business day (06:00→06:00 PP cutoff, reuse finance.py)
    amount_cents  INTEGER,                  -- canonical USD cents; NULL until a total is read/typed
    orig_currency TEXT DEFAULT 'USD',       -- 'USD' | 'KHR' (audit trail)
    orig_amount   NUMERIC,                  -- as-written amount in orig_currency
    pay_method    TEXT,                     -- 'cash' | 'aba'  (cash → auto-paid at capture)
    category      TEXT,                     -- defaults from vendor, correctable
    items_text    TEXT,                     -- best-effort line items (never blocks)
    is_handwritten BOOLEAN DEFAULT FALSE,
    status        TEXT DEFAULT 'captured',  -- captured|confirmed|paid|disputed|void
                                            -- ABA path: confirmed→(matched)→paid ; cash: →paid at capture
    photo_file_id TEXT,                     -- Telegram file_id of the receipt image
    photo_sha     TEXT,                     -- dedup key (same photo twice = one row, C3 idempotency)
    tg_chat_id    BIGINT,                   -- where it was captured (supplier group vs expense group)
    tg_msg_id     BIGINT,                   -- for reply-to-receipt secondary paid-signal (B3-a)
    captured_by   BIGINT,                   -- Telegram user id (audit trail, who logged it)
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    is_test       BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_acc_receipts_vendor_status ON acc_receipts (vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_acc_receipts_bizdate ON acc_receipts (biz_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_receipts_sha ON acc_receipts (photo_sha) WHERE photo_sha IS NOT NULL;
```
Notes: `photo_sha` UNIQUE (partial, NULLs allowed) gives dedup at the DB layer (flip-status-first lesson).
`amount_cents` NULL is the ONLY thing that blocks a row from being payable (B4); vendor/items are
best-effort. State machine matches §C3-A.

### D3. `acc_payments` + `acc_payment_allocations` — the lump matcher (§C6)
A lump ABA transfer clears several receipts → a payment is **1 row**, its split across receipts is
**N allocation rows** (subset-sum / FIFO writes these). This keeps a payment auditable as one real-world
event while flipping many `#`s paid.
```sql
CREATE TABLE IF NOT EXISTS acc_payments (
    id            SERIAL PRIMARY KEY,
    vendor_id     INTEGER REFERENCES acc_vendors(id),  -- from the group it landed in (C1, zero-read)
    amount_cents  INTEGER,                  -- total transfer amount (canonical USD cents)
    orig_currency TEXT DEFAULT 'USD',
    orig_amount   NUMERIC,
    paid_at       TIMESTAMPTZ,              -- slip timestamp
    aba_account   TEXT,                     -- destination read off the slip
    slip_file_id  TEXT,                     -- Telegram file_id of the payment slip
    slip_sha      TEXT,                     -- dedup (same slip twice = one flip, C3)
    tg_chat_id    BIGINT,
    tg_msg_id     BIGINT,
    status        TEXT DEFAULT 'pending',   -- pending|confirmed|unmatched  (never silently 'paid' anything)
    confirmed_by  BIGINT,                   -- owner who tapped ✅ (the confirm gate, B3)
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    is_test       BOOLEAN DEFAULT FALSE
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_acc_payments_sha ON acc_payments (slip_sha) WHERE slip_sha IS NOT NULL;

CREATE TABLE IF NOT EXISTS acc_payment_allocations (
    id            SERIAL PRIMARY KEY,
    payment_id    INTEGER REFERENCES acc_payments(id),
    receipt_id    INTEGER REFERENCES acc_receipts(id),
    amount_cents  INTEGER,                  -- how much of the payment applied to this receipt
                                            -- (= receipt total normally; partial allowed, C6 remainder)
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (payment_id, receipt_id)
);
CREATE INDEX IF NOT EXISTS idx_acc_alloc_receipt ON acc_payment_allocations (receipt_id);
```

### D4. State-integrity / invariants this schema must honour (ties to §C3-F, STATE_INTEGRITY_LAWS)
- **S2 idempotent paid-flip:** flip `acc_receipts.status='paid'` FIRST (atomic `UPDATE … WHERE
  status<>'paid' RETURNING`), then write allocations — a redelivered slip can't double-pay. `slip_sha` /
  `photo_sha` UNIQUE are the structural backstops.
- **S3 atomic claim on match:** the matcher CAS-claims each receipt before allocating (no check-then-write
  race between two slips touching the same `#`).
- **Close-of-day invariant (future `/audit` law):** every `acc_receipts` row for a closed biz_date is
  `paid` or `void`; anything `captured/confirmed` past cutoff is FLAGGED. A receipt's `amount_cents` must
  equal Σ its allocations once `paid` (no over/under-allocation). Leak-detector (§C1): a `confirmed`
  payment whose allocations < its amount, OR a payment in a vendor group with no open receipts → flag.
- **S4 shown=true:** the `#14` shown in chat IS `acc_receipts.id`; the "$ owed Atlas" in the payable run
  = Σ unpaid `amount_cents` for that vendor — derived, never stored stale.

### D5. OPEN QUESTIONS before this becomes a migration
1. **Receipt numbering** — global `SERIAL` (`#14` unique forever, simplest, recommended) vs per-day/
   per-vendor sequence (prettier "#3 today" but needs a counter + collision handling). Lean: global serial.
2. **New-bot vs GM ownership of `init_accounting_db()`** — decision §157 says separate `twbshop-accountant`
   NOW; so the new bot's `run_*.py` calls `init_accounting_db()` at startup. Confirm before wiring.
3. **`amount_cents` integer-cents** assumes USD-cents granularity is enough; Riel buys (20,000៛=$5.00)
   convert clean at 4000៛=$1. Confirm no sub-cent need (there isn't for cash books).
4. Whether `acc_` prefix is wanted (keeps the finance package's tables visually grouped + greppable) —
   used here for that reason; easy to drop.

---

## E. THIRD DEEP PASS (2026-06-18) — capture UX, anti-double-pay, stock catalog, owner menu, test mode

> Owner brainstorm continued. This pass **refines** earlier sections; where it differs, the note here
> wins (flagged inline): capture is now in ONE internal Expense group (refines §C1), and the payment slip
> is **relayed owner→bot→supplier** (refines §C1/§C6 — the subset-sum matcher drops to a *fallback*).

### E1. Capture model — ONE Expense Group + the living receipt card  (REFINES C1)
- Staff snap **all** receipts into ONE internal **Expense Group** (not per-supplier). Supplier groups are
  now used by the bot only to (i) **post the payment slip** and (ii) be **watched** (by the listener) for
  price/account changes — the bot still never chats there.
- **Vendor ID:** read from the receipt if the name is printed; else the staffer **taps the vendor** from a
  short list (one tap). **The bot learns** — a confirmed tap stores the receipt's printed name → that
  vendor, so it auto-IDs next time. A *remembered mapping*, not an AI guess (deterministic, auditable, $0).
- **ONE bot reply per photo = the living status card**, edited in place through its life:
  `DRAFT (read + math-checked) → CONFIRMED (staff ✓ paper-vs-bot) → [💵 Cash-paid | 🏦 For ABA] → PAID`.
  Persistent **✏️ Edit/Fix** button — the staffer's correction edits the card; no extra messages.
- **Math check before listing:** compare Σ(line items **incl. tax/VAT/delivery/rounding**) to the printed
  total; on a gap **SHOW it** ("items add to $X, receipt says $Y — check the paper"), never block. Tax
  tolerance so it doesn't cry wolf on every normal receipt.

### E2. Payment — owner→bot→supplier slip relay  (REFINES C1/C6; makes matching EXPLICIT)
- After staff CONFIRM + tap **For ABA**, the bot DMs the **owner**. Owner pays in ABA and sends the slip
  **to the bot (DM)**. Bot validates → **posts the slip into the supplier's group** → edits the
  Expense-group card to **"ABA Paid ✅"**.
- Because the owner pays from a *specific receipt's DM prompt*, the bot **knows which receipt(s)** the slip
  covers → the subset-sum/FIFO matcher (§C6) becomes a **fallback** for lump payments made out-of-band.
  The payable-run (§C6) still drives *what* to pay; the relay makes the *match* explicit.
- **The wrong-amount ladder** (each surfaces as an attention card to the owner; the **txn ref** is the
  strong key — owner's refinement):
  - txn ref already seen → same slip → ignore (dedup).
  - **DIFFERENT txn ref, same vendor + amount, on an ALREADY-PAID receipt → 🚨 accidental double-pay.**
  - slip < receipt → partial, "still owe $Z." · slip > receipt → "covers #14+#17+#21?" (the set).
  - wrong vendor → "looks like Beer Co, retry?" · Riel vs USD → convert at 4000៛ · unreadable → retype.
  - Only an **exact, unambiguous** match auto-posts to the supplier + flips paid.

### E3. Anti-double-pay — defense in depth (the owner's worry, answered)
Risk: a supplier posts their own receipt copy a day later → re-logged → paid twice. Layers:
1. Numbered ledger = sole truth; a **paid receipt can't be paid again** (S2 flip-first).
2. `photo_sha` → identical image = "already #14."
3. **Look-alike:** same vendor + total + within N days → "same as #14 (paid 2d ago)? [Same][New]."
4. **Supplier's own invoice #** (when printed) = strongest dedup key.
5. Payment side: slip **txn-ref** dedup + the double-pay alert (E2).
- PLUS the **"Received Yet?" candidate flow** for supplier-group photos: a photo a supplier posts in THEIR
  group is forwarded to the Expense group as a **CANDIDATE (never auto-numbered)**. First question forks:
  `Not yet received → park as "expected" (order/quote)` · `Already logged → link to #14, ignore` ·
  `New & received → run the look-alike guard → THEN promote to a numbered receipt`.
  **▶ BUILT 2026-06-19** (lane/accountant, not deployed): `acc_receipt_candidates` table + the four forks +
  look-alike guard (same vendor+amount ≤7d) + claim-first promote (no double-#) in `accountant/{db,capture,
  bot}.py`; bot stays silent in the supplier group, candidate card headed "From <vendor> · <group>". Pure
  logic proven (21 tests); DB lifecycle tests written (run on the staging machine). NEXT = P2 (HIGH-RISK).

### E4. Listener — free eyes in supplier groups (verified in code 2026-06-18)
- `ops_intelligence/listener.py` is a Telethon **user account**: streams every message to `ops_messages`,
  **zero Claude API calls**. Listening is free; AI cost only on a separate, gated analysis step.
- Watching a supplier group for an **account-number change** = regex over already-stored text = **free** →
  a pending-queue item to confirm.
- **Division of labour:** listener = **eyes** in supplier groups (a photo / account-change posted there);
  accountant bot = **hands** in the Expense group (gets photo *bytes* via Bot API → OCR → cards). The
  listener stores that a photo *exists*, not its bytes — so OCR needs the accountant bot's direct access.
- **Open:** confirm the listener account is a *member* of each supplier group (then the feed already exists).

### E5. Price tracking + supplier-message guardrail (needs line items)
- Store receipt **line items** (name/qty/unit/line-total). Compare each item's unit price to last-seen for
  that vendor → up / down / new-product / substitution.
- **Guardrail:** the bot **never messages a supplier on its own.** It DMs the **owner**
  ("Atlas onion $1.20→$1.50 +25% [Ask Atlas][It's fine][Ignore]"); the owner triggers any supplier
  message. Confirm-never-infer applies double to outward-facing (third-party) actions.

### E6. Stock — three layers + catalog seed (answers "what's it good for")
- **Three layers:** (1) **Item catalog** — canonical name, category, unit, min, reorder-qty, candidate
  suppliers — **seeded from the owner's ~143-item reorder sheet** (~13 categories, multi-supplier);
  (2) **Price history** — per item, per supplier, learned from receipts; (3) **Item aliases** — canonical
  name ↔ each supplier's slightly-different name, **learned from confirmations**.
- The sheet is a **re-order sheet, not a price list** (Item·Category·Unit·Min·Order-qty·Supplier(s)·
  "unit correct?"). It seeds the **catalog**; **prices come from receipts over time.**
- Sheet notes: some "suppliers" are **internal** (Homemade, Delis) → **NOT AP vendors we pay** (the
  accounting vendor list ⊂ the stock supplier list). `[X]` items (Strawberry purée, Oregano, Marjoram,
  Basil) look **discontinued** → skip on seed. Units are uncertain ("is unit correct?") → refine from
  receipts.
- **What stock gives:** paperless goods-in · inventory value · smart reorder · **🎯 3-way reconciliation**
  (bought [accountant] + sold [POS] vs counted [stock] → shrinkage/theft/waste — the headline) · true
  margin / COGS.
- New item on a receipt → **pending-queue**: "recurring catalog item, or once-off purchase?"

### E7. Stock ↔ accountant boundary — shared TABLE, not shared code (S5 seam; answers Q3)
- The two lanes **never edit each other's code.** The seam is shared DB tables in the **`shared` zone**:
  the item catalog + aliases, and a **`stock_movements`** ledger. Accountant inserts a `+received` movement
  when a receipt confirms (a one-line write to a shared table); stock inserts `−used / −counted` and reads
  on-hand `= SUM(qty_delta)`. Each lane edits only its own files; the shared schema changes via an
  integrator merge (which the lane-guard already flags as "shared — concerns ALL lanes").
- **Stock-from-receipt is gated on the item alias being resolved:** an unmapped supplier line → pending
  queue ("map Atlas 'T55 Flour' to which catalog item?") and the movement waits until mapped. Graceful.

### E8. Owner menu + pending-decisions queue (the time-saver)
```
/menu  (accountant, owner-only)
  💵 To Pay   — everything awaiting your ABA, tap to pay      ← the worklist
  🧾 Receipts — recent · by vendor · paid/unpaid · find by #
  🏦 Vendors  — list · saved account # · group link · spend
  📦 Stocks   — catalog · low-stock · price history · cheapest-supplier
  ❗ Pending  — the decisions queue
  📊 Reports  — midday / final · re-show · export
```
**Pending queue** = ONE list of everything needing your call (new vendor recurring/once-off · new item
recurring/once-off · price change · account-number change · wrong-amount ladder · unmapped item).
Batch-clear when convenient = saves your time.

### E9. Report cutoff + cash recon + "count the cash" target (answers Q2)
- **Cutoff = the moment the bot RELEASES the sheet** — a receipt counts if `paid_at ≤ released_at`. Each
  report covers window `(last_release → this_release]` → no double-count, no gap.
- **Cash-paid is always from the drawer** → reduces expected drawer.
- **Target:** the only staff action at report time is **"count the cash, tell me $X."** Bot has float
  (yesterday's close) + sales (POS) + expenses (ledger) → `expected = float + cash_sales − cash_expenses`;
  `over/short = counted − expected` → composes the standard report instantly.
- **SCOPE HONESTY (the one dependency):** "count the cash only" holds **once SambaPOS sales are wired**
  (the shop-PC push agent, decision §157). Until then, staff/owner also gives the POS sales figure
  (number or photo). v1 keeps recon simple (float + cash_sales − cash_expenses); cash-outs / float top-ups
  refine later.

### E10. Test mode — real-path, isolated data (owner's plan, mirrors attendance)
Owner plays staff in the **real** Expense group + makes a **fake supplier group**. Reuse the proven
`is_test` pattern (`docs/ATTENDANCE_TEST_MODE.md`): **real** buttons, OCR, matching, card edits — only the
**data** is `is_test`-tagged so it never touches real reports/ledger/stock; `/testreset` wipes it.
Satisfies Rule 1 (one real system, isolate data only). The fake supplier group makes the slip-relay +
price/account-watch paths real too.

### E11. SCHEMA ADDITIONS (extends §D; design, not migrated)
New tables/columns implied by this pass. **`acc_items`, `acc_item_aliases`, `stock_movements` live in the
SHARED zone** (read/written by both the accountant and stock lanes, per E7); the rest are accountant-owned.
- **`acc_receipt_lines`** (`receipt_id` → acc_receipts, `raw_name`, `item_id` NULL → acc_items, `qty`,
  `unit`, `unit_price_cents`, `line_total_cents`) — feeds the math check + price history + stock movements.
- **`acc_items`** (catalog: `name` canonical, `category`, `unit`, `min_qty`, `reorder_qty`, `active`) —
  seeded from the 143-item sheet.
- **`acc_item_aliases`** (`item_id`, `vendor_id`, `supplier_name`) UNIQUE(`vendor_id`,`supplier_name`) —
  learned canonical↔supplier name mappings.
- **`stock_movements`** (`item_id`, `qty_delta`, `unit`, `reason` 'received|used|counted|waste|adjust',
  `source` 'receipt|count|pos', `ref_id`, `at` TIMESTAMPTZ, `is_test`) — the shared accountant↔stock seam;
  on-hand = SUM(qty_delta) per item.
- **`acc_pending_decisions`** (`kind`, `payload` JSON, `status` open|done, `created_at`, `resolved_by`,
  `resolved_at`, `is_test`) — the queue behind ❗ Pending.
- **`acc_payments`** += **`txn_ref` TEXT** (bank-slip transaction id — dedup + double-pay key) + a UNIQUE
  partial index on (`vendor_id`, `txn_ref`).
- **`acc_vendors`** += **`printed_names` JSON** (learned receipt-name hints → auto vendor-ID, E1).

### ▶ PHASES — 2026-06-18 UPDATE (supersedes the §"REFINED PHASES" list where they differ)
- **P0** — ledger + vendor↔group map **+ seed `acc_items` from the sheet + `is_test` test-mode plumbing**.
- **P1 (capture)** — ONE Expense group · living status card · ✏️ Edit/Fix · math check · **vendor-learning**
  · cash auto-paid · "Received Yet?" candidate flow. (Reuse `assess_receipt_photo` + `clarify.py`.)
- **P2 (HEART, HIGH-RISK)** — **owner→bot→supplier slip relay** + wrong-amount **txn-ref ladder** +
  double-pay defense; subset-sum/FIFO as the lump **fallback**; per-step owner approval, no live money
  until each step is approved.
- **P3** — daily report (release-cutoff windows · cash recon · count-the-cash) · AP aging · **pending
  queue** · **owner menu**.
- **P4+** — price tracking + supplier-message-with-approval · **stock 3-way reconciliation** (with the
  stock lane, via `stock_movements`) · Sheet/CSV export · voice-note expenses · KHQR-pay (pending Bakong).

---

## F. (2026-06-18) Data-collection mandate + CSV exports + broadcast price-scan

### F1. Daily receipt-archive cron (DONE 2026-06-18)
The report group lost ~204 early receipts to manual deletion (the listener kept metadata only, not
bytes). Fix: a daily cron archives every new photo from TWB REPORT to
`/root/TWBshop/receipts_archive/TWB_REPORT/` (gitignored, server-only) via the read-only
`ops_listener` session — `scripts/fetch_report_receipts.py` (idempotent, skips existing), cron
**15:15 PP daily**. ~135 MB for 3 wks, ~2 GB/yr against 39 GB free → **no compression** (receipts
must stay legible). Supplier *broadcast* groups are deliberately NOT archived (volume — see F4).

### F2. "Collect a lot of good details" — schema mandate (owner)
Owner wants rich CSVs, so capture generously as we go:
- **acc_vendors enrich:** `payment_account_no`, `bank_name` (NOT all ABA — owner pays from ABA
  regardless), secondary accounts (JSON), contact name/phone, `terms_days`, typical-spend band,
  `last_order_at`, `total_spent`, aliases, notes.
- **acc_items enrich (stock lane):** canonical name, category, unit, pack/qty, on-hand, `min_qty`,
  `reorder_qty`, candidate suppliers, per-supplier price+pack, cheapest supplier, last price,
  price trend, aliases. (More columns than the 3 reorder-sheet images.)

### F3. CSV exports (owner-requested)
1. **Products CSV** — per item: F2 detail + **price per supplier per pack/qty + "who wins" (cheapest)**
   + min/reorder + how-much-to-order. The stock lane's headline export.
2. **Suppliers CSV** — per vendor: payment account + bank + contact + terms + spend + group + aliases.
3. **Bonus ideas:** AP aging (owed per supplier, days outstanding) · monthly expense by category/vendor
   · price-change log · cash-vs-ABA spend · receipt-ledger dump · payment history · recurring-expense
   calendar · 3-way reconciliation (bought/sold/counted).

### F4. Broadcast price-scan (PARKED — after the accountant + stock lanes are solid)
On-demand only (owner at the terminal): scan recent photos+messages of the BROADCAST groups
(`scripts/vendor_seed.py::BROADCAST`) and compare to our current product prices → flag cheaper
options. "No API for these spammers": text promos are free (regex); photo promos need vision, so do
it SELECTIVELY + on demand, never as routine spend. Do NOT bulk-store their photos.

---

## G. STEP 2 — vendor-aware reading (priors-in + price "did-you-mean")  (2026-06-21 — DESIGN; owner-locked choices; NOT built)

> Follows the **session-50 read fix** (`temperature=0` + honest `?` display, commit `ef818cc`). That made
> the read STABLE; this makes it SMARTER over 1–3 receipts. **Owner-locked (2026-06-21):** (i) **cold-read
> + post-read did-you-mean** — NO two-pass re-read · the **"did-you-mean" lives in the ✏️ Fix flow**, the
> card stays clean. Builds on what already exists — **NO new tables, NO new API call.**

### G0. The problem this closes
The session-50 fix stopped the SAME receipt reading differently each time, but the read is still **cold**:
`extract_receipt` knows nothing about the vendor. A learned alias only helps if the *next* read produces
the byte-identical `orig_name` — brittle (this was "Gap 1"). Step 2 gives the read memory.

### G1. Mechanism A — vendor priors INTO the read (fix the error at source)
- `extract_receipt` gains an optional `vendor_priors` arg (interface-first per Arch-Rule-2; `None` = today's
  cold read, unchanged).
- Priors `= {vendor_name, aliases:[{orig,english}], items:[{english, typ_price_cents, unit}]}`, built from
  `acc_item_aliases` (`orig→english`) + a price/items query over `acc_receipt_lines`. Keep it **SHORT**
  (this vendor's actual history, top ~N by frequency) — long context anchors AND costs tokens.
- Prompt block (soft-hint, **anti-anchor**): *"Likely from <vendor>. Bought before: ដំឡូង=potato (~$1.20)…
  Read TOWARD these when ambiguous, but read what is ACTUALLY written — they may sell something new."*
- **Applied ONLY when the vendor is known BEFORE the read** — supplier-group capture (zero-read: the group
  IS the vendor) or after a vendor tap. The first untapped Expense-group photo stays a **cold read**
  (decision i) → Mechanism B covers it.

### G2. Mechanism B — price/attribute "did you mean?" in the ✏️ Fix flow (graceful failure)
- Targets **exactly the lines that render with a `?` today** (handwritten + no confirmed alias — reuse the
  session-50 confidence signal in `capture.render_card`; no new heuristic).
- **Pure-Python ranking (zero API):** for a `?` line, rank this vendor's historical items by price proximity
  (`|line unit/total − item typical|`) + qty/unit plausibility → top 1–3 candidates.
- **UX (Fix flow — card stays clean):** today ✏️ Fix sets `acc_fix` and asks for a typed reply
  (`1 Apple` = rename line 1 + `learn_item_alias`, `bot.py::on_text`). Step 2 adds, on tapping ✏️ Fix, a
  **suggestion-button layer** for each `?` line — e.g. line 1: `[potato $1.20] [onion $1.10] [⌨ type it]`.
  One tap = `rename_receipt_line` + `learn_item_alias` (same effect as typing "1 potato", but one tap).
  Typing stays the fallback.
- A ranked guess is a **suggestion shown to a human** — it NEVER auto-applies and NEVER overrides a
  confident (alias-backed) read.

### G3. New vs reused (scope honesty)
- **NEW (small, read-side):** `vendor_priors_for(vendor_id)` (read-only: aliases + item/price history over
  existing tables; may reuse `recent_receipts_for_vendor`) · the priors prompt-builder · the pure ranking
  function · Fix-flow suggestion buttons + their callback.
- **REUSED:** `acc_item_aliases` + `learn_item_alias`/`get_item_alias` (learn path unchanged → the
  "human-only learning" guardrail is free) · `acc_receipt_lines` (prices already persisted → price history
  is a QUERY, not a new table) · the `?` confidence signal · the ✏️ Fix entry point.
- **NEW SCHEMA: none. NEW API CALLS: none** (A adds a few tokens to the existing call; B is pure Python).

### G4. Guardrails = build invariants (carry from the step-2 discussion)
1. A ranked guess never overrides a confident read. 2. Learn ONLY from human-confirmed corrections (the `?`
must stay visible enough that staff *look*, not rubber-stamp). 3. Priors are soft hints, not anchors (the
prompt says "read what's written"). 4. Prices are a signal; the receipt's printed number is truth.

### G5. Build order (each step testable; DESIGN until owner says build)
1. `vendor_priors_for()` read-only query + staging tests. 2. `extract_receipt(vendor_priors=…)` param +
prompt-builder (pure prompt-shape test) + wire the pre-known-vendor callers to pass it. 3. pure ranking
function + tests. 4. Fix-flow suggestion buttons + callback (rename + learn) + tests. 5. staging walk: the
same hard receipt across 1–3 corrections → names firm up; verify a confident read is never overridden.

### G6. Deferred (NOT MVP — add only if it bites)
Per-line model self-confidence flag · two-pass re-read for cold hard receipts (decision ii) · inline card
suggestions (kept in Fix per owner) · cross-vendor / global item priors.

### G7. Vendor identity — the key everything hangs off (new-supplier handling; owner-locked A, 2026-06-21)
Priors / aliases / price-history ALL key on `vendor_id`, so a wrong or duplicate vendor fragments ALL of
it (worse than a wrong item name — vendor is the parent key). **Principle: a typed name SEARCHES or
PROPOSES, it NEVER becomes the key.** A vendor is ONE `acc_vendors` row referenced by id; spellings are
`name` + `aliases` ON that row; corrections edit the one row so every receipt/alias/price re-points
automatically. (This is the S5 "one home / one resolver" law applied to vendors — same family as the
truth-consolidation work.)
- **Auto-resolve (conservative, no guessing):** `vendor_by_name` matches by case-insensitive SUBSTRING on
  the vendor name OR any saved alias — deterministic, NO fuzzy (it silently attributes a receipt's money;
  a loose match would mis-attribute). Typo/transposition matching is HUMAN-confirmed, not here.
- **New-supplier capture flow:** (1) PICK from existing (tap / type-to-search over name+aliases) — the
  front-line anti-dup; (2) "+ New supplier" → **dedup gate** `find_similar_vendors` (looser fuzzy, because
  a human confirms) → "Did you mean Atlas? [Use Atlas] [No, it's new]" → only "new" creates a row.
- **DECISION A (owner, 2026-06-21):** on "it's new", staff create it IMMEDIATELY (capture not blocked); it
  lands UNCONFIRMED for a one-tap owner name-confirm. **Dependency:** the ❗ Pending queue
  (`acc_pending_decisions`, §E8/E11) is NOT built yet → lean interim = a `needs_review`/`unconfirmed` flag
  on `acc_vendors` + an owner confirm list; fold into the full Pending queue when it lands.
- **Repair — "can another staff fix?" YES, safe by construction (shared record):**
  - rename / add-alias = ANY allowed staff: edits the ONE row, so everything keyed on `vendor_id` follows;
    the wrong spelling becomes an ALIAS → self-healing next time. Same ergonomics as the item ✏️ Fix.
  - MERGE two vendor RECORDS = OWNER only: moves financial history (audit + undo; repoint `vendor_id`
    dup→canonical, deactivate dup). The risky op, so it's gated.
- **Group-signal removes most of this:** a supplier WITH a Telegram group has vendor = the group
  (`tg_group_id` UNIQUE, named once by owner at `/vendor link`) → zero staff typing. Typed names only matter
  for groupless (cash / market / one-off) suppliers — a small set.
- **Permission tiers:** staff = pick · propose-new (behind dedup) · rename · add-alias. Owner = `/vendor
  link` group map · confirm a new canonical name · merge duplicates.
- **Build slices:** **V1** alias-aware (+ deterministic) `vendor_by_name` ✅ **BUILT 2026-06-21** ·
  **V2** `find_similar_vendors` dedup helper ✅ **BUILT** · `add_vendor_alias` (self-healing) ✅ **BUILT**
  (6 tests, accountant suite 49/49) · **V3** pick/propose-new capture UX + create-immediately →
  **LEAN INTERIM `needs_review` flag on `acc_vendors`** (owner-chosen 2026-06-21; fold into the full
  Pending queue when it lands) · **V4** rename/add-alias (staff) + merge (owner). V1+V2 were the
  unblocked read-side foundation; V3 is next.

### G8. Prices are a PRIMARY goal — keep the door open (owner emphasis, 2026-06-21)
Prices aren't just a did-you-mean signal; they're a headline feature in their own right (ties to §E5/E6,
§F3, §H): (a) **per-supplier price TREND** ("Atlas onion $1.20→$1.50, +25%") and (b) **cross-supplier
COMPARISON** ("who's cheapest for onions") to drive ordering. Design constraints so the build never closes
this door:
- keep **per-line prices** in `acc_receipt_lines` (already there: `unit_price_cents` / `line_total_cents`)
  with vendor (via the receipt) and date — raw and queryable, never a lossy per-vendor cache;
- keep the path to a **canonical `item_id`** open (the `acc_item_aliases` → `acc_items` seam, §E7) so the
  SAME real item is comparable ACROSS suppliers — cross-supplier comparison is impossible without it;
- both trend and comparison are then QUERIES over that, not new stored/duplicated numbers (money stays
  point-in-time truth on the receipt line — the money-pin).
Step 2's vendor price-priors are a READ of this same data → building them must lean on / populate the
per-line + canonical-item structure, **not** a vendor-only shortcut.

### G9. Channel attach (listener-powered) + once-off / contact-only suppliers (owner-locked, 2026-06-21)
Owner ask: link a supplier's EXISTING group without scrolling 100s; handle groupless / once-off / a
supplier reachable only as a listener DM contact — **without the work ever halting for an approval.** Key
asset: the LISTENER already sees every chat (groups + DMs) and stores `chat_id`+`chat_title` in `ops_messages`.
- **One concept — "attach a channel" = search the listener's known chats by name → tap.** `_rank_channels`
  fuzzy-matches the vendor name against `ops_messages` titles; the owner taps the right group/DM. No
  `/vendor link` inside the group, no scrolling. Read-only over the listener's data; defensive if
  `ops_messages` is absent/empty.
- **Channel = group OR DM.** A DM is just a `chat_id` too → reuse `tg_group_id` for any listener-visible
  chat; `channel_kind` inferred ('dm' if id > 0 else 'group'). DM attach is owner-only + deliberate (privacy).
- **Groupless is first-class; once-off = a `kind` flag** (`supplier` | `oneoff` | `internal`). The picker
  ALWAYS offers skip (groupless) + 🗑 once-off, so it's never a dead end. `oneoff`/`internal` stay off the
  payable run.
- **NON-BLOCKING throughout (owner ask, 2026-06-21):** staff create a vendor usable IMMEDIATELY; the owner's
  confirm + channel-link are optional taps (vok → suggestions → tap or skip; `/vendors` shows Confirm + 🔗
  Link). The work never halts waiting on the owner to approve a name or a channel.
- **Honest split:** the listener DETECTS that a slip/photo exists + its text in the channel; the bot OCRs the
  IMAGE only where it is itself a member (a finite set the owner adds the bot to). Once-off / contact-only
  lean on detection + the reply/relay path.
- **BUILT 2026-06-21 (V3.5):** `set_vendor_kind` · `attach_vendor_channel` (group/DM) · `_rank_channels`
  (pure) + `listener_channels_matching` (defensive `ops_messages` read) · `channel_picker_buttons` · vok now
  offers channel suggestions · `lch`/`lskip`/`1off`/`lsug` callbacks · `/vendors` = Confirm + Link. Tests:
  pure picker + ranking + kind/channel lifecycle.

---

## H. PARKED NEXT-WAVE (owner brainstorm 2026-06-21 — DESIGN ONLY, not built)
Captured so they survive context; build later, after the P1/vendor + §G read work.

### H1. "Why is this higher now?" — price-increase prompt (own + supplier receipts)
When a recognised item's unit price is HIGHER than its recent history for that source → ask the buyer
**"why is <item> more expensive now?"** (one tap: supplier raised it · smaller pack · one-off · mistake).
**NEVER prompt on a price DROP** (lower is good — owner). Depends on the canonical-item price history (§G8)
so the SAME item is comparable over time; a tolerance band stops normal wobble from nagging. The logged
reason feeds the supplier price-trend + cheapest-supplier comparison. Pure-logic detection, ~no extra API.

### H2. Own handwritten / local-market receipts (no printed receipt) — record + new-item watch
Some own-written buys are ad-hoc local-market purchases (extremely rare, no supplier receipt). Goal: RECORD
what they are (item + price + date, on a "Misc / market" `oneoff` vendor, §G9) and FLAG when staff start
buying a **NEW item** ("first time we've logged <X>") for the owner to notice. Reuses the existing capture
(a handwritten own-receipt photo → lines) + the pending-queue "recurring or once-off?" fork (§E8); the
new-item flag = an item not yet in the catalog/alias history. Voice-note capture (§C3-D) suits the
receiptless market buys.
