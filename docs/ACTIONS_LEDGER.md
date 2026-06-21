# Operational Actions Ledger

> Every owner instruction that changes **real data** (payback · AL · balances · staff records ·
> payments) or is a concrete operational task gets ONE line here the moment it's given — Open or
> Done-with-proof. Chat is disposable; this file is truth. Claude reads this at session start (with
> Current Status) and, at the end of any turn where an instruction was given, states the open loops
> ("Open items: none" or the list). **Default: do real-data writes immediately, with independent
> before/after proof — never defer them.**

## Done (with proof)

- **2026-06-21 — HENG (id 37) PB-OVERBOOK data fix DONE (HIGH-RISK payroll write; deployed code + vetted
  script, independent before/after proof).** After deploying the over-book guard (tag `session-51-gm-20260621`),
  ran `scripts/fix_heng_overbook.py --apply` on prod. **BEFORE:** debt #148 owed 96 / paid 89 / open · booking
  #62 (Jun-21 89min) booked · sc #268 approved. **AFTER (independent re-read):** debt #148 **96/96 CLEARED** ·
  booking #62 **cancelled** · sc #268 **cancelled**. Audit overbook flag GONE. The phantom Jun-21 89-min slot is
  void (he already paid his 89 on Jun 19); the worked-but-uncredited 7-min Jun-20 tail is now credited. NEVER-AGAIN:
  authoritative `book_room` guard at the `payback_book` chokepoint (commit `07807f6`). **Group post still HELD** for
  owner go (Heng's balance is now genuinely 0 → the correction post is factually ready).

- **2026-06-21 — LONG (id 1) retroactive −15 DONE (HIGH-RISK payroll write; vetted script + independent proof).**
  Owner decision = just Long + going-forward. Ran `scripts/fix_long_late_sick.py --apply` on prod. **BEFORE:** no
  late_sick_inform events. **AFTER (independent re-read):** event #130 `late_sick_inform` ref 2026-06-19 recorded
  + deferred-notice flag set → the bot teaches Long + offers his 540 payback (debt #154) at his next check-in.
  ROOT-CAUSE FIX (self-cancellation: lateness captured before sick_create) deployed `d09e00c`/tag above; the −15
  now fires for everyone going forward. ⚠ A pre-deploy miss surfaced (THYDA, own-sick Jun 21 13:52 PP, 113 min
  late, before the 16:12 deploy) — left per "just Long" pending owner's call.

- **2026-06-19 — FALLBACK END-OF-SHIFT SESSION-CLOSER built + deployed + the 3 stale sessions CLOSED on prod
  (HIGH-RISK: closes live attendance sessions; before/after independent proof + final clean audit).** Daily
  07:00 PP `_session_closer_job` (`gm_bot/bot.py`) closes any still-open session whose shift has fully ended
  (`att_open_past_sessions`), at the resolved shift end (redefine window if any, else normal hours — overnight
  aware; a check-in means they worked, so it closes even a resolver-day-off shift), settling EXACTLY like
  auto-checkout (no-op for a normal shift; banks pre-authorized OT idempotently; no behavior fork). Belt: only
  `shift_date<today` AND `end_dt<now`. PROOF: suite **769 passed/2 skip** + 10 closer tests; deployed by tag
  `session-closer-20260619b` (`15f2575`); gm active, NRestarts=0, `gm_session_closer` registered in the running
  log. **Ran once on prod, before/after independent re-read:** BEFORE 3 open (Tra/Anan Jun16, Davy Jun17) →
  AFTER 0 open → Tra closed Jun17 06:00, Davy Jun18 06:00 (overnight ends), Anan Jun16 17:00 (normal end) →
  **`run_audit` = 0 problems.** The day-off edge (Anan) was caught BY the first prod run (skipped) → fixed
  (close at scheduled hours when a session exists, not skip) → redeployed → Anan closed. No OT banked (the 3
  were normal shifts). Reversible if ever needed (re-open + null checked_out_at) but no reason to.

- **2026-06-19 — LIVE audit-watchdog built + deployed to gm (go-live hardening; READ-ONLY, no balance path
  touched) + 3 stale sessions investigated read-only.** Owner chose Option 1 ("phased both"). `_live_watchdog_job`
  (`gm_bot/bot.py`) runs `run_audit` over the REAL ledger every 3 min while live, DMs the owner the instant a NEW
  inconsistency appears (✅ when cleared), de-duped via the pure `_watchdog_delta` (8 unit tests). PROOF: suite
  **760 passed/2 skip**; deployed by tag `live-watchdog-20260619` (`cfa8ca3`) — server HEAD==tag, gm active,
  NRestarts=0, `gm_live_watchdog` registered in the running process's startup log, no Traceback/REFUSING/409;
  `live_watchdog_last` pre-seeded with the 3 current stale rows so the first cycle fired SILENT (independent
  re-read). Batched main delta to gm (inert C3 stock button + additive ai_client/stock_shared gm never calls);
  other 4 services untouched. **Read-only investigation of the 3 flagged stale sessions** (Tra/Anan Jun16, Davy
  Jun17): all PRESENT (Davy 49 in-zone pings then stopped sharing 15 min in), pay-safe (late=0, nothing to
  settle); cause = auto-checkout needs a live in-zone share at shift end which they'd turned off → session never
  closes. Benign + recurring → the fallback-closer is logged Open above. The 3 were NOT closed (owner chose
  investigate-first; closing is a separate real-data op).

- **2026-06-19 — retired the resolved 2026-06-08 dated checkpoint (dev-DB isolation).** Verified LIVE that dev
  can no longer silently hit prod — superseded by the Phase-0 fail-closed switch (`active_database_url()` raises
  on unset `TWBSHOP_ENV`), all 5 server units pinned `TWBSHOP_ENV=prod` (confirmed via the running gm process
  environ), `conftest.py` forces staging, distinct `STAGING_DATABASE_URL` present. Accepted residual: prod URL
  still physically in dev secrets (deliberate set is possible; accidental/silent is closed). CLAUDE.md updated.

- **2026-06-17 — REVERSED bug-created attendance data (overnight check-in binding bug).** Owner
  authorized "reverse all of it" after the deep read confirmed all 5 Jun-16 no-show flags were FALSE.
  Applied to PROD with explicit-ID rowcount asserts (mismatch → rollback) + independent fresh-process
  re-read + `/audit` CLEAN after:
  - **A. 5 false no-shows (Jun16) → status='reversed'** (`no_show_reverse`): Chenda·Piseth·Samphass (all
    flagged on their **Tuesday day off**), Davy (present — 20 in-zone pings 06:09-06:20), Meng (present —
    in-zone 06:01). no_show records #1-5.
  - **B. 5 no-show points_events DELETED** (pe #71-75: −540/−720 each).
  - **C. 6 phantom Jun-17 sessions DELETED** (#564/597/599/600/612/654 — PISEY/Nak/Heng/Long/Davy/Thyda,
    all open/no-checkout; the "ends 06:00 / still on shift" `/att` artifact).
  - **D. 6 wrongful Jun-17 points DELETED** (pe #63/65/66/67/68/69: late_uninformed PISEY 540·Nak 550·
    Heng 660·Long 541·Davy 549 + Thyda early 1).
  - **E. PISEY phantom payback debt #150 (540 min) DELETED** (0 bookings referenced it).
  - **KEPT (real, untouched):** debts #145 (Norin 6), #148 (Heng 89), #149 (Nak 10); all 7 real Jun-16
    late points (ref=2026-06-16); Samphass AL #432 (Jun20-21). Owner chose option-1 (reverse bug
    artifacts only; do NOT grace the real first-night lates). Root-cause CODE fix shipped+deployed to gm
    (`10fdf39`) — see CLAUDE.md Current Status. Residual cosmetic: Davy has no Jun-16 session (she only
    shared location at shift end under the old code) → may show "absent" for Jun16 in `/att` though
    present; no penalty (no-show reversed); self-resolves on her next check-in under the fixed code.

## Open (not yet done)

- **2026-06-21 — THYDA (id ?) pre-deploy −15 miss — OWNER DECISION PENDING.** Own-sick filed Jun 21 13:52 PP
  (113 min after shift start), ~2.3h BEFORE the 16:12 deploy → hit the old buggy code, no −15. Per "just Long"
  it's left; but it's TODAY + egregious. Owner: apply −15 to Thyda too (one-liner like Long), or leave it?
  Until resolved it shows in the audit/watchdog for 14 days (bounded). FAMILY-sick late-note: VERIFIED built +
  NOT affected by the self-cancellation bug (computed at screen-build before the case) — confirm in a live walk.

- **🛠 POST-WALK / GO-LIVE HARDENING (owner wants this for live, Jun 14): build the PER-EVENT
  COMMIT-VERIFIER.** **▶ PHASE 1 SHIPPED 2026-06-19** — the broad-net **LIVE audit-watchdog** (see Done
  below); owner picked "phased both". **Only the per-event exact-delta version remains (phase 2): wire an
  independent re-read + scoped assertion into the 1–2 highest-money paths (AL approve/deduct, OT settle/bank)
  — surgery on live balance paths, needs staging before/after proof + a 2nd-opinion pass. DEFERRED.** Original
  spec below. Upgrade of the 60s test-watchdog: instead of polling, verify AT THE MOMENT each
  state-change commits. **What:** at each balance/state commit, do an INDEPENDENT re-read and assert the
  action's expected delta; on failure, DM the owner with SPECIFICS — e.g. "🚨 staff X's AL (3 days) was
  approved but al_left didn't move (still 14)". This is Rule 2 (WRITTEN≠SAVED) made automatic per action:
  the confirmation says "approved ✓", the verifier independently confirms the number actually changed.
  **Design:** trigger on the EVENT/commit, NOT the message text; fire ONCE per event (dual staff+owner
  messages are fine); per-call-site wiring at the state-change points — AL approve/cancel, payback
  credit/clear, OT settle/bank, shift-change settle, swap apply, no-show, special-leave; reuse the matching
  `/audit` validator SCOPED to the one affected row for the assertion (so the verifier and /audit can't
  drift). **Relationship:** does NOT replace `/audit` — /audit stays the backstop for (a) un-wired/future
  paths, (b) cross-row/cross-feature invariants (S5/F14 collisions, "no day double-deducts"), (c)
  drift/time-based problems (approved-past-date never-deducted, stale opens), (d) if the verifier itself is
  bugged/bypassed. Belt (event check) + suspenders (/audit). **Honest ceiling:** verifies the action's own
  contract (the number moved as the code intended), NOT owner intent (a self-consistent but unintended
  number won't fire). **Coverage caveat:** only the wired sites are covered → that's exactly why /audit
  remains. Build AFTER the owner /test walk (touches live write-paths; don't risk them pre-walk). HIGH-RISK
  (balance paths) → real before/after proof on a staging row + a second-opinion pass.

- **🌙 2026-06-19 — FALLBACK END-OF-SHIFT SESSION-CLOSER → BUILT + DEPLOYED + the 3 closed with proof.**
  Owner chose the real fix (not "quiet the warning"). See Done below. (Daily 07:00 PP job; closes dangling
  past sessions at the resolved shift end; settles like auto-checkout.) Nothing left open here.

- **🔓 2026-06-14 (owner-gated — guard blocks Claude from editing `.claude/hooks/`): the command-pattern
  guard has a known BYPASS CLASS.** DB write-path audit (advisor grep, `psycopg2.connect` + raw DDL/DELETE
  across the repo) found: **no script writes payroll / AL / staff_registry / attendance data outside the
  approved `shared/database.py` wrapper** (those tables are touched only by the wrapper + staging-scoped
  tests) — the important reassurance. BUT `hire_bot/*` + ~12 `run_*`/import/seed/migration scripts use raw
  `psycopg2.connect(DATABASE_URL)` and run writes/DELETEs/DDL (hiring/b2b/test tables); `python run_X.py`
  is NOT matched by the highrisk guard's command patterns (it scans the command string, not the file's
  contents). `run_scoring_schema_migration.py` is a real DDL tool that dodges the guard. None touch
  payroll/AL, so exposure is bounded. CLOSE-AT-GUARD is owner-only (Claude can't edit `.claude/hooks/`):
  add a CMD pattern for `python\s+\S*migrat`/`\.connect(` in a run-script, OR (better, parked) route
  `hire_bot/*` + run-scripts through the `_db()` wrapper so they honor the staging switch too (already a
  parked staging item). **DECIDED (owner, Jun 14): LEAVE the guard (don't tune); fix properly by routing
  these through `_db()` at the staging cutover — closes the bypass AND the staging-switch gap in one move,
  and it's a code change Claude CAN do (vs a guard edit it can't). Folded into the staging work.**

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

- **▶ ADVISOR REVIEW of the Bedrock/rule additions (owner: remind me when we have nothing else to do).**
  This session added universal rules; take the WHOLE set to the advisors to see if it can be **leaned /
  unified** (it may already live in parts of Bedrock but not as one awoken whole). The advisors should
  get the WHYs so they judge it as universally as possible. The additions + why:
  - **Precision Standard Rule 4 → WHOLE-PICTURE RE-SWEEP** (v2026-06-13-A, project + global). WHY: I kept
    treating "the new unit passes" as done; owner had to PROMPT the zoom-out each time. Possible overlap
    to lean: Rule 4 (every actor) + Rule 5 (cover every branch) + the breadth memory already circle this —
    is it a new clause or a sharpening of one? Is it the "definition of done" for SHIPPABLE/HIGH-RISK?
  - **State-Integrity Law S5 (multi-feature shared resource)** — WHY: cross-function "spiderweb" risk when
    many features write one slot (AL/redefine/swap/payback schedule). Possible overlap: S3 (atomic claim)
    + menu Law 3 (supersession) + Law 7 (exclusivity) — is S5 a unification of those into the data layer,
    or redundant? Lean question for the advisors.
  - Ask the advisors: can these collapse into ONE universal principle ("a change isn't done until the
    whole it touches is re-verified; a resource with many writers needs one resolver + reverse-on-supersede
    + announce") without weakening the precise/by-construction guarantees? Don't lean if it costs precision.
  - **▶ NEW (Jun 14) — Rule 4 WHOLE-PICTURE RE-SWEEP needs a TRIGGER + ARTIFACT, not just prose. EVIDENCE
    OF THE GAP:** I codified the re-sweep clause on Jun 13, then in the SAME session shipped 4 HIGH-RISK
    phases + declared "functionally complete" WITHOUT a system-scope sweep — owner had to prompt it again.
    So a prose "do it proactively" rule does NOT self-trigger even when freshly written. Diagnosis (see
    memory [[breadth-over-narrowness]] #9): NOT a wires/Bedrock failure (guard was on, auto-bedrock rigor
    ran — but a command-pattern hook can't detect "about to declare done"); NOT a tripwire failure (Rule
    5/6 are ENTRY gates, fired fine — there is no CLOSING-step tripwire and a pre-work gate can't be one);
    the real miss = per-CHANGE (local) sweeps felt complete so the per-ARC (SYSTEM) sweep fell between
    phases (narrowness recurring at the sweep step). **PROPOSED FIX for the advisors to judge/lean:** split
    the rule into (a) per-change local sweep and (b) per-arc SYSTEM sweep that fires at a NAMED boundary —
    any "done/complete/shipped" claim AND before any HIGH-RISK push — and require it as a POPULATED report
    section (specific other-readers/writers, cross-bot blast radius grepped, audit invariant, human-process)
    where blank/"✓ swept" = NOT done. It is NOT a yes/no attestation (those get rubber-stamped like the
    "ask" permission). A pre-push hook could SURFACE the checklist but cannot VERIFY a judgment, so the
    lever is the mandatory populated section, not a new wire. Question for advisors: is this the "definition
    of done" for SHIPPABLE/HIGH-RISK, and does it belong in Rule 6's closing evidence block as a required
    line?
    **▶ UPDATE (Jun 14) — the STRENGTHENING is now APPLIED (owner-directed); only the LEAN/UNIFY stays held.**
    Owner asked "isn't 'don't make me walk an incomplete test' a rule? where are your laws — anything to
    update?" → codified Rule 4 as the **DONE-CLAIM GATE** (Standard bumped to **v2026-06-14-A**, project +
    global): named trigger (done/complete/shipped claim · HIGH-RISK push · ANY invite to walk/test/review)
    + populated report (per-change + per-arc SYSTEM sweep) + a **WALK-READINESS** line (built · pushed ·
    deployed-verified · NO draft/placeholder content in the path they'll touch incl. untranslated strings ·
    per-arc sweep done · invariant check clean). Done with the required self-critique pass (it tightened
    scope to SHIPPABLE/HIGH-RISK + walk invites, and generalized "/audit"→"project invariant check" in the
    global copy). **What REMAINS for the advisors = only the LEAN/UNIFY** (can Rule 4 + Rule 5 + S5 +
    breadth memory collapse into ONE universal principle without weakening precision?) + the **S5
    balance-semantics extension** ("supersession reverses the loser's balance in-txn + announces"). Those
    are the optimization / irreversible-logic parts; the strengthening above did not wait for them.
    **▶ WORKING ARTIFACT (Jun 14) → `docs/GOVERNANCE_INVENTORY.md`.** Owner greenlit the read-only
    governance-inventory evidence pass. It is FILED there (not chat), clearly marked NOT ratified
    doctrine, and changed zero rules/code. It classifies every standing rule (KIND × ENFORCEMENT) with
    a cited artifact + trigger for each "enforced" claim, lists the prose-only rot rules, and poses the
    candidate collapses as QUESTIONS (incl. the advisor warning: don't force-merge S1/S2/S3/S5 — lean the
    redundancies, not the invariants). The lean-set decision stays here in the advisor lane (owner +
    advisors); the builder only installs the ratified result. This inventory is the INPUT to this item.
    **▶ DECIDED (owner, Jun 14): the 8 prose collapses are DECLINED — cosmetic, zero functional change,
    constitution-churn not worth it ("stop polishing wording, build"). The LOAD-BEARING outcomes were taken
    instead: the `.githooks/pre-push` surfacing gate · secret-guard wiring · the DB write-path audit.
    Lean/unify is effectively CLOSED — reopen only if the rules actually cause a problem. Don't re-raise.**


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
  (e) **Sick→AL reverse-order race (Phase 3b-ii residual, Jun 13).** A sick day logged in the sub-second
      *before* a same-day PENDING AL is approved leaves that AL charged — the AL-approval path doesn't yet
      refuse/supersede on a pre-existing sick day. Rare, recoverable (visible + Cancel-able), and a strict
      improvement (sick NEVER refunded AL before). Fix = an AL-approval-side sick guard, or the planned
      `v_supersede_reversed` audit catching the un-reversed charge.

## Done (with proof)

- **2026-06-16 — Heng (id37) points lifted to ZERO (owner: been coming early all week; HIGH-RISK points
  real data, before/after independent proof).** Owner: keep his payback, but ADD to his points to make the
  balance 0, not minus. BEFORE: points total **−156** (`late_uninformed` 67×−2 + `late_informed` 22×−1),
  open payback **#148 = 89m**. Did NOT touch the late events or payback (owner: "he has to payback"; and
  the `/audit` late-points law requires late_* events to sum to the session's 89 late-min — offsetting them
  would desync + trip the daily audit). Instead added a NEW reusable cause **`owner_adjustment`** (value +1,
  active; helper `points_set_rule`, catalogued) and recorded **+156** (ref `owner_jun16_heng_goodwill_to_
  zero`). AFTER (separate-process re-read): **total points = 0.0**, late_* events still sum to **89**
  (audit-consistent), payback #148 = 89 KEPT, owner_adjustment rule active/+1. Additive code (points.py
  CATALOGUE + database.py helper) — not bot-called, data already live on prod, no deploy needed. The
  `owner_adjustment` primitive is now reusable for future balance corrections (+ or −).

- **2026-06-16 — Chomreun (id19) work time corrected + Thyda (id34) zeroed (owner; HIGH-RISK staff/points/
  payback real data, before/after independent proof).** **Chomreun:** work time 06:00–18:00 → **09:00–21:00**
  (`staff_set_work_time`, new additive helper in shared/database.py — not bot-called, so no deploy; the gm
  scheduler/verdict read work_start/work_end live so it applies next tick). No payback/points/lateness on
  him. Per-arc check: it was 20:17 PP (past the old 18:00 end) so he'd received wrong 18:00 checkout prompts,
  but `checked_out_at=None` (he ignored them; auto-checkout couldn't fire — stopped sharing at 11:47) → no
  early checkout, no damage; now prompts correctly at 21:00. **Thyda:** owner "back to zero — payback +
  lateness points." Deleted open payback **#147** (478m "late arrival", open/0-paid/no bookings/no redefine →
  1 row removed) + offset the **478 `late_uninformed`** points with same-cause −478 (ref
  `owner_jun16_thyda_zero`, net 0, audit trail). FLAGGED: her 478 came from an ~8h-late check-in (≈19:58 PP
  vs 12:00 start) — possibly her shift time is also wrong (like Chomreun's); owner only asked to zero, so
  hours left as-is. **Proof (separate-process re-read):** Chomreun work 09:00/21:00; Thyda open debt=None,
  #147 gone, late_uninformed net=0.

- **2026-06-16 — Seth (id21) wiped to ZERO at owner request (PB + late points + late = 0; HIGH-RISK real
  data, before/after independent proof).** Owner: "his real debt also gone, back to zero PB." UNLIKE Por,
  Seth was NOT a radius victim — his only ping was 13.2m (inside even old 100m); the 45-min late was a
  genuine late arrival. His debt #143 was 105m = 60m (owner's morning "1h remaining" correction) + 45m
  (today's auto late). Flagged both points to owner, who confirmed full wipe (Option A). Reversal: debt #143
  had a BOOKED payback slot (#52, 60m) which had auto-created an approved shift REDEFINE (#258, 12:00–22:00,
  normal_len 540). Per-arc catch: deleting the debt while leaving #258 live would have MINTED OT at checkout
  (the extension would credit a non-existent debt → bank as OT). So: cancelled booking #52 (+unlinked its
  debt_id FK), cancelled redefine #258, deleted debt #143 (`payback_delete_debt`, 1 row), offset 45 late
  points with same-cause −45 (ref `owner_jun16_seth_full_wipe`, net 0, audit trail), session #16
  minutes_late→0. **Proof (separate-process re-read):** open debt id21=None, #143 gone, booking #52=cancelled,
  redefine #258=cancelled, late_uninformed net qty=0, session #16 minutes_late=0. Reversible if needed
  (recreate the 60m debt; the 45m + points were the genuine-late portion the owner chose to forgive).

- **2026-06-16 — Por (id16) made whole after the 100m radius bug (owner: "do what's best"; HIGH-RISK real
  points+payback data, before/after independent proof).** Por was on-site (earliest ping 121m @ 12:20 PP)
  but the old 100m zone rejected him until 13:18 PP → system recorded 78 min late, creating payback debt
  **#146** (78m) + late points event #52 (`late_uninformed` qty 78) + session #18 `minutes_late=78`.
  Full reversal: (1) deleted debt #146 (`payback_delete_debt`, was open/0-paid/no bookings → 1 row removed);
  (2) offset the late points with a same-cause `late_uninformed` qty **−78** (ref
  `radius_bug_jun16_por_onsite_121m`) so net late_uninformed = 0, audit trail kept; (3) session #18
  `minutes_late`→0. **Proof (separate-process re-read):** open debt id16 = None, net late qty = 0, session
  #18 minutes_late=0, debt #146 row gone. NOTE: first session-UPDATE didn't commit (used `_db().__enter__()`
  w/o exit) — caught by the independent re-read, redone inside a proper `with _db()` and re-verified. Por
  was the ONLY staffer caught in the 100–150m band (everyone else ≤76m or genuinely off-site @1.2km), so no
  other reversals needed. Root cause fixed structurally by the 100m→150m widening (`fc3fedc`, deployed gm).

- **2026-06-16 — payback reality update (owner: "everyone paid back except Seth, 1h remaining"; HIGH-RISK
  real data, before/after independent proof).** BEFORE (fresh-process read): 2 real open debts — PISEY #60
  (29m) + Por #61 (120m), no bookings; **Seth (id21) had NO open debt** (his old 300m was deleted in the
  Jun 14 reset). Did: cleared both via `payback_credit` (PISEY→0/cleared, Por→0/cleared); created Seth a
  fresh 60-min debt **#143** (`payback_add_debt`, reason "owner correction Jun 16: 1h remaining", created
  today, is_test=False). AFTER (separate-process re-read): exactly ONE real open debt remains — **Seth #143
  balance=60**. **MISMATCH FLAGGED:** Seth wasn't tracked, so "1h remaining" became a *newly created* debt,
  not a reduction of an existing one — say so if that's wrong (reversible: delete #143). Behind
  `attendance_live`=OFF (ladder dormant, no staff pushed).

- **2026-06-14 — GO-LIVE REALITY RESET (owner-instructed, HIGH-RISK real data, before/after proof on real
  rows).** Synced the real DB to the true current state ahead of go-live. **Day-offs:** confirmed all 33
  active staff vs the owner's latest screenshot — 2 drifts corrected to image (An Davy `Wed→Thu`, Rom
  Sopheaktra `Thu→Fri`); rest already matched. **Renames:** Khon Visalpisey call `Sey→PISEY`; Chuch Pisey
  call `Pisey→PISEY-CHUCH`. **Payback:** deleted 3 stale manual-import open debts (Long 80m, Por 240m, Seth
  300m), set true current → PISEY 29m, Por 120m (final open PB = exactly those two; the 2 already-cleared
  paid rows Chantrea/Davy kept as history). **AL:** owner asked to "clear all AL (keep balances)"; I first
  cancelled the 4 planned rows, but `/audit` caught that 3 of them (Sao Visal Jun9/11/12, Chomreun Jun8,
  Heng Jun7) already carry REAL deductions and Long's is PH-comp no-deduct covering today — cancelling a
  deducted row with no refund = a false "missing refund" flag, and refunding was NOT wanted. Resolution:
  RESTORED all 4 to their truthful `approved` state (real past/today leave; balances untouched; all are
  past/today dates so none show as upcoming → go-live unaffected; re-audit CLEAN). The only AL balance
  change is Chantrea `al_left 2.0→1.0` (−1). **OPEN for owner:** if you want those 4 import rows physically
  gone (irreversible delete, balances still kept) rather than left as approved history, say so. **Sick:** logged Yi Sony own-sick (papers seen) for Jun 14; owner then said she's back the 15th →
  case set `papered` (NOT nudged; proven out of the nightly `provisional/me` queue). **Swap:** approved
  day-off swap Pisey↔Heng — Pisey off Mon 15 Jun / works Thu 18; Heng off Thu 18 / works Mon 15 (4
  `dayoff_overrides` written via the real `swap_approve_claim` path; AL-conflict check clean). Proof: a
  fresh-process independent re-read confirmed every value (call names, day-offs, Chantrea=1.0, open PB =
  {PISEY:29, Por:120}, 0 approved real AL, Sony papered, all 4 swap overrides off/work correct). Mechanism:
  added 4 reusable owner-correction primitives to `shared/database.py` (`staff_set_call_name`,
  `staff_set_day_off`, `al_adjust_balance`, `payback_delete_debt`) — additive, NOT called by the bot (no
  deploy needed; data is already live on the shared prod DB). One-off driver `golive_reset.py` deleted
  (teardown). **NOTE:** changes are live on the real DB now (gm reads the same DB) — independent of
  `attendance_live` (still OFF). Normal own-sick+papers behavior (owner asked): debt auto-made at
  declaration is WIPED on papers-accept within the 2-day window (→`papered`), papers seen by owner+Tyty
  only, nightly return-check stops; +15 only if they opt into part-duty.

