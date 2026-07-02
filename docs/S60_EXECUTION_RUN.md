# S60 EXECUTION RUN — the standing autonomous list + the owner YES-PACK (2026-07-03)

> Owner: "when I /clear then say keep going, you do it all." THIS DOC is the contract. On every
> "keep going": run **Part 0**, then work **Part A top-to-bottom, one item at a time, to done**
> (bedrock where flagged; quiet-window deploys; each item ends with its done-criteria met + status
> updated here). Part B items fire the moment the owner types their yes-word — in any session, in
> any order. Part C needs the owner's hands (park until he does his step). Big items may span
> sessions — progress is ticked HERE so every "keep going" resumes exactly where the last stopped.

## Part 0 — EVERY session start (the daily ritual)
- [x] **Fault check**: `python scripts/alarms.py --open` + prod sentinel sweep + flowcheck → fix what's
      found → every fix leaves a guard. FIRST TIME ALSO: verify the checkout hook's first real firings
      (journal `[SHADOW] checkout fed` from the ~06:00 wave) + the 9 crew sessions completed + the
      08:00 digest clean.
      **2026-07-03 01:35 PP run: CLEAN** — sink 0 open · audit 0 · sentinel+flowcheck = only the known
      aging-out finding (staff 1, 26/06; gone 15:01 PP) · heartbeats stale=[] · all 6 services active.
      **⏳ STILL DUE (physically can't run before morning — it was 01:35): the ~06:00 checkout-wave
      firings + the 08:00 digest → FIRST ITEM next session.**

## Part A — AUTONOMOUS, in order (I do; owner reads reports)
- [x] **A1. DB pooling** — BUILT + SUITE-GREEN 2026-07-03 (~02:30 PP). **Finding: the "16/25, no pool"
      reading was WRONG** — a `SimpleConnectionPool(1,10)` has existed since 2026-05-22; ~10 of the 16
      are DO-internal, our app holds ~6 (1/service). The REAL fixes shipped: `ThreadedConnectionPool`
      (threads write today — Simple is thread-UNSAFE), per-process cap 4 (`TWBSHOP_DB_POOL_MAX`),
      burst-waiting `_acquire` (5s timeout), poisoned-conn eviction, **every raw `psycopg2.connect`
      folded through `raw_connect()`** (14 files; closes the 2026-06-14 ledger bypass item) + structural
      guard `tests/test_no_raw_db_connections.py` + sentinel `db_headroom` detector (warn 80%/crit 92%).
      Full gate **1381p/0f**. **▶ DEPLOYED (canary half) + VERIFIED 2026-07-03 ~03:15 PP** — commit
      `8f0b7d7` = tag `session-60-parta-20260703`; server HEAD==8f0b7d7; wizard PID 1688053 · hire
      1688059 · automations 1688052, all NR=0, clean boots, "DB pool → PROD" banner in each journal,
      wizard :8090=200; post-deploy `heartbeat.stale('twb')=[]` + sink 0 open; the 1-min watchdog cron
      + 08:00 digest now run the pooled code from disk = overnight burn-in. **REMAINING: gm·retail·
      listener restart in the morning lull** (after the wave verification; retail BEFORE 14:00 PP; then
      re-run `repair_core_mispairs` for any pairs the old-code 06:00 wave creates). **A2's historical
      repair APPLIED on prod: 14/14 pairs merged, 0 remaining (independent re-read); worked-minutes
      cross-checked against live settle numbers (Thyda 510 ✓ Vannary 839 ✓).** ⚠ deploy gotcha logged:
      a stale server tag (`session-59b`) non-zeroed `git fetch --tags` and silently stopped the &&
      chain — verify HEAD moved, never trust the chain.
- [x] **A2. Redefine/split-aware shift MATERIALIZATION in core** — BUILT 2026-07-03 (~03:30 PP).
      **Prod data killed the split hypothesis**: every mispair (Nak's 20:56/20:57, Thyda's 06:00) =
      the check-in fed live's RESOLVED start while the checkout bound the BASE window → two orphan
      half-shifts. Cure = symmetric resolution: `check_in/check_out(windows=…)` (multi-window,
      split-capable binding in `_bind_shift`), `shadow_checkout` now resolves via live `resolve_day`
      (`att_check_out` passes `shift_date`; the >3h-extension KNOWN LIMIT is gone), native
      `core.derive.resolved_windows` for cut-over/web, web channel wired (all windows + overrides).
      BONUS: materialization is containment-gated → no more empty sibling rows. 8 tests
      (`tests/test_shift_materialization.py`) + s59c feed tests green. **Historical orphans:
      `scripts/repair_core_mispairs.py` (dry-run default) — run on prod at deploy.**
- [x] **A3. Settle-flip STATS PREP** — DONE 2026-07-03 (read-only prod): **44/44 settle comparisons
      agree** (Jun 23→Jul 2, 0 disagreements); **19/19 fully-modeled payback-slot settles agree
      exactly** (worked+ot_banked+pb_cleared, credits incl. 116/86/61/60/58/57 min); 25 older rows =
      pre-#5 informational. **Honest caveat: 0 samples with ot_banked>0** — the OT arm is parity-locked
      by drift-guard tests only. → the "flip settle" yes-word is data-backed.
- [x] **A4. Retention tidy** — BUILT 2026-07-03: `core/retention.py` (flip_log >30d · send_ledger >90d;
      evidence tables deliberately untouched) + daily `gm_retention_tidy` 03:40 PP (gap declared; law
      test green) + the ops_messages retention KNOB design → `docs/CAPACITY_AND_SCALE.md` §5.3.
      Measured: flip_log ~470 rows/day = the only fast grower. **Rides the gm restart.**
- [x] **A5. Retail increments** — BUILT 2026-07-03: `_startup_summary_check` ported (missed-summary
      catch-up on boot + `retail_last_summary_date` bot-meta recording) + the staff-flag durable record
      (sink-first → group post → mark_delivered; urgent=money severity; audit #14). 4 tests
      (`tests/test_retail_increments.py`). **Rides the retail restart (morning lull, BEFORE 14:00 PP —
      the summary hour — so the catch-up can't false-fire; pre-seed the meta key at deploy anyway).**
- [x] **A6. Multi-tenant runtime host** — DESIGN + INERT SKELETON 2026-07-03: `docs/RUNTIME_HOST_DESIGN.md`
      (one process, N PTB Applications on one loop; per-tenant crash isolation + heartbeats; tokens from
      core_org_secrets; shares the ONE pooled DB → N tenants ≈ 0 extra conns) + `runtime_host/host.py`
      (TenantSpec · build_apps fail-soft · manual-lifecycle run) + 2 tests. NOTHING runs it — first user
      = the onboarding demo / tenant #2, per the capacity plan trigger.
- [x] **A7. Backup/restore drill** — 2026-07-03: DO PG backups VERIFIED (8 dailies, ~0.23 GB, 20:13 UTC
      cadence) + restore-to-fork EXECUTED via API (fork created from the newest backup → row counts
      verified → fork DELETED; runbook → `docs/BACKUP_RESTORE_RUNBOOK.md`). ~~escalate~~ the API path works.
- [x] **A8. Anomalous-access rule + canaries** — assessed HONESTLY: with auth OFF, wizard localhost-bound
      and zero external clients there is NO signal to detect on — an inert detector with invented
      thresholds would be draft content. The design is pinned in `docs/CAPACITY_AND_SCALE.md` §4 with its
      build trigger (= W3 window / first external client, alongside `WIZARD_AUTH=1`). Nothing to build today.
- [x] **A9. Small tail** — 2026-07-03: swap + shift-change senior-card coords now persist
      (`approval_cards` self-provisioning table + union-read at all 4 sites — a gm restart no longer
      orphans co-seniors' cards; the Part-C chase ladders get durable coords); retention ages the
      peek-only rows (>30d). 3 tests. monitor_bot self-watch: stays a NOTE (read surface; delivery
      works without it — audit's own disposition).

## Part B — YES-PACK: one word from the owner → I complete it fully
| Yes-word (type it any time) | What I then do, end-to-end | Risk net |
|---|---|---|
| **"tables ok"** | stop flagging the 2 additive s59 tables | — |
| **"flip points"** | `set_authoritative('twb','points',True)` → watch `core_flip_log` on real events → report | auto-revert + instant manual revert |
| **"flip settle"** (after A3 stats look good) | same for settle — the last money path onto core | auto-revert + instant revert |
| **"set the keys"** | generate `ORG_SECRET_KEY` + `ANCHOR_HMAC_KEY` → secrets.py (deliberate #HIGHRISK-OK) → `--push-secrets` → restart wizard → verify PII encrypt round-trip + signed anchors | reversible; staged verify |
| **"name = ___"** | apply the product/company name everywhere safe (wizard/docs/templates) | rename-only |
| **"phase5 on, daily"** (or a cadence) | schedule the continuous checker (cloud routine reading sink+flowcheck+digest per tenant) → digests arrive | read-only agent; safe-class only |
| **"b2b go"** | deploy F2–F5 money fixes → indexes auto-apply → start `twbshop-b2b` → verify; owner just glances at the FIRST real payment card | claim-first fixes + staged |
| **"config batch go"** | migrate the next MED-risk config-key batch (prove default==current → deploy) | behavior-preserving proofs |

## Part C — needs the owner's HANDS or real decisions (park until given)
- **3 answers → chase ladders**: re-ping every __h? · expire when? · escalate to whom? → then I build+deploy the swap/shift-change T2 ladders alone.
- **Comms go-live**: window + ladder choice + Khmer line approval → I deploy + verify on one real mention.
- **Onboarding real-bot**: BotFather `/newbot` → paste token → I run the demo; you tap Confirm once.
- **Hire launch**: post the job ad (I watch the pipeline).
- **Accountant P2 matcher**: HIGH-RISK money — your go + a joint staging walk, then I build claim-first.
- **AppSheet**: create the app → paste creds → I wire + import the 143 items.
- **Server GitHub PAT**: create → paste → I install.
- **`secret_guard.py:33`**: open the file → paste my one-liner → save (the hook blocks me).
- **Real HR values**: fill in wizard `/staff`.
- **Dashboard taste**: point at what to change.
- **W3 #5 monitor cut-over**: deferred to multi-client by design; pick an evening when it's time.
