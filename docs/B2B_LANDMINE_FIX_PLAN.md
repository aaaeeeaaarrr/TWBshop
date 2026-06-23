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
- Regression tests: `tests/test_b2b_billing_atomic.py` — claim-once, no-double-credit, ON-CONFLICT dedup.
- A second-opinion / red-team pass on the money logic before re-enable.
- Then, and only then, the owner re-enables `twbshop-b2b`.

## Status
Plan ready. Code unchanged (B2B disabled). Execute together at re-enable.