- **2026-06-14 — DB write-path security audit + surfacing gate (advisor pass, OS-lock deferred by owner).**
  (a) Audited every `psycopg2.connect`/raw-DDL/DELETE in the repo → **no payroll/AL/staff/attendance write
  bypasses `shared/database.py`** (proof: grep classification, sensitive tables touched only by the wrapper
  + staging-scoped tests). Residual guard-bypass class logged in Open above. (b) Added `.githooks/pre-push`
  — a NON-blocking surfacing gate that prints the DONE-CLAIM skeleton when CODE ships, silent on docs-only;
  proven (test: silent on a docs range, printed on a gm_bot range, exit 0 both). It surfaces the gate at the
  push boundary; it does NOT verify (the ceiling). `core.hooksPath=.githooks` already set.

- **2026-06-14 — `secret_guard.py` now wired in the PROJECT `.claude/settings.json`** (owner pasted; the
  highrisk guard blocks Claude from editing that file). Closes the inventory's asymmetry (highrisk was
  repo-wired, secret only global). Independent proof: file parses as valid JSON (a malformed one would
  break ALL hooks — it didn't), both guards present under the one PreToolUse matcher, both script files
  exist, and `secret_guard.py` fed a synthetic Anthropic key returned **exit 2 + "SECRET-LEAK BLOCKED"**.
  Active on hook reload (`/hooks`/restart). Belt-and-suspenders alongside the global wiring.

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
