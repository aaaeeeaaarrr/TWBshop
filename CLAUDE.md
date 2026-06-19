# Bakery Automation System — Project Rules & Status

---

## Real-Path Precision Standard — UNIVERSAL, ENFORCED (full local copy — self-contained)
REAL_PATH_PRECISION_STANDARD_VERSION: 2026-06-14-A

> This is a FULL copy (not a pointer) so the project carries its own enforcement even if the global
> `~/.claude/CLAUDE.md` fails to load, is stale on another machine, bootstrap wasn't run, the secrets
> repo is unavailable, or a future session only sees this repo. Reliability > elegance for operating
> constraints. Same text lives in the global file.

Constraints, not values. The bar is EVIDENCE, never promises. Chat stays fast and friendly; proof on
real work never softens. The user may demand the evidence block at ANY time; its absence = NOT done.

### MODES — default UP if unsure.
- **CHAT / THINKING** — explain / plan / review. No ceremony.
- **TRIVIAL EDIT** — comments / docs / wording, no runtime change. Light proof: files + quick check.
- **SHIPPABLE** — any behavior / UI / API / DB / bot / report / deploy change. Full real-path evidence
  before "done."
- **HIGH-RISK** — money / payroll / staff+customer records / audit / deletions / migrations /
  permissions / prod deploy / integrations / secrets. No shortcuts, no "probably," nothing called done
  without real-path proof.

### RULES
1. **ONE REAL SYSTEM — no behavior fork.** Isolate data / routing only, never logic / permissions /
   paths. Isolation reversible with teardown; never pollute real data. Test once → ship that same
   code; go-live only flips routing/config; re-test if code changed.
2. **PROOF, NOT ECHO.** Nothing is done / fixed / live / saved on the operation's own word. Verify
   from an INDEPENDENT read after it settles: **PUSHED ≠ LIVE** (ref==origin, service up, running code
   carries the change); **WRITTEN ≠ SAVED** (commit/close first, then re-read from a SEPARATE
   connection/session/process). A 2xx, RETURNING row, return value, same-transaction read, local
   buffer, or enqueue/send acknowledgement is NOT final proof. Check state yourself before blaming it.
3. **FILES ARE TRUTH, CHAT IS DISPOSABLE.** Persist to the repo as you go; prove from git.
4. **EVERY ACTOR, NO DEAD ENDS.** User-path first and each role's view (backend-only proof is
   insufficient for user-facing work); every control does a real action or faithfully advances through
   a real path.
   **DONE-CLAIM GATE — the closing step of SHIPPABLE/HIGH-RISK; it fires at a NAMED boundary, never only
   when prompted.** The moment you would call something done / complete / shipped / ready, OR push
   HIGH-RISK, OR invite the user to walk / test / review it — STOP and produce a POPULATED report. A bare
   "✓ done" or a yes/no attestation does NOT count (those get rubber-stamped, exactly like an "ask"
   prompt the user always approves). It is the trigger that fills Rule 6's evidence block. Two distinct
   sweeps:
   - **Per-change (local):** the change itself does what it says.
   - **Per-arc (SYSTEM) re-sweep:** every OTHER reader/writer of the same state, the cross-module /
     cross-bot blast radius (GREPPED, not guessed), the system-level invariants/audit, and everywhere the
     same pattern could live (technical AND human-process). The unit passing is NOT the system being correct.
   **WALK-READINESS — before you EVER put the user in front of it to test/walk/review:** built ✓ · pushed
   ✓ · deployed+verified if it runs on a service ✓ · NO draft/placeholder content in the path they'll
   touch (untranslated/draft strings, TODOs, stubbed buttons) ✓ · the per-arc sweep done ✓ · `/audit`
   clean ✓. If ANY line is incomplete, SAY SO plainly and DO NOT invite the walk — never let the user
   discover mid-test that something wasn't built, pushed, deployed, or translated. (Trivial/chat edits
   stay lean — this whole gate is the SHIPPABLE/HIGH-RISK closing step, not pre-work ceremony.)
