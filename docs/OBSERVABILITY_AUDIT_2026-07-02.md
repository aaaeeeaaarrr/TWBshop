# DEAD-END / LADDER-TERMINAL AUDIT — 2026-07-02

> Step 1 of the observability program (owner endorsed 2026-07-02). Method: 4 parallel read-only sweeps
> per the DRASTIC protocol (grep the CLASS, never the instance) — ① every gm-bot send/escalation site,
> ② every cron/script/service sender, ③ every other bot's send site, ④ an independent inventory of every
> EXISTING verifier — then a bipartite match (send-sites × verifiers). Each site was scored on the triple
> **{durable log · terminal step · downstream verifier}**. Ground truth was read from the SERVER (real
> crontab, real service list), not from docs — which caught two doc-vs-reality drifts (below).
> The law this produced → `docs/OBSERVABILITY_LAW.md`. The guard → `tests/test_observability_law.py`.

## DEAD-ENDS found → dispositions

| # | Dead-end | Why it was lost-forever | Disposition (2026-07-02) |
|---|---|---|---|
| 1 | **Cron/service liveness itself** — nothing watched whether the 3 crons ran (bit once: 2026-06-11, cron daemon inactive, watchdog never ran, found by hand) | a dead checker alarms nothing | **FIXED** — `core/heartbeat.py` + beats in all 3 crons + the automations loop + an APScheduler listener beating all 27 gm jobs; `detect_stale_heartbeats` on the 30-min sweep; silent `cron:*` = CRITICAL |
| 2 | **gm JobQueue stall** — gm `active` but its scheduler dead = watchdogs/sentinel silently gone | in-process sweep can't see itself die | **FIXED** — the 1-min collection-watchdog cron now cross-checks `gm_sentinel_sweep`/`gm_live_watchdog`/`gm_checkin_scheduler` beats out-of-process |
| 3 | **`_missing_final_report_job`** (books-missing 06:30 owner DM, raw send) | tomorrow's run checks a different day → a failed DM = that day's books-alert gone forever | **FIXED** — new `_client_alert` chokepoint (sink-first → GM-bot DM → `mark_delivered`); severity **money**; mid-report + sales-anomaly + AL-ladder-escalation routed too |
| 4 | **AL-ladder escalate DM raw** + `al_mark_escalated` set first → a failed DM never retried | durable flag blocks the retry; owner never told | **FIXED** — routed via `_client_alert` (undelivered → sweep re-raises ≤30 min; auto-expire terminal unchanged) |
| 5 | **`gm_alarms` design drift** — `alarms.py` docstring CLAIMED no-report + error-handler write the sink; neither did | 5 bots' crash alarms invisible to Claude/morning report; throttle suppressed repeats with no durable trace | **FIXED** — shared error handler now sinks EVERY crash (`error:<bot>`, throttled repeats pre-acked), `mark_delivered` on Monitor success; the docstring is true again |
| 6 | **Undelivered sink alarms sat silent** — `delivered=FALSE` existed but only the daily morning report surfaced it | up to 24h blind window | **FIXED** — `detect_undelivered_alarms` on the 30-min sweep (money undelivered → CRITICAL) |
| 7 | **`notify_monitor` fire-and-forget** — returns a bool most callers drop; no durable record (morning report's own delivery, watchdog alert, listener alert, hire pipeline alert) | a failed builder DM vanished | **FIXED** — ledger inside `notify_monitor` (`core_send_ledger` intent→sent\|failed) + `detect_stuck_sends` |
| 8 | **Hire trial-approval DM** — DB write INSIDE the same try as the send → failed send = zero state, applicant waits forever; pipeline runs once | double-swallowed, no re-nudge | **FIXED** — state (`pending_approval`) written FIRST (nothing gates on it; re-run re-sends), failure → durable sink alarm (sweep re-raises to owner) |
| 9 | **Hire applicant questions** — forwarded to owner, applicant told "we'll reply", no record | broken human promise on a dropped send | **FIXED** — failure → `hire_question_lost` sink alarm carrying the question text |
| 10 | **`core/flip.py` auto-revert = silent DB event if a future caller forgets to alarm** (and `detect_flip_divergence` stops watching once `authoritative=FALSE`) | dormant-armed trap | **FIXED** — `detect_silent_flip_revert` (any recent `auto-revert:*` reason → CRITICAL, caller-independent) |
| 11 | **Automations dispatch recorded `ok:false` as sent** (`token_sender` ignored the response) | silent Telegram rejection = recipe never retried | **FIXED** — `token_sender` raises on `ok:false` → `_record_sent` skipped → natural retry next tick (debounce intact) |
| 12 | **Service-liveness blind spots** — `twbshop-automations`/`-wizard`/`-retail` in NO watcher list | a dead service alarmed nothing | **FIXED** — collection watchdog + `scripts/monitor.py` cover all 6 active units (b2b stays EXPECTED_INACTIVE) |
| 13 | **B2B markpaid owner-approval DM** — self-swallowed, no re-nudge; staff sees "awaiting approval" forever, money never applied | the worst money dead-end — but **B2B is DISABLED** | **PARKED** → added to `docs/B2B_LANDMINE_FIX_PLAN.md` scope (F-class, fix WITH owner at re-enable; pattern to copy = the existing verification-nudge tick) |
| 14 | **Retail flagged-staff-message alert** — AI flag exists only in a group post + log line | a benign mis-send loses the flag | **PARKED** (retail deploy; low frequency) → PENDING_WORK |
| 15 | **`_callout_job`** — dedupe stamp set BEFORE sends (anti-retry by design, behavioral nudge) | accepted-by-design | documented, no change |
| 16 | **Audit-chain nightly anchor cron MISSING on the server** (docs said nightly; real crontab has no `anchor_audit.py` line) | tamper-anchor not being laid | **→ deploy step tonight** (add the cron line + one manual verify run) |

## PARTIAL classes — accepted with rationale (the law's recompute-FYI clause)

Daily/weekly **recompute-FYI** sends (retail production summary + missing-photo reminder, stock-order
nudge, weekly digest, pay-restore/AL-accrual notes, reconciliation previews, b2b balance reminders):
the next run re-derives fresh state, so the cadence is the retry — and T3 heartbeats now guarantee the
cadence itself is alive. NOT converted per-send tonight (scope honesty). Notables for later increments:
retail has no missed-summary catch-up on restart (b2b HAS one — `_startup_summary_check`; port it),
and `automation_dispatches` records intent-not-delivery (mitigated by #11).

## Verifier inventory (agent ④) — the other half of the matrix

- **Fixed-list detector registry** (`core/sentinel.py::DETECTORS`, now 8) auto-run by the 30-min gm
  sweep + morning report + (dormant) builder_monitor — this WAS the designed generic chain-checker;
  the gap was detector coverage, not architecture. No auto-discovery (deliberate; the floor test
  guards shrinkage).
- **`gm_bot/audit.py`** = ~24 hand-rolled `v_*` invariants over 14 attendance/payroll tables, consumed
  by 5 schedulers/commands (3-min live watchdog · daily 07:30 · test watchdog · `/audit` · morning
  report). **Domains with NO auditor:** stock, POS/sales, payroll payslip math, food_money, report
  content, comms → future detectors as those domains go live (multi-tenant: `run_audit` is TWB-legacy
  single-tenant; only the sentinel is org-scoped).
- **Reapers/closers** (session-closer 07:00 · payback no-show reaper 07:05 · AL expiry · reason-nudge
  +30 auto-resolve · self-closing alarms) = the self-healing tier, all with durable terminals.
- **Approval-ladder asymmetry:** AL has chase→escalate→expire; **swap + shift-change have
  detection-only** (`v_swaps`, `v_shift_changes`) + in-memory card coords (lost on restart) →
  PENDING (behavioral build, owner-gated). `comms.py` ladder exists but is unwired (dormant by
  design, owner-gated go-live).
- **`builder_monitor.py`** is the one non-gm sender already on the COVERED sink-first pattern —
  deliberately dormant until multi-client cut-over (W3 #5).
- **`monitor_bot.py`** (owner dashboard) is itself unwatched — acceptable: it's a read surface; the
  delivery channel (`notify_monitor` direct POST) works without it. Noted, not built.

## Doc-vs-reality drifts caught (and fixed)

1. `run_collection_watchdog.py` docstring said cron `*/30`; the real crontab runs it **every minute**
   → docstring corrected (its heartbeat gap assumes the 1-min truth).
2. `alarms.py` B1 docstring claimed sink coverage that didn't exist → the code now matches the claim
   (#3, #5).
3. `morning_report.py` "NEVER writes anything" → now "nothing except its own liveness heartbeat".

## What tonight's build adds up to

Every proactive send now either (a) writes a durable outbox record whose non-completion ALARMS
(`gm_alarms.delivered` / `core_send_ledger`), or (b) belongs to a recompute cadence whose LIVENESS
alarms (heartbeats) — and the checkers themselves are cross-watched from a separate process. Intraday
coverage = the existing 30-min sweep auto-running the 4 new detectors + the 3-min watchdog + the 1-min
cron probe; the 08:00 digest is now the backstop, not the only net. The remaining honest gaps are the
parked items above + the owner-gated Phase-5 continuous checker.
