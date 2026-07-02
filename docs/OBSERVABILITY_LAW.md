# OBSERVABILITY LAW — every send lands, every ladder terminates, every checker is checked

> Owner direction (2026-07-02, verbatim intent): *"everything we built/deployed has logs · all logs get
> checked that things really went through 100% all the time · every escalation and ladder must reach its
> next step · log to log to log endlessly · more checks spread through the day · later my CLIENTS get
> their things auto-fixed in our build whenever."*
> This document is the LAW + the substrate that enforces it. The enumerated audit that produced it →
> `docs/OBSERVABILITY_AUDIT_2026-07-02.md`. The structural guard → `tests/test_observability_law.py`
> (a law without a guard is a hope).

## The law (three tiers)

- **T1 — FYI sends** (a human should see it; no action required): must have
  **{a durable log · delivery verified · alarm on final failure}**. The outbox shape: persist the
  intent BEFORE attempting, mark the outcome after, and something out-of-band re-raises what never
  landed. In-repo chokepoints: `_alarm` (builder alarms → sink+Monitor), `_client_alert` (client-ops
  alerts → sink+GM bot), `_att_send` (attendance sends → `core_send_ledger`), `notify_monitor`
  (builder DMs from any process → `core_send_ledger`).
- **T2 — action-requiring sends** (approvals, escalations — the flow is broken until a human decides):
  T1 **plus {a chase ladder + a recorded terminal}** — re-ping non-responders, escalate, and END in a
  definite state (decision recorded or auto-expire). Model citizens already in-repo: the **AL re-ping
  ladder** (chase ×4 → escalate → auto-expire, DB-backed pings) and the **B2B nudge ticks**
  (verification hourly / wrong-account 6-hourly / dispatch 60s — each re-sends until resolved).
- **T3 — the schedulers themselves** (a dead checker is the ultimate dead-end — the 2026-06-11
  incident: cron daemon inactive, the watchdog had NEVER run, found only by hand): every scheduled
  job, cron script, and service loop **heartbeats `core_job_heartbeats` with its OWN declared
  `expected_gap_min`**. Self-describing — no registry to drift. Anything silent past its gap alarms;
  a silent `cron:*` beat is CRITICAL (the cron daemon itself is likely dead).

**Honest ceiling:** for a bot, "delivered" maxes out at *Telegram accepted the message* (a
`message_id`). A human READING a DM is not verifiable — which is exactly why T2 flows must chase to a
recorded terminal instead of trusting one delivery. And a recurring **recompute-FYI** (daily summary,
stock nudge — the next run re-derives fresh state) is acceptable at T1-minus-ledger: its cadence is
its retry, and T3 guarantees the cadence itself is alive.

## The substrate (what enforces it, and when it runs)

| Piece | What it does | Cadence |
|---|---|---|
| `gm_alarms` sink (`gm_bot/alarms.py`) | durable alarm outbox with `delivered`/`acked` flags | on event |
| `core/sends.py` ledger | intent→sent\|failed for proactive sends (`_att_send`, `notify_monitor`) | on send |
| `core/heartbeat.py` | per-(org, job) liveness beats with self-declared gaps | per job/cron run |
| `core/sentinel.py` — 9 detectors | shadow-dark · malformed check-in · flip divergence · config health · **undelivered alarms** · **stale heartbeats** · **stuck sends** · **silent flip-revert** · **broken flows** | every 30 min (gm sweep) + nightly digest + on demand |
| `core/flowcheck.py` — declarative flow rules | "step A must reach step B (or a terminal) within T", one line per flow, swept for EVERY org — the multi-tenant answer to hand-rolled checkers. First rules: core session must reach checkout/close · a LIVE shadow mismatch must reach `reconciled` (a shadowrun log is itself a step) · an onboarding candidate must reach confirmed/skipped | rides the sweep via detect_broken_flows |
| gm live watchdog (`run_audit`) | money/data invariants over the real ledger | every 3 min |
| collection watchdog (cron) | services active · collection fresh · **gm's own watcher jobs beating** (out-of-process) | every minute |
| morning report (cron 08:00 PP) | audit + sentinel + open/undelivered sink alarms + shadow digest | daily |
| PTB error handler (all bots) | every crash → **sink (durable, Claude-readable)** + throttled Monitor DM | on crash |

**Mutual watch (who watches the watchers):** the 1-minute cron beats → the gm sweep alarms if crons go
silent (daemon death ≤ ~10 min). The gm sweep beats → the cron checks `gm_sentinel_sweep`/
`gm_live_watchdog`/`gm_checkin_scheduler` staleness out-of-process (gm "active" but JobQueue stalled —
previously invisible). The morning report (separate process, daily) re-surfaces anything undelivered.
systemd `Restart=always` backstops process death. No single process is its own only witness.

## The guard — `tests/test_observability_law.py`