5. **COVER EVERY BRANCH** — success / fail / cancel / invalid / permission / duplicate / edge; one
   harness per workflow. Fixes become permanent guards (regression test or constraint), never symptom
   patches.
6. **REPORT FAITHFULLY.** Don't ask unless needed, but state assumptions, verify inputs against
   context (flag mismatches before applying), and name any shortcut as a tradeoff before taking it
   (HIGH-RISK: none). SHIPPABLE / HIGH-RISK ends with: files · commands · path verified · evidence
   (independent, post-settlement) · cleanup · regression guard · remaining risk · next step.

### TWBshop HIGH-RISK paths (no shortcuts, real-path proof mandatory)
- Payments / KHQR / Bakong · payroll & salary (staff_registry, slips, pays) · staff records &
  ex-staff offboarding / bans / permissions · DB migrations & deletions · deploys to the twbshop-*
  services (retail / b2b / gm / listener / hire) · the attendance live path (`attendance_live`, LIVE since 2026-06-16).
- Attendance test harness design: `docs/ATTENDANCE_TEST_MODE.md`.

---

## Connectivity Reference
*Broken something? Connectivity checks (SSH · GitHub · DO API/droplet/db · Anthropic · Telegram) → `docs/CONNECTIVITY.md`.*

---

## What This System Does
A Telegram-based bakery operations system that handles:
- Customer orders (received, confirmed, stored)
- Daily production totals sent to the bakery staff group
- Per-customer fulfillment lists (who ordered what, pickup/delivery time)
- Staff workstation and fridge photo submissions
- Stock sheet photo uploads (for later OCR processing)
- Staff communications monitoring (for later AI analysis)

---

## The `push` and `pull` words — multi-lane (one word in, everything synced)

The owner types ONE word and expects the WHOLE project synced across machines. Lanes are git
worktrees on `lane/<name>` branches; **`main` is the single thing that travels** (deploys come from
TAGS, never from `main`, so `main` may safely carry work-in-progress from every lane).

**When the owner says `push`:**
1. Commit the current worktree's CODE (clear message). Do NOT edit the tracked `CLAUDE.md` from
   inside a lane — lane-local notes go in `CLAUDE.local.md` (gitignored) so merges never conflict.
2. Run **`scripts/checkpoint.ps1`** — it merges EVERY `lane/*` branch that's ahead into `main`,
   pushes `main` + all lane branches, and verifies `main == origin/main`. On a real conflict it
   ABORTS that one lane and reports it (main untouched) — fix only that lane, then re-run. It never
   resets and never force-pushes.
3. Update **Current Status** in this file (on `main`, one place), commit, push.
4. Deploy ONLY if a LIVE service's code changed, and only that service (see Deploy Discipline).
   Inert/design/docs changes deploy nothing — say so.
5. Report: merged lanes · any conflicted/dirty lanes · pushed SHA · deploy (or "nothing live changed").

**When the owner says `pull`:** run **`pull.ps1`** (fetch --all, rebase, secrets sync, pip). `main`
holds the full checkpoint; if you're on a lane it tells you. Then read Current Status (next rule).

Preview anytime without changing anything: `scripts/checkpoint.ps1 -DryRun`. Start a new lane:
`scripts/make_lane.ps1 <name>` (see `docs/PARALLEL_LANES.md`).

---

## After Every Pull

**Read the "Current Status" section of this file immediately.** It is the only source of truth for what to work on next. Never use memory notes — they are local to one machine and go stale across machines.

**Also read `docs/ACTIONS_LEDGER.md`** — any operational/real-data instruction that's still Open.

---

## Operational Instructions — never drop a real-data change

