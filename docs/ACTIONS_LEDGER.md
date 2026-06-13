# Operational Actions Ledger

> Every owner instruction that changes **real data** (payback · AL · balances · staff records ·
> payments) or is a concrete operational task gets ONE line here the moment it's given — Open or
> Done-with-proof. Chat is disposable; this file is truth. Claude reads this at session start (with
> Current Status) and, at the end of any turn where an instruction was given, states the open loops
> ("Open items: none" or the list). **Default: do real-data writes immediately, with independent
> before/after proof — never defer them.**

## Open (not yet done)

- **🛑 2026-06-13 (CRITICAL BALANCE BUG — found by Fable's pre-guard review, NOT yet fixed, awaiting
  owner decision): AL deduction is split-brained; HOURS-AL is never deducted at all.** `_al_finalize`
  flips the request to `status='approved'` (bot.py:2550) BEFORE computing `nw = staff_absent_dates()`
  (bot.py:2558), and `staff_absent_dates` returns ALL approved AL days for the staffer (database.py:3704)
  — so the request's own days are excluded as "already absent" → `al_day_count = 0` → `al_deduct(…, 0)`
  deducts NOTHING at approval. **Days-AL** is then charged only by the daily job `al_apply_due_deductions`
  as dates pass. **Hours-AL** (fractional, e.g. "9pm–12am = 0.3 AL") is charged by NEITHER (the job
  filters `kind='days'`, database.py:2818) → **fractional leave is currently FREE**. Side effects: the
  approval message shows the uncharged balance, and the request-time over-balance gate reads the unmoved
  `al_left` → staff can stack approved future AL beyond their balance. **DECISION NEEDED (owner):** which
  is the ONE canonical deduction path — (i) finalize deducts immediately (compute amount before the
  status flip; retire the daily job; update /audit), or (ii) the daily job deducts (extend it to hours-AL
  pro-rata; fix the message + gate to account for approved-but-undeducted). HIGH-RISK / auto-bedrock:
  fix with real-path before/after proof on a real row; ideally after the staging-DB lock. Blocks the F14
  guard (Stage 5b) — the guard's "each approved AL-day deducts once" invariant + override-refund are
  unspecifiable until exactly one thing charges.
  **→ OWNER DECISION (2026-06-13): Option (i) — DEDUCT-AT-APPROVAL + REFUND-ON-CANCEL.** Finalize
  computes the amount BEFORE the status flip and deducts (days AND hours); Cancel-AL refunds the same
  amount; retire/neuter the daily `al_apply_due_deductions` job; update `/audit` (`v_al`) to the
  deduct-at-approval model + cover hours-AL. Rationale (owner): "just 2 things, eliminates overbooking."
  Still HIGH-RISK/auto-bedrock: implement with real before/after proof on a real row, ideally after the
  staging-DB lock. Then build the F14 guard on top.
  **→ DESIGN REDONE (2026-06-13) after Fable red-team:** my first design (reorder + mark deducted_days
  + daily-job backstop) shipped 2 Criticals on paper (daily-job double-charge of excluded days;
  cancel double-refund/mint via stale buttons) + a crash window. **REPLACED** with a per-day
  `{date: amount}` map on the row + two atomic functions (`al_approve_and_deduct` /
  `al_cancel_and_refund`, each one CAS transaction) — fewer parts, mechanically auditable. Full build
  brief + the 5 must-hold invariants + my added checks → **`docs/AL_DEDUCTION_REDESIGN.md`**. Build on
  staging, then the F14 guard on the corrected base.

- **⏰ Jul 1 (AUTOMATED · MUTED · SELF-DESTRUCT — owner: no redundancy): Kimying full-split
  restore.** `_pay_restore_job` (daily 07:05 PP) restores 145/30 from her seeded `pay_restore:42`
  record once June passes, and DMs the owner. Do NOT mention in open-loops reports; act ONLY if no
  DM arrived by Jul 2. **Once fired & good: DELETE this entry entirely** — her state record is
  auto-cleared by the job itself, the job is GENERIC (serves every future hire — stays), and her
  proration history lives in Done below. Nothing Kimying-specific remains in code after that.

## Parked for owner (autonomous run Jun 13 — answer later, NOT blocking)

> Owner greenlit an autonomous "next next next" run: do the next best step with no pauses, park any
> owner-judgment decision here instead of stopping. These are NOT done and NOT urgent — answer when free.

