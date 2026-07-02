# B2B money-path fix plan (F2/F3/F4) — READY TO EXECUTE WITH THE OWNER (not done autonomously)

**Why not done autonomously:** these touch REAL payment money + the real `b2b_payments` ledger (B2B ran
before), and B2B re-enable is the owner's deliberate call. HIGH-RISK money on real data = no rushing while
the owner is away. This plan makes the fix fast + safe to execute together at re-enable. Source: the
bedrock audit (`docs/BEDROCK_AUDIT_2026-06-22.md`). **B2B stays DISABLED until all of this is done +
proven.**

## Order of operations (do in this sequence)
### A. Dedup existing data FIRST (before any constraint)
A unique constraint creation FAILS if duplicates already exist. So first, read-only on prod:
```sql
SELECT group_chat_id, tg_file_unique_id, count(*) FROM b2b_payments
WHERE tg_file_unique_id IS NOT NULL GROUP BY 1,2 HAVING count(*)>1;   -- find dup payment rows
```
If any, reconcile them by hand (owner decides which is the real one; the others were double-credits that
must also be corrected on the customer's balance). Independent before/after proof per correction.

### B. F3 — structural dedup (after data is clean)
`b2b_payments` currently has only `id PK`. Add partial UNIQUEs so a redelivery / the hourly nudge running
concurrently with the ✅ handler can't double-insert:
```sql
CREATE UNIQUE INDEX uq_b2b_pay_fileuid ON b2b_payments (group_chat_id, tg_file_unique_id)
  WHERE tg_file_unique_id IS NOT NULL;
CREATE UNIQUE INDEX uq_b2b_pay_msg ON b2b_payments (group_chat_id, message_id)
  WHERE message_id IS NOT NULL;
```
Then make the payment-record insert `… ON CONFLICT DO NOTHING` (the check-then-write at `billing.py:~493`
becomes a structural claim).

### C. F4 — atomic claim-first in `_do_confirm` (`staff_commands.py:310`)
Today it CHECKS `status in (draft,pending)` (312) → `apply_payment` (316) → `set_markpaid_status('approved')`
(323): a double-tap passes the check twice → double-credit. Fix = claim FIRST:
```python
async def _do_confirm(bot, req_id):
    req = claim_markpaid_request(req_id)   # NEW: UPDATE b2b_markpaid_requests SET status='approved'
                                           #      WHERE id=%s AND status IN ('draft','pending') RETURNING *
    if not req:
        return                              # a concurrent tap already claimed it → no double-apply
    result = apply_payment(req["group_chat_id"], float(req["amount"]))
    save_b2b_payment(...); ...             # status already flipped by the claim
```

### D. F2 — make `apply_payment` atomic + idempotent (`billing.py:91-127`)
Today `mark_b2b_orders_paid` + `mark_b2b_cake_orders_paid` + `set_b2b_customer_credit` are SEPARATE commits
(crash between = inconsistent) and it re-reads live unpaid each call (called twice = double-applies). Fix:
- One transaction: inline the three writes inside a single `_db()` block (refactor the helpers to accept a
  cursor, or inline their SQL) so they commit all-or-nothing.
- Idempotency: tie the application to the CLAIMED `b2b_markpaid_requests` row id (from F4) — `apply_payment`
  runs exactly once per claimed request. (F4 already guarantees one call per request; F2 adds crash-safety.)

### E. Proof + guards (HIGH-RISK → mandatory)
- Staging before/after on a real row: a single confirm credits once; a DOUBLE-TAP / re-delivery credits
  ONCE (not twice); a crash mid-apply leaves a consistent state.
- Regression tests: a new `test_b2b_billing_atomic` suite — claim-once, no-double-credit, ON-CONFLICT dedup.
- A second-opinion / red-team pass on the money logic before re-enable.
- Then, and only then, the owner re-enables `twbshop-b2b`.

## Prep done (s57, read-only on prod — makes the joint session fast)
- **Step A is a NO-OP:** prod `b2b_payments` = **4 rows, 0 duplicates** (by `tg_file_unique_id`). So the UNIQUE
  indexes (F3) can be added directly at re-enable — no by-hand dedup needed.
- **Column name confirmed:** it's **`group_message_id`** (not `message_id`) — the F3 index B uses `group_message_id`.
- **`b2b_markpaid_requests` shape:** `id · group_chat_id · business_name · amount · method · staff_user_id ·
  staff_msg_id · owner_msg_id · status · covered_dates · created_at` → F4 `claim_markpaid_request` = `UPDATE …
  SET status='approved' WHERE id=%s AND status IN ('draft','pending') RETURNING *`.
- **F2 confirmed:** `apply_payment` (`b2b_bot/billing.py:91`) does 3 SEPARATE writes (`mark_b2b_orders_paid` +
  `mark_b2b_cake_orders_paid` + `set_b2b_customer_credit`) → not atomic; + re-reads live unpaid each call →
  double-applies if called twice. Fix = one txn (cursor-threaded) + idempotency via the claimed request id.

## Status — ✅ STAGING CODE BUILT + TESTED + RED-TEAMED (s57; B2B still disabled; prod apply + re-enable stay JOINT)
- **F4 claim-first** — `shared.database.claim_markpaid_request` (atomic CAS: draft/pending→approved RETURNING) +
  `staff_commands._do_confirm` claims BEFORE applying → a double-tap claims once → `apply_payment` runs once.
- **F3 dedup** — 2 partial UNIQUE indexes on `b2b_payments` (created **defensively** — own txn + try/except — in
  `init_db`, prod verified 0-dups so safe to ride along on the next core-bot init) + `save_b2b_payment` is now
  `ON CONFLICT DO NOTHING RETURNING id` (None on dup) + **both photo call-sites gate `apply_payment` on the
  save-return** (the save is the structural claim → a redelivered photo never double-applies).
- **F2 atomic** — `shared.database.apply_b2b_payment_writes` does the 3 money writes (bread paid · cake paid ·
  credit) in ONE `_db()` txn; `billing.apply_payment` uses it → no half-applied payment.
- **Tests:** `tests/test_b2b_billing_atomic.py` — claim-once · redelivery-dedups · atomic-writes (3 pass).
- **Red-team note (deliberate, per State-Integrity S2):** claim-first means a crash *after* the claim leaves the
  request **approved-but-unapplied** (visible + manually re-runnable) instead of the old **double-credit** — the
  correct trade-off; F2 ensures the apply itself is all-or-nothing (never partial).
- **⛔ Still JOINT with owner:** deploy a tag (the indexes auto-apply on the next core-bot init — safe) → confirm
  on prod → re-enable `twbshop-b2b`. (Code is on `main`, NOT deployed; bots untouched.)

## Status (original)
Plan ready + prep done. Code unchanged (B2B disabled). The staging CODE build (F2/F3/F4 + tests + red-team) is
safe-autonomous (B2B disabled, no live money); the prod INDEX application + the re-enable stay joint with the owner.

## F5 (added 2026-07-02, observability audit dead-end #13) — markpaid owner-approval DM has NO re-nudge
`b2b_bot/staff_commands.py::callback_markpaid_method` DMs the owner the Confirm/Reject card inside a
`try/except logger.error` with no retry and no watcher: a failed DM = staff sees "⏳ awaiting approval"
forever, owner never learns, money never applied. Fix at re-enable WITH the F2/F3/F4 session: copy the
existing hourly verification-nudge tick pattern (`run_verification_nudge_tick`) onto pending
`b2b_markpaid_requests`, and sink-alarm the send failure (observability law T2).

## F6 (added 2026-07-03, s60): `_startup_summary_check` can abort the boot
Found while porting it to retail (S60 A5): b2b's `post_init` catch-up is UNWRAPPED — a transient
Telegram error during the missed-summary send raises out of post_init, which kills `run_polling`
→ systemd restart-loops the service at exactly the moment Telegram is flaky. Retail's port wraps
it (non-fatal, the daily job is the retry cadence); apply the same 3-line try/except to
`b2b_bot/bot.py::_startup_summary_check` at re-enable, with the F2–F5 batch.