Real-data instructions (clear/adjust **payback**, deduct/add **AL**, change a **balance**, **staff
record**, **payment**, or any "do X to the numbers") are HIGH-RISK and must NEVER sit unacted — a
dropped one makes the shop's numbers wrong. The rule:

1. **Do it immediately** when instructed, with before/after proof from an INDEPENDENT read (separate
   process/connection) — never defer a data change to "later in the task" or treat it as a chat aside.
2. If it genuinely can't be done right now, **log it to `docs/ACTIONS_LEDGER.md` → Open** the moment
   it's given, and tell the owner plainly it is NOT done yet.
3. **Read `docs/ACTIONS_LEDGER.md` at session start** (with Current Status). At the end of any turn
   where the owner gave instructions, **state the open loops** — "Open items: none" or the list.

Why: an instruction acknowledged only in chat, never executed or written to a file, gets buried by
context compaction and the numbers silently go wrong. Files are truth; chat is disposable. (Now that
`attendance_live` is ON (since 2026-06-16), most of these happen through the bot's audited button flows, not by hand —
which shrinks this risk on its own.)

---

## Deploy Discipline (restart-safety — read before restarting any service)

A restart is a ~2–3s blip: the bots long-poll, so Telegram **queues** messages during the gap and the
bot drains them on resume — nothing is lost. Polling is the safety net; **never switch to webhooks**
(a down endpoint drops the POST). The risks are small and these three habits remove them. They are
human discipline, not code — honor them on every deploy (Claude enforces them when asked to deploy):

1. **Restart in the quiet window, not at a shift edge.** The only moments a restart can skip a
   prompt are when check-in/checkout jobs fire — roughly **05:30–07:00 · 14:00–15:30 · 20:30–21:30**
   (Phnom-Penh). Deploy in a mid-afternoon lull and even the self-healing risks vanish.
2. **Batch deploys.** Accumulate the day's changes and restart once — don't restart per micro-edit.
   Check `git log origin/main..HEAD` before deploying to see what's actually shipping.
3. **Restart only the changed service.** A `gm` deploy must never touch `twbshop-retail` /
   `twbshop-b2b` (the customer-facing + payment bots). Restart customer bots only when their code
   changed.

**Always verify after restart** (independent proof, not "active"): server `HEAD == origin`, service
`is-active`, and the running code carries the change (grep it). The OT-banking path is idempotent
(atomic claim) so a crash-redelivered duplicate can't double-bank — keep new balance-moving paths
idempotent too (flip status FIRST, before the write).

**All "system down" safeguards live in `docs/RESILIENCE.md`** — the single record (layers, status,
proof, known gaps, incident history). Update it whenever a safeguard is added or changed.

---

## Core Architectural Rules (READ BEFORE WRITING ANY CODE)

### 1. AI API Calls Only via shared/ai_client.py
All Claude API calls go through `shared/ai_client.py`. No other module imports the
`anthropic` SDK directly. Natural language order parsing stays rule-based (regex,
difflib).
**AI usage rules by system:**
- Retail/B2B bots: photo analysis, staff message monitoring, receipt clarity
- Hire bot intake: max 2 normal Haiku calls per applicant (intent classification + CV extraction, text only). Optional 3rd call (deflection_check) only after 3 CV deflections. No media/photo analysis before TEST_UNLOCKED. No expensive scoring before arrival. Every Haiku call = exactly one row in hiring_intake_ai_events.
- Hire bot scoring: Opus/Sonnet after TEST_UNLOCKED only
- All AI decisions during intake are logged to `hiring_intake_ai_events` for audit
When ANTHROPIC_API_KEY is empty the system falls back to manual-review mode automatically.

### 2. Always Build the Interface First
For every future AI-powered feature, create the function stub now with a placeholder return before wiring up the API. The stub is the contract — build around it first.

### 3. Confirmation Gate Is Mandatory
The bot must ALWAYS restate an interpreted order and ask for explicit confirmation
before saving anything to the database. No silent acceptance of natural language input.
Example flow:
- Customer types something → bot matches to menu items → bot rephrases clearly →
  customer presses [Confirm] or [Edit] → only then save to database.

