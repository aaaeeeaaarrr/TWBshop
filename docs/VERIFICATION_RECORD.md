# Verification record — attendance balance/schedule work (session 33, 2026-06-13)

> "How do we make sure the WHOLE is precise?" — this is the answer: the proof baseline + a re-review of
> every invariant against the ACTUAL code, the residual risks, and the ongoing mechanisms that keep it
> accurate. Re-run the baseline anytime; update the verdicts when code changes. All behind `attendance_live=OFF`.

## How precision is ASSURED (the 5 layers)
1. **By construction** — error-classes made impossible: ONE resolver for the daily schedule, atomic CAS
   claims, frozen per-day values read back (never recomputed), all `al_left` writes RELATIVE, structural
   flags (not text), supersede-only-own-rows. (Strongest: a property, not a test.)
2. **By continuous self-check** — `/audit` cross-checks every row daily (`v_al`, `v_special`,
   `v_exclusivity`, `v_one_active_redefine`, `v_payback`, `v_shift_changes`, … 20+ laws).
3. **By real-path proof** — before/after on real-shaped STAGING rows + the full suite.
4. **By independent review** — a fresh-eyes red-team (did one; literal Fable when available).
5. **By the human walk** — the owner re-walks every flow in `/test` before go-live.

## Proof baseline (re-runnable)
- `TWBSHOP_ENV=staging python -m pytest tests/ -q` → **564 passed, 2 skipped.**
- `/audit` real-mode on staging → **NONE** (clean).
- Concurrent races (F14 AL×AL, AL×shift cross-flow, AL×swap cross-flow) → **deterministic** over repeated runs.

## Invariant re-review (each checked against the real code, not assumed)
| Law | Verdict | Evidence / where |
|---|---|---|
| **S1** reversible-by-construction | ✅ for built; 2 gaps flagged | AL deduct↔refund, special-leave refund, points reverse-in-txn, OT add/spend, payback add/credit — all clean pairs, tested. GAPS: day-off-swap undo (Phase 6); a confirmed-revoke that refunds AL (Phase 3). |
| **S2** idempotent/apply-once | ✅ | every claim is a CAS: `al_approve_and_deduct`, `al_cancel_and_refund`, `al_reject`, `shift_change_claim_settle`, `shift_change_approve_claim`, `swap_approve_claim` — double-tap/retry proven to apply once. |
| **S3** atomic claim-or-reject | ✅ | F14 advisory-lock + CAS, race-proven (same-flow + cross-flow). |
| **S4** shown == true | ✅ | the AL gate (`_al_requested_amount`/`_al_over_balance`) and the deduction read the SAME `al_left`; every `al_left` write is RELATIVE (incl. the legacy daily job now); test-mode never moves the real column. |
| **S5** multi-feature resource | ✅ mostly; 2 gaps | ONE resolver (`resolve_day`) for the daily schedule, used by compute_day_events + verdict + settle-guard; supersede scoped to own rows (`senior_id`); `/audit v_one_active_redefine`. GAPS: asymmetric picker (senior picker doesn't skip payback dates); no cancel-approved-redefine undo. |
| **is_test** isolation | ✅ (one item CLOSED this review) | every balance/schedule read on the AL+schedule path is scoped (`staff_absent_dates`, `al_leave_days_set`, conflict reads, `resolve_day`/`_day_context`). The flagged `dayoff_override_for` (unscoped) is now **dead** (its only caller `works_on` was removed) → moot. |
| **Single resolver** (no drift) | ✅ for the daily-schedule question | `resolve_day` is the one answer to "what is X doing on day D". `_sc_running` (shift running NOW, overnight-aware) and the payback-clash/`/test`-sim are DIFFERENT questions — left as-is (forcing them through `resolve_day` would weaken them); tracked. |

## The two original "real bugs" — re-confirmed GONE
- A redefine **silently overriding AL** → gone: `resolve_day` puts leave above a redefine; integration test proves an AL+redefine day is excluded from the schedule; settle won't bank OT on it.
- **Sick never touching the schedule** → gone: sick is a first-class AWAY event; excluded from the schedule and from no-show.

## Residual (explicitly tracked — this is the boundary of "precise so far")
- **Unbuilt schedule-model phases 3–6** (supersede engine + reverse-on-supersede · notify-all · retire the
  silent path · swap-side reversal) — the graceful "new cancels old + tell everyone" layer. Designed in
  `docs/SCHEDULE_RESOLUTION_MODEL.md`; F14 is the backstop until then.
- **S5 gaps:** symmetric picker (senior picker skip payback dates); cancel-approved-redefine undo.
- **Different-question readers** (`_sc_running`, clash, `/test` sim) — optional resolve_day unification.
- **Prod backfill** `special_leaves.deducted_amount` at go-live.
- See `docs/ACTIONS_LEDGER.md` → Parked + `docs/SCHEDULE_RESOLUTION_MODEL.md` → Wider Sweep.

## Bottom line
For everything BUILT, the whole is precise **by construction + proven** (S1–S4 fully, S5 with two named
gaps), the two original bugs are gone, and `/audit` will catch a regression daily. The remaining
imprecision is **only** the explicitly-tracked unbuilt phases + flagged gaps — nothing silent. Next
accuracy gains come from finishing phases 3–6 (each with real-path proof) and the owner's `/test` walk.