- **Red-team DONE (Jun 13) — but NOT literal Fable.** The `claude-fable-5` model isn't accessible in
  this environment, so an INDEPENDENT cold-context review (available model) was run instead. Hot path
  (CAS, advisory-lock races, frozen-map refund, float symmetry, is_test isolation) verified clean.
  Findings fixed (commit `2763427`): forward short-notice points moved INTO the approve txn (was a
  crash window); legacy no-map rows excluded from the cancel list (were a silent no-op); 0-cost-day FYI
  suppressed; **+ a pre-existing bug surfaced & fixed** — `al_cancel_list`/`al_cancel_confirm` had a
  `_db` NameError (swallowed) so the Cancel-AL list ALWAYS came back empty. Parked low: over-strict
  same-day hours-AL conflict (#4), non-atomic special-leave grant (#5), PH backfill not needed (#6).
  **Owner may still want to run the LITERAL Fable** for its broader aperture — say the word.
- **Marriage/death/birth special-leave timing.** Adding a frozen `deducted_amount` + refund path; these
  already deduct via `al_deduct` at grant. If I also route them through deduct-at-approval semantics it's
  a charge-timing change. Default I'm taking: keep their existing grant-time deduction, just ADD a frozen
  amount + clean refund (no timing change). Flag if you wanted otherwise.
- **Over-balance at approval.** Deduct-at-approval already stops sequential over-booking (each approval
  drops the gate). Building a senior "this takes them negative — approve anyway?" warning for the rare
  simultaneous-approval race (Fable M1). Default: build it as a non-blocking notice, never a hard stop.
- **Phase C cutover timing** (pin 5 server units to `TWBSHOP_ENV=prod`, then flip dev default to
  staging). Deliberate, needs a quiet-window deploy. Say when.
- **hire_bot/* + run_*.py** still bind `secrets.DATABASE_URL` directly (don't honor the switch). Fold in
  before hire/import work moves to staging. Not on the AL path.
- **F14 — DONE in every direction (data-integrity guarantee complete + race-proven).** AL-vs-AL ·
  AL-vs-shift-change (both ways) · AL-vs-swap (both ways) · request-side submit block. All serialized by
  a shared `pg_advisory_xact_lock(911, staff_id)` so no two flows can both claim a staff-date, proven
  with real concurrent same-flow AND cross-flow races (AL×AL, AL×shift-change, AL×swap — deterministic
  over repeated runs). `swap_approve_claim` locks BOTH parties' ids (sorted, deadlock-safe), rejects a
  swap that would put either party to WORK a day they have approved AL, and flips+writes the 4 overrides
  in one txn. **ONLY remaining F14 piece = senior OVERRIDE** to force-approve despite a conflict — an
  owner POLICY decision (who may override, does it need a 2nd senior, does it re-check balance). Nothing
  else in F14 is open.
- **AL go-live prep (owner-driven):** owner re-walk of the new deduct-at-approval + Cancel-AL flows in
  /test → `/testreset` → backfill `special_leaves.deducted_amount` on prod → flip `attendance_live`.

- **▶ UNIFIED SCHEDULE-EVENT MODEL (owner-driven design, Jun 13) → `docs/SCHEDULE_RESOLUTION_MODEL.md`.**
  Owner's direction: replace block/override with "newest decision wins, old one stands down, its balance
  is reversed, and ALL involved are told (supervisors + staff + senior + swap-partner: 'X replaced Y'),
  humans re-cover." Design doc written (precedence, per-event inverse, notify-all, two-party=human
  boundary, every edge, new-bug discipline, law/audit evolution). Subsumes the S5 follow-ups below + the
  override question (override NOT needed — a confirmed-revoke + reverse replaces it). Build phased on
  staging, each proven, F14 stays backstop. NEXT BUILD STEP when resumed: the single `resolve_day()`
  resolver (kills the implicit redefine-overrides-AL precedence + folds sick in).
- **S5 multi-feature follow-ups (cross-function audit, Jun 13 — low/rare, all behind go-live).** The
  shared "staff-date schedule" is written by 5 features (AL · senior redefine · payback slot · OT-rest ·
  swap). The AL-centric interactions are guarded (F14 both ways + payback picker skips AL/redefined
  dates) and `al_left` writes are all relative now; `/audit v_one_active_redefine` catches multi-writer
  clobbers. REMAINING gaps (each a focused pass):
  (a) **Asymmetric picker:** senior redefine picker (`sc_day_pick`) does NOT skip payback/OT-rest-slotted
      dates (payback picker skips redefined dates). Fix = symmetric `_sc_taken_dates` in the senior picker.
  (b) **No undo:** no senior "cancel an approved redefine" path → a redefined day can't be cleanly freed
      for AL (you can only supersede, which still occupies the day). This is the real fix for the
      AL-on-a-redefine-day case (better than an override). Add a cancel-approved-redefine action.
  (c) **swap ↔ redefine resolution UNVERIFIED:** a swap writes `dayoff_overrides`, a redefine writes
      `shift_changes`; if a day has BOTH, which wins in `compute_day_events`/`works_on`? Not yet traced —
      verify the resolver consults both consistently (one source of truth).
  (d) **OT-rest picker** symmetry (same as (a)) not verified.

## Done (with proof)

- **2026-06-13 — staging DB stood up (Phase A+B).** `twbshop_staging` CREATED on the existing DO
  cluster (idempotent — `setup_staging.py`); schema cloned via every `init_*_db()`. Independent
  re-read proof (`verify_staging.py`, separate connection to twbshop_staging): all key AL-build tables
  present and **EMPTY — zero prod data leaked** (only the 7 seeded `points_rules` rows, which are rule
  definitions). prod↔staging column diff surfaced + closed 1 real drift (staff_registry
  `first_pay_usd`/`second_pay_usd` were ad-hoc on prod → added to the canonical init). `TWBSHOP_ENV`
  switch in `shared/database.py` defaults to prod (zero behavior change; verified prod/staging/no-secret
  resolution with no connection opened). Latent init bug fixed (init_attendance_db ALTERed al_requests
  before CREATEing it — no-op on prod, unblocks fresh-DB bootstrap). hire_bot/secretary tables
  deliberately omitted (separate subsystems, own connections). OWNER STEP PENDING: add the
  `STAGING_DATABASE_URL` line to secrets.py (guard blocks Claude from secrets.py). Phase C (pin server
  units to prod, then flip dev default) is later + deliberate.
- **2026-06-11 — dead `secretary.service` removed from the server.** The Personal project's bot
  unit (pointed at /root/Personal) was already stopped+disabled by the owner; the unit file was the
  last remnant — deleted + daemon-reload, verified gone ("could not be found"). No cron entries, no
  twbshop-code references existed. `/root/Personal` itself NOT touched (separate project decision).
- **2026-06-11 — Davy (id 26): payback cleared ("she paid").** Real debt #5 (60 min) + test mirror
  #45 credited → cleared. No attached bookings (checked first). Independent re-read: both open
  debts now None. (Rath explicitly NOT touched — owner's hypothetical only.)
- **2026-06-11 — Tyty (id 28): pay record corrected + included in /menu pay views.** salary 1500→
  1700 (stale), 1st stays 1700, 2nd 0, bonus 0 (owner: "only on the 1st, $1700, no bonus"). Views
  now include her (1st list only; zero-2nd staff skip the 2nd list). Verified fresh-process re-read.
- **2026-06-11 — Sun Kimying (id 42): June prorated + joined date.** Joined 2026-06-04 → 27/30
  payroll days → 144 prorated; 1st = 80%×144 = 115.20 → next 5/0 up = **120**; 2nd = 24 base +
  15 bonus (kept, not prorated) = **39** stored. joined_date set 2026-06-04. Verified fresh-process
  re-read. Full split restores ~Jul 1 (see Open).

- **2026-06-11 — cron daemon enabled on the server (the watchdog was never running).** The
  session-28 collection watchdog (`run_collection_watchdog.py`, crontab every 1 min) had NEVER
  executed: the cron daemon itself was `inactive`. `systemctl enable --now cron` → `active` +
  `enabled`; proof: the next minute's cron tick wrote `logs/watchdog.log` ("ok") on its own.
  ⏳ Owner-step pending: fire the alert path once (stop a bot briefly) to see the 🚨 DM arrive.

- **2026-06-11 — Chantrea (id 15): cleared ALL open payback.** Real debt id 2 (27 min) + test debt
  id 43 (27 min) → both `None`/cleared. Her AL untouched (2.0). Method: `payback_credit` of the full
  remaining balance. Verified by an independent fresh-process re-read.
- **2026-06-11 — Davy (id 26): −1.0 AL.** 15.0 → 14.0 (`al_deduct(26, 1.0)`, real). His 60-min
  payback (debt id 5) left untouched — not instructed. Verified by an independent fresh-process re-read.
  - *Note: both were instructed earlier in session 32 and dropped at the time; surfaced + executed when
    the owner re-checked. This ledger exists so that never recurs.*
