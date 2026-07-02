# S60 EXECUTION RUN — the standing autonomous list + the owner YES-PACK (2026-07-03)

> Owner: "when I /clear then say keep going, you do it all." THIS DOC is the contract. On every
> "keep going": run **Part 0**, then work **Part A top-to-bottom, one item at a time, to done**
> (bedrock where flagged; quiet-window deploys; each item ends with its done-criteria met + status
> updated here). Part B items fire the moment the owner types their yes-word — in any session, in
> any order. Part C needs the owner's hands (park until he does his step). Big items may span
> sessions — progress is ticked HERE so every "keep going" resumes exactly where the last stopped.

## Part 0 — EVERY session start (the daily ritual)
- [ ] **Fault check**: `python scripts/alarms.py --open` + prod sentinel sweep + flowcheck → fix what's
      found → every fix leaves a guard. FIRST TIME ALSO: verify the checkout hook's first real firings
      (journal `[SHADOW] checkout fed` from the ~06:00 wave) + the 9 crew sessions completed + the
      08:00 digest clean.

## Part A — AUTONOMOUS, in order (I do; owner reads reports)
- [ ] **A1. DB pooling** — the measured wall (16/25 conns TODAY). App-side pool in `shared/database._db`
      (or pgbouncer on the droplet). HIGH-RISK-adjacent (touches every DB call): staging-proven, full
      suite, quiet-window deploy, all services restarted once, verified. Done = conns drop + suite green
      + live verify.
- [ ] **A2. Redefine/split-aware shift MATERIALIZATION in core** (flowcheck 2nd catch): core shifts
      materialize from the RESOLVED day (redefines/splits/come-early), not the base window → mispairs
      end; exact worked-minutes self-derivable. Shadow-side only; parity tests; big build.
- [ ] **A3. Settle-flip STATS PREP** (feeds YES-2): read-only digest of payback-slot settle agreement on
      real checkouts (`shadow_comparisons kind='settle'`) → present numbers to the owner.
- [ ] **A4. Retention tidy** — age-out jobs for `core_send_ledger`/`core_flip_log` (+heartbeat rows are
      1/job, fine) + design the ops_messages retention KNOB (product lever). Additive, small.
- [ ] **A5. Retail increments** — port b2b's `_startup_summary_check` to retail + durable staff-flag
      record; ONE quiet-window retail restart (also picks up the error-handler sink mirror + noise gate).
- [ ] **A6. Multi-tenant runtime host** — design doc + inert skeleton (one process, N tenant bot apps);
      kills the ~30-client process wall. No live change until a 2nd tenant exists.
- [ ] **A7. Backup/restore drill** — verify DO PG backups + attempt a restore-to-fork via API; document
      the runbook. Escalate to Part C only if the DO console blocks the API path.
- [ ] **A8. Anomalous-access sentinel rule + per-tenant canary values** (inert until external clients).
- [ ] **A9. Small tail** — persist swap/shift-change senior-card coords (like `al_pings`) ·
      monitor_bot self-watch note.

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