### 4. Modular Files — Keep Each File Focused
No giant single files. Small, focused modules so Claude Code can load only what's
relevant in future sessions without hitting context limits.

### 6. Balance/State Changes — Apply the State-Integrity Laws (TRIPWIRE)
Writing or changing any code that moves a **balance or persistent state** (leave days, debt, OT bank,
points, a booking, a status, a claimed resource) → **read `docs/STATE_INTEGRITY_LAWS.md` FIRST.**
S1 reversible-by-construction (apply once + one clean inverse: deduct↔refund, claim↔release — never
reconstruct across job+read+write; prefer "commit + reverse on undo" over "defer the effect"); S2
idempotent/apply-once (flip status first); S3 atomic claim-or-reject for a shared resource (CAS, not
check-then-write); S4 the shown number = the true number; S5 a resource written by MULTIPLE features
(one slot, many writers) needs ONE resolver for all readers + supersede only your own rows (structural
marker) + symmetric picker exclusion + an undo on the same resource + /audit flags >1 live writer.
Universal (not project-specific). HIGH-RISK
money/leave/payroll work earns real before/after proof on a real row (staging DB) + a second-opinion pass.

### 5. Stateful Menus — Apply the Menu Patterns Law (TRIPWIRE)
Building or editing **any** menu, picker, wizard, or multi-step flow that stashes selection state
between taps (Telegram inline menus today; also any future web / Messenger / WhatsApp flow, or any UI
where two copies of a screen can share one state bag) → **read `docs/STATEFUL_MENU_PATTERNS.md`
FIRST** and apply its five laws. The trap: one shared state store backed by multiple live menu
instances → cross-contamination, plus the single-slot input-overwrite bug that needs only ONE menu.
The laws (button never trusts its screen · singleton the nav not the commitments · supersession
honesty · reset on entry · always a backstop, never a silent nothing) and the per-project status
(GM attendance: P2+P3 shipped, P1 pending; retail/b2b/hire menus un-audited) live there.

---

## Tech Stack
- **Language:** Python 3.11+
- **Telegram:** `python-telegram-bot` library
- **Database:** PostgreSQL on DigitalOcean (managed) — `psycopg2`, connection via `DATABASE_URL` in secrets.py
- **Fuzzy Matching:** `difflib` (standard library)
- **Logging:** `RotatingFileHandler` — 5MB cap, 3 backups. Unmatched orders log to `logs/unmatched.log`

---

## Repo Structure
*Need the file layout? → `docs/REPO_STRUCTURE.md` (or just read the filesystem).*

---

## Build Phases

### Retail Bot — Complete
Phases 1–6 done: foundation, menu + ordering, production summaries, photo flow, stock sheets, Claude API layer (OCR, photo analysis, staff monitoring, fallback mode).

---

## New Machine Setup

Just say: **pull**

Claude Code clones the repo, syncs all secrets and SSH keys, and runs bootstrap automatically.
You will be asked for your GitHub PAT (`repo` scope) once — everything else is handled.

PAT creation: https://github.com/settings/tokens
Secrets live in: `github.com/aaaeeeaaarrr/twbshop-secrets` (private)
Claude Code permissions sync automatically via `.claude/settings.json` in this repo.

---

## Key Decisions (Do Not Revisit Without Good Reason)
- **PostgreSQL on DigitalOcean** — migrated from SQLite. All data lives in the managed DO database. No local .db file.
- **Free-first architecture** — API features are additions, not the foundation.
  The bot must work fully without any API calls before any API calls are added.
- **No silent AI guessing** — every ambiguous input goes to a human confirmation step.
  The confirmation gate is not optional, it is the safety mechanism.
- **Telegram only** — no web dashboard, no separate app. Staff and customers
  already use Telegram. Keep the surface area small.

