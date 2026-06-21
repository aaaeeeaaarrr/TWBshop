# Bedrock Audit — whole system (old live + new design), 2026-06-22

> Owner asked for a rigorous "bedrock the whole thing" pass → bonuses + new findings. Done read-only via
> 2 parallel code-audit agents + a live-prod data reconciliation. Every load-bearing finding re-read in
> source. **Verdict: the LIVE GM attendance/payroll core is sound + the live data is clean; the real
> exposure is concentrated in DORMANT/DISABLED paths (landmines, not current fires).**

## Verdict in one line
Nothing currently live-and-reachable is broken. The findings are **landmines in paths that aren't active
right now** (B2B disabled, OT-bank empty, accountant inert) — fix them before those paths go live.

## Live data (read-only prod reconciliation)
**0 integrity issues** across 15 money/balance tables (payroll + b2b + hiring + reports + customer credit):
no negatives, no orphans, no over-credited debts, no >1-open-debt, no checkout<checkin, no impossible
states. `ot_bank` = **0 rows** (nobody has ever banked OT → the OT-buyback path below is currently
unreachable; also a "is this feature earning its complexity?" flag).

## NEW FINDINGS — ranked by real-world risk

### 🟡 F1 — OT-rest BUYBACK is the un-fixed TWIN of the payback over-book ("never again" class)
`gm_bot/bot.py:2581-2608` → `ot_buyback_book` (database.py:3186, raw INSERT) + `ot_bank_spend` + autoapprove.
The picker sizes two windows to the full bank, captured in the button at build time; booking does a raw
INSERT with **no re-read of the bank in the same txn** and **no atomic claim** — the exact shape we
hardened in `payback_book` (the `book_room` guard), left undone on the OT twin. No UNIQUE on
`(staff_id, slot_date)` → a double-tap / two-device stale menu = TWO buyback rows + TWO auto-approved
redefines for one bank's worth. LIVE gm code, but **currently DORMANT (ot_bank empty)**. **Fix:** mirror
`payback_book` — re-read balance in the insert txn + refuse over-spend; atomic claim before spend+redefine.
*This is the owner's explicit "never again" class — recommend fixing now (cheap, closes the class).*

### 🔴-when-live F2/F3/F4 — B2B money path: 3 HIGH bugs, no atomic claim (B2B is DISABLED → LANDMINE)
B2B (`twbshop-b2b`) is installed but stopped. **Must fix before re-enabling.**
- **F2 `apply_payment` non-atomic + no idempotency key** (`b2b_bot/billing.py:91-127`): mark-orders-paid
  and credit-write are SEPARATE commits (crash between = money lost/duplicated); re-reads live unpaid each
  call → called twice double-applies. Fix: one txn; key to a payment-row id.
- **F3 payment dedup is check-then-write, NO unique constraint** (`billing.py:284/431→510`; `b2b_payments`
  has only `id PK`): the hourly nudge job runs concurrently with the ✅ handler → redelivery/near-simul
  re-send double-credits. Fix: partial UNIQUE on `(group_chat_id, tg_file_unique_id)` + `(…, message_id)`.
- **F4 `_do_confirm` flips guard status AFTER moving money** (`staff_commands.py:310-323`): double-tap
  re-applies. Fix: atomic `UPDATE … SET status='approved' WHERE status IN('draft','pending') RETURNING`
  FIRST; only `apply_payment` if a row was claimed.

### 🟢 F5/F6/F7 — Accountant (INERT/staging): money-class logic to harden in the build
- **F5 `merge_vendors`/`undo_vendor_merge`** atomic but not re-merge-guarded → re-merge then undo can
  strand financial rows on a deactivated vendor (db.py:414-490).
- **F6 `propose_vendor`** check-then-insert, no unique name → two trusted actors add "Atlas" simultaneously
  = duplicate vendor (db.py:327). (Contrast the correct `photo_sha` UNIQUE backstop on receipts.)
- **F7 P2 matcher is a stub** (`record_payment_and_match` → NotImplementedError) → apply the atomic
  claim-first pattern when built (don't repeat F2/F3).

### 🔵 LOW — display / date cosmetics
- `payback_open_bookings` (database.py:4321) filters on naive `date.today()` + slot START → an in-progress
  OVERNIGHT payback slot drops off the staffer's "Booked" header. **Display only** (the guard + settle use
  the live ledger). Same naive-date sibling as what we fixed.
- Food corrected-report: re-post leaves gives welded to the dead report id + an empty list (no money
  lost/doubled — the give itself is atomic). 
- B2B daily reminder uses raw UTC `date.today()` (correct only 17:00–24:00 UTC) — wrong-day message risk,
  not a balance error.

## ALREADY FIXED this pass
- 🔒 Bot-token leak to the systemd journal on **retail (LIVE) + B2B** (+ tightened hire/accountant/listener)
  — `install_log_hygiene()` on all 5 bots (committed `52702d5`; pending restart of retail + listener).
- (earlier today) audit overnight false-alarm + the OT-vs-payback label.

## CONFIRMED SOLID (good-news findings, re-read in source)
- **`al_approve_and_deduct`** — one txn + `pg_advisory_xact_lock` + F14 claim + frozen maps + atomic
  OT-rest refund. Exemplary. **`payback_book`** (the reference fix), **`special_leave_refund`**,
  **`al_cancel_and_refund`**, **`shift_change_claim_settle`** (atomic CAS) — all clean.
- **Stock** — append-only movement ledger, `on_hand`=live SUM → structurally immune to all four bug classes.
- **No webhooks anywhere** (polling mandate holds). **AI rule holds** (only ai_client.py imports the SDK;
  all max_tokens set; hire 2(+1)-call limit enforced in code). **Overnight discipline** holds on the live
  action paths (only the display sibling above slips through).

## Cross-cutting ROOT CAUSE (the bonus insight)
Every money bug — old and latent — shares ONE disease: **caps + single-application enforced in the CALLER,
never atomically at the DB write.** And ONE proven cure already lives in this codebase: **flip a status
FIRST via conditional `UPDATE … WHERE status=… RETURNING`, or make the INSERT itself the claim via a UNIQUE
constraint** (exactly `al_approve_and_deduct`, `payback_book`, `shift_change_claim_settle`).

## BONUS — this validates the platform direction
The new **entity + event** model + the **per-event verifier** ("balance row == sum(its events)") + a house
rule of **atomic-claim-at-the-write everywhere** would **kill this entire class by construction** — no
future module could reintroduce it. So the bedrock pass isn't just a bug list; it's evidence that the
platform architecture we chose cures the recurring disease, and a ready-made **"atomic-claim-first" coding
standard** to carry into every module.
