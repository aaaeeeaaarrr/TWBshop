# AL deduction redesign — build brief (Option i, reshaped after Fable red-team)

> **HIGH-RISK / auto-bedrock — moves real leave balances.** Build on the **staging DB** (2026-06-30
> checkpoint) with real before/after proof on a real-shaped row, and a second-opinion pass. Dormant
> until go-live (`attendance_live=OFF`), so there is NO urgency — correctness over speed.
> Governed by `docs/STATE_INTEGRITY_LAWS.md` (S1–S4). Decision + history in `docs/ACTIONS_LEDGER.md`.

## The bug (why)
`_al_finalize` flips status to `approved` BEFORE computing `nw = staff_absent_dates()`, which then
includes the request's own days → `al_day_count` self-excludes them → `al_deduct(0)`. Days-AL is then
charged only by the daily job; **hours-AL is charged by nothing (free)**; the shown balance + the
over-booking gate read the un-moved number.

## The shape (Fable's reshape — fewer moving parts than reorder-and-mark)
Store the deduction as a **frozen per-day map on the row**, and move it via **two atomic functions**.
A single record is the source of truth for deduct, refund, audit, and points reversal.

### Schema (migration)
- `al_requests.deducted_map JSONB` — `{ "YYYY-MM-DD": amount }` for **every selected day** (zeros for
  excluded day-offs / holidays / overlaps / PH-comp; the frozen frac per charged day for hours-kind).
  Empty/NULL = legacy row (pre-migration) OR not-yet-approved.
- `al_requests.points_map JSONB` — `{ "YYYY-MM-DD": qty }` frozen short-notice penalty per day.
- (special leave) `special_leaves.deducted_amount` — the frozen amount, for refundability + audit.
- (PH-comp) a **structural flag** (`al_requests.no_deduct BOOLEAN` or `kind='ph_comp'`) set by the
  granter — NOT the typed-reason prefix. Migrate existing `reason LIKE 'PH%'` rows once on staging.

### Two atomic functions (each ONE transaction, compare-and-swap)
1. `al_approve_and_deduct(req_id, total, deducted_map, points_map)`:
   `UPDATE al_requests SET status='approved', deducted_map=%s, points_map=%s, decided_at=NOW()
    WHERE id=%s AND status='pending' RETURNING id` — and, only if it returned, **in the same txn**
   `UPDATE staff_registry SET al_left = al_left - %s WHERE id=%s` (RELATIVE, not Python-computed) +
   append the points events. Finalize proceeds only if the claim won. The `❌` reject path uses the
   same `WHERE status='pending'` claim (no balance move).
2. `al_cancel_and_refund(req_id, staff_id, iso)`:
   pop `iso` from `deducted_map` `WHERE id=%s AND staff_id=%s AND status='approved' RETURNING old_amount`
   — and only if a row/amount came back, **in the same txn** `al_left = al_left + old_amount` + append a
   negative-quantity points event from `points_map[iso]`. Popped-nothing ⇒ refund-nothing (double-tap
   and never-charged-day both die by construction).

`total`/`deducted_map` are computed in finalize purely from the request + an **explicit**
`staff_absent_dates(staff_id, exclude_req_id=req_id)` (so reordering can never re-introduce
self-exclusion), with `is_test` filtered (H1).

### The daily job + audit
- `al_apply_due_deductions` (the legacy "deduct as dates pass" job) **only touches rows with no map**
  (`WHERE deducted_map IS NULL`) — partition, don't reconcile. It keeps charging legacy rows until they
  age out; new rows are immune.
- `v_al` becomes mechanical: approved ⇒ `keys(deducted_map) == days`; `Σ deducted_map == recorded
  total`; rejected/cancelled-whole ⇒ map empty / fully refunded; a passed approved non-`no_deduct` day
  must be a map key. No recompute → no false positives.

## Additional checks BEYOND Fable's findings (my widened-aperture pass)
- **Concurrency with the monthly accrual job:** `al_accrual_job` ALSO writes `al_left`. Make EVERY
  `al_left` write relative (`= al_left ± n`), never a Python-computed absolute from a stale read
  (Fable's m1 was the daily job — this extends it to accrual + cancel + the special-leave grants).
- **Cancel-after-the-day-passed:** the handler already blocks past/started days
  (`attendance_ui.py:2735` cutoff) — keep that gate AND have `al_cancel_and_refund` itself refuse a
  date `< today` (defense in depth; a stale button shouldn't refund a day already taken).
- **Special leave (death/marriage/birth, `bot.py:~1703/1745/1760`):** give them a frozen
  `deducted_amount` + a `v_special` audit law + a refund path; **state the marriage-timing change**
  (marriage flows the normal AL engine, so it moves from charge-as-dates-pass to charge-at-approval —
  confirm that's intended).
- **`/testreset` must wipe the new columns** on is_test rows (or test-mode `/audit` flags every
  role-played approval).
- **Migration/backfill on staging:** existing approved real rows have no map → stay legacy (job
  handles). Optionally backfill them to the map model once, with before/after proof, on staging.
- **Over-booking gate re-check at approval (Fable M1):** N pending requests all pass the submit-time
  gate against the same balance; re-check `amount > current al_left` INSIDE the atomic approve and
  surface to the approving senior ("this takes them negative — approve anyway?"), special-leave exempt.
- **Float symmetry:** refund the STORED amount, never recompute — keeps deduct/refund exactly
  symmetric (no 0.01 residue).
- **Edit-an-approved-AL:** confirm there is no senior "edit approved AL" flow; if there is, it must
  adjust map + balance atomically (else cancel+re-request is the only supported change).

## Build order (on staging, prove each)
1. Migration (columns + structural PH flag) + backfill PH flag from `reason LIKE 'PH%'`.
2. `al_approve_and_deduct` + `al_cancel_and_refund` (atomic) + the relative `al_left` writes everywhere.
3. Rewire `_al_finalize` (compute map, call the atomic approve) + the cancel handler (call the atomic
   refund, drop the flat `-1`, verify ownership).
4. Points map + negative-event reversal (+ test that aggregation sums negatives).
5. `is_test` filters into `staff_absent_dates` + `al_leave_days_set`.
6. Partition the daily job + rewrite `v_al` to the mechanical laws + add `v_special`.
7. Then F14 guard (Stage 5b) on this corrected base.

## The 5 invariants this MUST hold (Fable's "must get right")
1. Status-claim + balance-move + record in ONE transaction (CAS), both approve and cancel.
2. Amounts FROZEN at approval per-day; refund/audit/points read the record, never recompute.
3. The daily job NEVER touches a row that has a map (partition, not reconcile).
4. `is_test` filter into `staff_absent_dates` + `al_leave_days_set` in the SAME change.
5. Cancel guards ownership + status + not-past inside the transaction; PH-comp is structural.