---

## GM Subsystems — status index
*One-line status; full detail → `docs/SUBSYSTEMS.md` (+ the per-topic docs named there).*
- **REPORT finance tracking (GM bot):** LIVE.
- **Supervisors/Management — lateness·AL·tagging:** mostly BUILT; group ladder SILENCED (moved to private-DM).
- **Delivery System (WOC):** SHELVED.
- **Staff Registry · Ex-staff offboarding · Paperless /stock:** BUILT (stock overhaul + 143-item CSV import PENDING).
- **Private-DM Attendance Overhaul:** **LIVE since 2026-06-16** (`attendance_live`=true, test mode off) → `docs/ATTENDANCE_SYSTEM_DETAILED.md` + `..._MAP.md` + `..._TEST_MODE.md`.
- **STRATEGIC — POS convergence:** keep our Postgres source-of-truth; AppSheet is a throwaway stock front-end.
- **GM Backlog & Roadmap:** → `docs/ROADMAP.md` (reference, not an auto-run list).
- **Operations Intelligence System:** mostly BUILT (Phase 3 — listener + import + AI tiers + hire bot).

---

## Current Status
> Update this at the end of every session. The only source of truth for what's next. Old session logs (19–43) → docs/HISTORY.md.

**Last updated:** 2026-06-19 (session 45 — **lane_guard v4 contention-scoped warn + shared-file rule + backlog pruned**).
**▶ LANE_GUARD v4 — CONTENTION-SCOPED SHARED-WARN (hub, tooling; INERT — nothing live, lanes `pull` to get it):** the blanket "warn on every shared edit" noise is GONE. A lone shared edit is now **silent**; the guard WARNs only when **another worktree has that exact file uncommitted right now** (same-machine live race), naming the lane → "let it commit + push, then `pull` before you edit". WARN not auto-block (a lane abandoning a dirty file must never deadlock another). New pure helpers `_sibling_contention` (git) + `_gate_shared` (decision); `tests/test_lane_guard.py` **13 pass** (pure only — never `main()`, which would pollute the event sink); real-path proven on all 4 worktrees (clean→silent · gm-dirty→names `gm` · cleanup→silent). **Shared-file RULE added to playbook:** pull-before-touch · commit-on-its-own · push-at-a-boundary (pulling-before-shared, not faster commits, is what stops divergence; `push`≠commit so per-edit pushing is waste). **Backlog PRUNED (prevention-at-source redundancy sweep):** DROP sparse-checkout (guard-block + valued cross-lane reads make it counterproductive); DEFER server-side commit-scope CI (guard prevents + audit detects). Files: `scripts/lane_guard.py` · `docs/MULTI_LANE_PLAYBOOK.md` §3/§4/§8/§9 · `tests/test_lane_guard.py`. **▶ NEXT (paused, resume after this): trim this CLAUDE.md** (move sessions 32–43 → `docs/HISTORY.md`, keep latest + open loops + rules).
**(prev, session 44)** INTEGRATOR CROSS-LANE VERIFY: full suite 738✓ on merged `main`, GM↔stock seam clean, drift guard added.
**▶ INTEGRATOR VERIFY (hub on `main` `3937b0b`) — the checks no single lane can do (they're blind to each other):** **full suite 738 passed / 2 skipped / 0 failed on merged main** (closes the "merged-main not suite-verified" gap). **GM↔stock handover CLEAN:** stock builds on the B1 shared tables (`acc_items`/`stock_movements`, no fork); `gm_bot/stock.py` ≡ `stock/order_brain.py` (AST-identical, faithful port); **no lane wrote another lane's code** (guard held). Added **`tests/test_stock_brain_no_drift.py`** — the two brain copies must stay logic-identical until the GM cutover (drift → red suite; auto-skips post-cutover). **⚠ HYGIENE FINDING:** lanes have been editing the tracked Current Status during their pushes (the `(prev)` line below included) — against the multi-lane rule (hub owns Current Status; lanes → `CLAUDE.local.md`). No conflict yet (sequential pushes) but latent → fix = lanes skip the Current-Status step (+ optional lane_guard `CLAUDE.md` hard-block).
**▶ LANES MACHINERY HARDENED + CAPTURED (hub, session 44 cont):** **(1)** `lane_guard` now **HARD-BLOCKS `CLAUDE.md`** in any lane (HUB_ONLY → lanes use `CLAUDE.local.md`; `.lane_ack` still overrides). **(2)** NEW **`scripts/integration_audit.py`** — the integrator's cross-lane sweep (map integrity = every file owned/shared · no cross-lane commit · optional `--suite`); **map COMPLETED** (`parallel_lanes.json` now covers all 29 prev-unowned root scripts/dirs → audit CLEAN). **(3)** dashboard gained **`/audit`** (runs it on demand). **(4)** ▶▶ **`docs/MULTI_LANE_PLAYBOOK.md`** — the full PORTABLE method (model · the whole toolkit · workflow · 8 safety layers · the self-review + integration-audit rituals · how to set this up in a NEW project · the up-our-game backlog · hard-won lessons). **Keep it updated as we improve the setup.** Monitor cmds now: `/board /health /issues /crossings /audit`.
**(prev, session 44 — accountant lane)** ACCOUNTANT P1.5: "Received Yet?" supplier-candidate forward flow + symmetric duplicate guard. BUILT + checkpointed to main (`8059f03`); INERT — the accountant bot is NOT a live server service, nothing deployed; staging only.
**▶▶ RESUME (accountant lane, session 44):** the bridge between P1 capture and the HIGH-RISK P2 money matcher — **moves no money** (creates *candidate* rows, promotes to a normal `captured` draft; the paid-flip + lump matcher stay untouched P2 stubs).
• **Flow:** a supplier posts a photo in their **linked** group → bot stays **silent there** → posts a **candidate card** to the Expense group headed `📨 From <vendor> · <group>` (routing verifiable) → owner forks: **🆕 New&received** → 1 lazy Sonnet read → **look-alike guard** (same vendor+amount ≤7d → "Same as #N / New?") → **claim-first promote** to a numbered receipt (atomic `open→promoting`, so a double-tap can't create two #s) → living receipt card · **🔗 Already-logged** → pick from the vendor's recent receipts → link to #N · **📦 Not-yet** → park `expected` · **✕ Ignore**.
• **Symmetric dup guard:** the DIRECT Expense-group capture now ALSO flags a same-vendor+amount-within-7d receipt as `⚠ possible duplicate of #N` (informational; new `acc_receipts.dup_suspect_of`). Candidate-promoted rows are NOT re-flagged (owner already chose "New").
• **Files:** `accountant/{db,capture,bot}.py` + `tests/test_accountant_candidates.py` (+`tests/test_accountant_capture.py`). Lane scratch in `CLAUDE.local.md` (gitignored). Design marker in `docs/REPORT_SYSTEM_DESIGN.md §E3`.
• **⚠ SCHEMA ADDITIONS (idempotent, self-applied by `init_accounting_db()` at bot startup — no manual migration):** new table **`acc_receipt_candidates`** + column **`acc_receipts.dup_suspect_of`**. Applied on **staging** when the bot/tests run; **NOT on prod** (accountant bot is not deployed).
• **PROOF (DB now DONE on staging — self-review session 44):** **35/35 accountant tests PASS on staging** (24.5s, real Postgres) incl. all candidate DB-lifecycle (atomic claim · sha-dedup · look-alike window/exclude · `dup_suspect_of` flag · link · unclaim) + P1 regressions. **Independent schema read** confirms `acc_receipt_candidates` (17 cols) + `acc_receipts.dup_suspect_of` + indexes (`uq_acc_cand_sha`, `idx_acc_cand_status`); **0 rows left** (fixtures clean — no staging pollution). Static: 27 db imports + 9 `capture.*` all resolve · SQL params balanced · claim-first ordering verified · P2 stubs (`open_receipts_for_vendor`/`record_payment_and_match`) uncalled. **▶ Gotcha:** the **lane worktree lacks the gitignored `secrets.py`** (`make_lane` doesn't copy it) so DB tests SKIP there — **run them from the main worktree**: `cd C:/Users/Papa/TWBshop && python -m pytest tests/test_accountant_candidates.py tests/test_accountant_capture.py -q`. **STILL UNPROVEN (owner live-walk only):** the Telegram/bot orchestration + OCR (need a live token + a real image).
**▶ NEXT:** (1) **live-walk** on staging (the one unproven layer): `python scripts/run_accountant_local.py`, `/vendor link <name>` the TEST Supplier group `-5406470751`, post a photo there → candidate card appears in Expenses TWB `-5417163768` → walk the four forks + promote. (2) Then **P2 (HEART, HIGH-RISK money)** — owner→bot→supplier slip relay + wrong-amount txn-ref ladder + subset-sum/FIFO lump matcher + anti-double-pay paid-flips; per-step owner approval, no live money until each step signs off.

**▶ STOCK LANE (session 44) — C2 FOUNDATION BUILT + consolidated to main; INERT (no service runs it, nothing deployed). Full suite 721/2-skip.** The headless stock worker (no chat bot — staff use the GM gateway button → AppSheet; Postgres = source of truth).
• **Catalog → shared `acc_items`** (`stock/catalog{,_data}.py`): 50 items migrated from GM's `_STOCK_SEED`; `run_stock.py --seed` (idempotent); read-model `overview/low_stock/reorder_list` (on-hand via the ONE `stock_movements` resolver, is_test-scoped).
• **Count model** (`stock/db.py` `stock_count_events`): one count/item/day; `reconciled` flag; `sync.apply_count` writes the count event + reconciling movement; `sync.reconcile_counts` turns AppSheet-direct writes into ledger movements (idempotent) — run every worker tick.
• **Order brain** ported to `stock/order_brain.py` (GM's `gm_bot/stock.py` removed at the integrator cutover — coordinate w/ gm lane).
• **GM C3 seam** (shipped by gm lane: `gm_bot/stock_gateway.py`): staff button gated on **`STOCK_APPSHEET_URL`** (env/config) — set once → button lights up + worker reconciles AppSheet counts.
• **⚠ SCHEMA (idempotent, self-applied at worker start):** `acc_items`+`stock_movements` (B1) + `stock_count_events`. Staging only; **prod migration at go-live.**
**▶ NEXT (owner gate — C2 first unknown):** create the AppSheet app over the DO Postgres per **`docs/STOCK_APPSHEET_SETUP.md`** (security-first: AppSheet gets ONLY a least-privilege role on `acc_items`+`stock_count_events`, NEVER payroll). Choose **direct-bind** (scoped role) vs **API** (DB stays private → wire `AppSheetClient`). Then: migrate GM stock code out (integrator cutover) · D2 accountant read-only cross-check.

**▶ STANDING OPEN LOOPS — the live threads (detail for completed work → `docs/HISTORY.md`):**
1. **Multi-lane operation (current focus)** — hub (`twbshop`/`main`) + 3 lane worktrees (`twbshop-accountant`/`-gm`/`-stock`). Portable method · toolkit · build sequence (Phases A–F) · lane layout/recreate → **`docs/MULTI_LANE_PLAYBOOK.md`** + `docs/PARALLEL_LANES.md`. Monitor (`scripts/monitor_bot.py`, owner-only): `/board /health /issues /crossings /audit`.
2. **Accountant bot** — P1.5 done (above); **NEXT = live-walk on staging → then P2 (HIGH-RISK money matcher)**. INERT (no server service imports it; nothing deployed). Design → `docs/REPORT_SYSTEM_DESIGN.md`. Key IDs: Expense group `-5417163768` · TEST Supplier `-5406470751`.
3. **Stock lane** — C2 foundation done (above); **NEXT (owner gate) = create the AppSheet app** → `docs/STOCK_APPSHEET_SETUP.md`. INERT. Then the GM↔stock cutover (remove `gm_bot/stock.py`; drift-guarded by `tests/test_stock_brain_no_drift.py` until then).
4. **Attendance / AL / OT / schedule system — LIVE since 2026-06-16 11:08 PP** (`attendance_live`=true, test mode OFF): real staff check in by live-location; AL/OT/no-show/points/schedule-changes all active on real data. **HIGH-RISK live path (payroll-adjacent)** — any change: investigate read-only on prod first, prove on staging, deploy-by-TAG in a quiet window + verify (never a casual restart). Live design → `docs/ATTENDANCE_SYSTEM_DETAILED.md` + `..._MAP.md` + `..._TEST_MODE.md`; build blow-by-blow (sessions 31–42) → `docs/HISTORY.md`; open data ops → `docs/ACTIONS_LEDGER.md`.
**At session start also read `docs/ACTIONS_LEDGER.md`** (open real-data instructions; Parked items are rare/behind-go-live).

**✅ RESOLVED (2026-06-19, was the ⏰ 2026-06-08 dated checkpoint) — dev can no longer silently hit prod.**
Superseded by the **Phase-0 fail-closed switch** (not the originally-planned "flip dev default"): `shared/
database.py::active_database_url()` REQUIRES `TWBSHOP_ENV` set explicitly to `prod`/`staging` — unset/unknown
**RAISES** (no silent prod fallback). Verified LIVE 2026-06-19: all 5 server units pinned `TWBSHOP_ENV=prod`
(and the running gm process's `/proc/PID/environ` carries it) · `tests/conftest.py` forces `staging` · staging
DB `twbshop_staging` exists with a distinct `STAGING_DATABASE_URL`. **Accepted residual:** the prod URL is
still physically in dev `secrets.py` (a human could deliberately set `TWBSHOP_ENV=prod`) — the *accidental/
silent* risk is closed; the deliberate path is by design. (Separate ledger item: fold `hire_bot/*` + `run_*.py`
raw connections through `raw_connect()` — not on the payroll path.)

**Phase:** Retail complete · B2B Phases 1+2 · GM Manager live · Ops listener live · Hiring intake+quiz+assessment built. **Attendance LIVE (since 2026-06-16).**

**Known issues:** None
**Notes:**
- Retail bot: `python run_bot.py` — systemd: `twbshop-retail`
- B2B bot: `python run_b2b_bot.py` — systemd: `twbshop-b2b`
- Listener: `python run_listener.py` — systemd: `twbshop-listener`
- GM bot: `python run_gm_bot.py` — systemd: `twbshop-gm`
  Groups the GM bot is IN: Stock Checks (-1003952029131), Supervisors, Management, COMMS & Transfers, TWB REPORT (-5136886404)
  Groups it monitors but does NOT post to (except TWB REPORT receipt checks): all of the above
- Price list fetcher: `python run_fetch_pricelists.py` — run manually to refresh supplier files
- Set ANTHROPIC_API_KEY in config.py to enable AI features (retail bot only for now)
- B2B customers: 24+ active customer groups identified in ops_messages DB; none have the bot yet — all ordering manually
- Bakong/KHQR registration pending — need passport (on other PC); check ABA app merchant QR first
- Personal project created at `C:\Users\Papa\Personal` — secretary bot command centre (separate repo)

---

---

## B2B Orders Bot — b2b_bot/
*Working on the B2B wholesale bot? Full design rules, repo structure, and build phases → `docs/B2B.md`.*