Fails the suite on: a gm job registered without a declared heartbeat gap (or a stale gap entry) · the
heartbeat listener removed · `_att_send`/`notify_monitor` de-ledgered · `_client_alert` no longer
sink-first · the one-shot alerts (no-report ×2, sales anomaly, AL escalation) unrouted · a cron script
that stops beating · the watchdog losing a service or the gm-brain check · a sentinel detector removed
· `token_sender` accepting `ok:false`.

## THE GOAL (owner, 2026-07-03 v2 — the standing statement; paste-ready)

> **GOAL — TOTAL VERIFIED OPERATION (the platform's defining property).**
> We are building a multi-tenant business-management platform whose defining property is that it
> VERIFIES ITSELF: every event, message, click, ladder step, scheduled job, and shadowrun — across
> every tenant and every config combination — leaves a durable log, and its arrival at the NEXT
> expected step (or a legitimate terminal) is mechanically checked within a declared time. Anything
> that fails to arrive raises an alarm that itself cannot be lost. Detection and safe self-healing run
> 24/7 in plain code at zero model cost, whether or not anyone is watching.
> The operating loop — ever-accuracy, ever-efficiency, ever-fix, toward zero faults: shadowruns on
> real TWBshop data (customer #1) surface every fault; a fault that could reach other clients must
> surface within ONE daily review cycle (24h SLA, tighter as we mature); every fix ships with a
> regression guard, so a fault class, once fixed, can never return — accuracy only ratchets upward.
> Safe classes auto-fix; money/payroll/deploy fixes are auto-prepared and human-approved, never
> auto-run.
> MAINTENANCE IS INVISIBLE TO CLIENTS: fixes are code/config changes that never alter a client's flow
> uninvited — config applies instantly with no restart; behavior changes ship dark behind per-tenant
> flags with instant revert and auto-revert-on-divergence; repairs restart only in quiet windows where
> polling queues every message so nothing is ever lost. Clients keep operating while the platform
> improves underneath them.
> No feature is "built" until it declares its steps, terminals, SLAs, and liveness heartbeat —
> enforced by the suite (`docs/OBSERVABILITY_LAW.md` · `tests/test_observability_law.py` ·
> `core/flowcheck.py`). Clients receive only the hardened result.

## MAINTENANCE INVISIBILITY — the contract (owner, 2026-07-03)

Every fix must take one of these four shapes, each with a proof obligation; anything else is a design
error to raise before building:

1. **Config change** — applies INSTANTLY, no restart (`get_config` reads fresh per call; atomic +
   race-locked writes; proven s56). Zero client impact by construction.
2. **Additive-dark code** — ships inert (flag-off / no-exception-set / `CREATE IF NOT EXISTS`),
   byte-identical until a per-tenant flag flips it; the flip is instant (DB flag, no restart),
   instantly revertible, and auto-reverts on divergence (`core.flip`). The C2/D2/F1 nets are the
   proven pattern. Zero behavior change until CHOSEN, per tenant.
3. **Behavior-preserving repair** — same outputs, healthier plumbing (tonight's chokepoints/ledgers).
   Proof = the suite + byte-identical/no-op verification on prod.
4. **Process restart** (when code on a live bot must reload) — the honest ceiling: long-polling means
   Telegram QUEUES every client message during the ~2–3s gap and the bot drains them on resume —
   **nothing is ever lost**; jobs are restart-safe (state in DB, idempotent, catch-up sweeps, and now
   heartbeat-verified). Residual client-visible artifact: a few seconds' reply delay, done in quiet
   windows. Never webhooks (a down endpoint DROPS, a poller QUEUES).

Multi-tenant note: one process serves many tenants, so shape 4 briefly touches all — but shapes 1–3
carry per-tenant RISK isolation (org-scoped flags/config), which is the part that matters: a fix for
client A cannot change client B's behavior uninvited.

## Known not-covered (deliberate, with rationale)

- **Swap + shift-change approvals have detection, not chase** (`v_swaps`/`v_shift_changes` flag stuck
  ones; no re-ping/auto-expire ladder like AL). A chase ladder sends new messages to real staff =
  behavioral change → owner-gated, in `docs/PENDING_WORK.md`.
- **Retail/B2B per-send ledger**: their proactive sends are recompute-FYI class (summaries, reminders)
  or already T2 (b2b nudge ticks); crashes now sink via the shared error handler. Chokepointing them
  is the next increment, not tonight's.
- **Listener has no beat**: doubly externally covered (systemd check + `ops_messages` freshness in the
  1-min watchdog).
- **Phase-5 continuous checker (Claude reading the sink on a schedule, multi-tenant auto-fix)**:
  designed, owner-gated, OFF. Everything it would read now exists and is being written.
- **Retention**: `core_send_ledger`/`core_job_heartbeats`/`core_flip_log` grow unbounded — tidy jobs
  are a later, low-risk chore (heartbeats are 1 row/job, only the ledger actually grows).
