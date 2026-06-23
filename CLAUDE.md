# Bakery Automation System — Project Rules & Status

> ## ▶▶ PROJECT NORTH STAR — the REAL objective (owner, 2026-06-22)
> This is **not** ultimately "a Telegram bakery bot." The end goal is a **portable, multi-tenant TOTAL
> business-management PLATFORM sold/leased as a service** — attendance + POS + stock + back-office +
> supervisory/HR + more — delivered via a **stupid-proof self-serve wizard** ("Telegram? web? app?
> several?", paste token, listener details…), **channel-agnostic** (the brain holds no Telegram/web/app
> code; channels are adapters), **config-driven per tenant**, **integration-friendly** (tap a customer's
> existing POS, or be the POS; stock via AppSheet today, maybe our cloud later), sold as **packages/
> bundles/layers** for different market segments. **TWBshop is CUSTOMER #1** — currently a live Telegram
> system; we'll onboard it onto the platform via **shadow-run** (build fresh, run parallel to live, prove
> it, cut over with instant revert). **Reuse TWB's hard-won domain RULES; rebuild the single-tenant,
> Telegram-fused PLUMBING clean.** Every architectural decision — even small ones — must keep this open.
> **Full design + the governing principles → `docs/PLATFORM_VISION.md`; the shift-model worked example →
> `docs/SHIFT_MODEL_DESIGN.md`.** (Current build is still TWB-the-bot; the platform is built deliberately,
> MVP-slice first, no fire — TWB stays stable meanwhile.)

> **🗺️ START HERE — open `MAP.md` for ANY task** (Layer 1: entry files · law-doc · `docs/HISTORY.md`
> section · ⚠ gotcha per area). **Need any other file / "where's function X"? → `MAP_INDEX.md`** (Layer 2:
> auto-generated complete inventory). **Before claiming anything exists / works / is missing / is a gap,
> check the records the map points to and cite them — or say "let me check" and check.** An unverified
> gap-claim is a violation, same as a false "done" (2026-06-19). On any file add/move/rename: run
> `python scripts/gen_map_index.py` (Layer 2 freshness is build-enforced) and fix any Layer-1 entry you
> changed — guards: `tests/test_map_integrity.py` + `tests/test_map_index_fresh.py`.

---

## ▶▶ PRODUCT SECURITY & IP PROTECTION — LAW (owner, 2026-06-23) — think like a serious company, always
We are building a **product to sell on the market**, not just an internal tool. Treat security, IP, and
anti-theft as **first-class in every design decision** — bake it in, never bolt it on. This is a standing
law, applied pervasively (like the Real-Path Standard), and it AUTO-BEDROCKS anything that exposes data,
logic, or a network surface.

1. **THE BRAIN STAYS SERVER-SIDE — never shippable, never decompilable.** The rules / engine / config /
   algorithms live and run on OUR servers only. Channels (web page, app, Telegram) are THIN clients that
   receive rendered views + scoped API responses — NEVER the engine, the full ruleset, the source, or the
   "why" behind a decision. SaaS is our moat: a customer/competitor never gets code they can reverse-engineer.
   (This is also WHY the platform is channel-agnostic — the value is the server brain, not the channel.)
2. **CLIENT GETS ONLY WHAT THAT USER IS ENTITLED TO.** No internal IDs, no other tenant's data, no secrets,
   no implementation detail, no algorithm, in any page / API response / log / error a user can see. A
   customer sees THEIR OWN config knobs and THEIR OWN data — never how it's computed beyond the knob, never
   anyone else's anything.
3. **AUTH + TENANT ISOLATION ON EVERY SERVER EXIT.** Every endpoint that leaves the server enforces authn +
   authz + `org_id` scoping SERVER-SIDE (never trust the client to say who it is or which org). Default
   posture for anything not yet behind real auth: **bind to localhost, reach it via SSH tunnel** (the SSH
   key is the auth) — nothing public until authn + HTTPS + rate-limit + input-validation exist.
4. **SECRETS & SURFACE.** Secrets in `secrets.py` only (existing law) — extended: no token/secret/internal
   id in any client payload, page, log, or error. Any network-exposed surface = rate-limited, input-validated,
   HTTPS, least-privilege DB access, abuse-monitored.
5. **AUDITABILITY.** Who-changed-what-when on config and money/data — for customer trust, forensics, and the
   multi-tenant story. Build the audit trail as we build the feature, not after.
6. **PROTECT THE REPO.** Private repos (existing) + server-only deploy + minimize what any client can infer.
   Don't leak the ruleset through verbose client payloads or error messages.

*(Full detail will live in a dedicated product-security doc when first needed. A concise version can be
mirrored to the global rules on request via `python bootstrap.py --push-global`.)*

---

## ▶ BONUSES & FINDINGS — always capture (standing practice, owner 2026-06-23)
As we build, ALWAYS append the **bonuses** (unexpected wins · sellable angles · leverage) and **findings**
(discoveries · gotchas · decisions) to **`docs/BONUSES_AND_FINDINGS.md`** — capture EVERYTHING, the owner
shaves/improves later (don't self-censor; a half-idea logged beats a lost one). One line + a tag per item.
It's a running ledger like `docs/ACTIONS_LEDGER.md`. Surface the new ones in the reply too, but the doc is
the durable home.

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
*Need the file layout / "where's function X"? → `MAP_INDEX.md` (auto-generated, never stale) + `MAP.md` (the curated router). Or just read the filesystem.*

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
> Update this at the end of every session. The only source of truth for what's next. Old session logs (19–46) → docs/HISTORY.md.

**Last updated:** 2026-06-23 (session 53 — **CONFIG-DRIVEN WIZARD BUILD + an AUTONOMOUS BACKLOG RUN (owner away)**).
**▶ AUTONOMOUS RUN (Jun 23, owner away — full log `docs/AUTONOMOUS_RUN_2026-06-23.md`).** Worked the backlog SAFELY (zero live-bot disruption — only the isolated `twbshop-wizard` restarted): ① shadow check-in residual RESOLVED → **check-in vertical now reads READY** (stale pre-port mismatches reconciled; flip is owner's call, NOT done) · ② **wizard admin cut-over dashboard** (per-vertical shadow agreement) deployed · ③ **accountant landmines F5/F6 FIXED** (inert: partial-UNIQUE vendor name + atomic propose/merge/undo; 953p/2s) · ④ **company-name shortlist** for review (`docs/COMPANY_NAME_IDEAS.md`) · ⑤ deferred owner-walks **de-risked** (automated coverage verified) · ⑥ **B2B F2/F3/F4 = ready plan** `docs/B2B_LANDMINE_FIX_PLAN.md` (HIGH-RISK money on the real ledger → execute WITH owner at re-enable; NOT done autonomously; B2B stays disabled). DEFERRED on purpose (documented): 3b sparse shadow hooks + settle payback-slot port (need a gm restart for sparse gain), the live cut-over, wizard W2.5/W3. Every bright line (live money, cut-over, B2B re-enable, the name) left for owner review.
**▶ WIZARD EXPANSION (Jun 23, owner feedback — tag `session-53e-wizard-expansion-20260623` = `2dd026d`; deployed to `twbshop-wizard`; bots untouched gm NR=0).** Config + UI + secret-store only, ZERO live behavior change (DEFAULTS still = TWB's rules). **4-state model** (added **LIVE_FIXED** — "live today, fixed rules; config drives at cut-over") fixes the OT/swap/sick "PLANNED" confusion. Attendance config now covers EVERY mechanism (sick details · schedule/swap/day-off · **staff rules** · full approvals ladder per request type) + **options beyond TWB** (OT disposition bank|convert_al|pay_money|expire · rate multiplier · AL accrual models · rest rules · consecutive-day/weekly-hour limits). **Connections/onboarding** screen (Telegram bot-token + listener session + owner chat + web/app + integration keys) with tokens as SECRETS → encrypted-pending store `core_org_secrets` (NEVER in config, NEVER shown — only set ✓/not set + write-only input). Customer view editable = safe SHADOW/PLANNED/LIVE_FIXED (LIVE_FIXED = a saved cut-over preference; only LIVE/AL locked). Catalog enriched (rostering·CRM·payments). ⚠ encrypt `core_org_secrets` at rest before any public exposure (W3). Tags through `session-53f`.
**▶ ONBOARDING DESIGN + CONFIG (Jun 23, owner brainstorm — tag `session-53g-onboarding-20260623` = `844370e`; deployed wizard; bots untouched).** Owner asked how a CUSTOMER (vs TWB's months of manual setup) gets onboarded. Deep design → `docs/ONBOARDING_DESIGN.md`: principle **DISCOVER-don't-dictate / CONFIRM-don't-type**; **bot-IN-groups as the listener (no user-session — the big simplification)**; auto-discover groups+staff → **confirm 1-by-1**; `/start` deep-link + Google OAuth for silent staff (approve-a-link, never type an id); **guided BotFather + Bot-API auto-config** (Telegram won't auto-create bots); **split-shift + overnight via the shift-id model** (owner validated); templates · bulk import · per-customer SHADOW as a sellable "try-risk-free"; consent; onboarding state-machine. BUILT: `onboarding` config section + `schedule.split_shift_allowed`/`overnight_shifts` + a wizard **Setup & staff** screen (config+UI only, nothing live). NEXT (bigger): the live discover-confirm flow + guided BotFather + staff CRUD. ⏸ owner said KEEP CHECK-IN IN SHADOW a few more days — do NOT cut over (READY = bar met, not "must flip").
**▶ EXPERTISE + BOT-APPROVER + DISCOVER-CONFIRM FLOW (Jun 23, owner brainstorm — tag `session-53h-expertise-onboarding-flow-20260623` = `8caf241`; deployed wizard; bots untouched gm NR=0; 956p/2s).** Config + UI + INERT core only — nothing live. **Expertise/coverage:** `categories.attendance.expertise` (enabled · roles{skill:min_required} · coverage_overrides[day/hour]) + expertise per staff; the wizard shows the toggle + full explanation (the per-skill/override editor = next, with the staff CRUD). **Bot-as-approver:** the Approvals "by" can be **the bot**, with a `bot_rule` whose every if-condition is spelled out for customers (Keep-coverage / Within-quota / Always / Easy-ones-only). **Discover-confirm flow core** (`core/onboarding_flow.py` + `core_staff` + `core_onboarding_candidates`): the bot stages people it sees → owner confirms each into a staff record (name·role·senior·**expertises**·**shift_windows** for split/overnight·telegram/google) — idempotent, org-scoped, acts on nothing live (TWB keeps `staff_registry`). 3 flow tests. Full design → `docs/ONBOARDING_DESIGN.md` (+ §B1/B2 expertise & bot-approver).
**▶ STAFF + EXPERTISE EDITORS (tag `session-53i-staff-expertise-editors-20260623` = `43cdfeb`; deployed wizard; bots untouched; 961p/2s).** Wizard `/staff` (the platform roster: add/remove staff with name·call·role·senior·comma-skills·hours incl. **overnight 21:00→06:00 = one window** + **split = a 2nd window**) + `/expertise` (add/remove skills with a min-at-all-times + add/remove **day/hour coverage overrides**). Writes `core_staff` + `categories.attendance.expertise` (roles now a list); server-validated; nav-linked. 5 editor tests. Config/UI only — nothing live.
**▶ TELEGRAM DISCOVER-CONFIRM ADAPTER (HEAD includes it; INERT — no live bot wires it; 5 mock tests).** `adapters/telegram_onboarding.py` (in `adapters/`, NOT core — core stays channel-free): a staff-group message **stager** (auto-records who posts) + `/onboard` (lists discovered people) + inline **confirm/skip** that calls the core flow + advances — one tap, no typing. `register(app, org, staff_chat_id)` attaches to a tenant bot. `run_onboard_demo.py` to try it on a throwaway BotFather bot (staging; org='demo'; never TWB live). **TO TRY LIVE:** owner makes a test bot (BotFather, privacy off), gives the token + group id → `run_onboard_demo.py`.
**▶ ONBOARDING WIZARD — FULL CHAIN BUILT (Jun 23, tags `session-53i/53j` + HEAD; deployed wizard; bots untouched).** A near-complete self-serve onboarding, all config/UI + inert adapter (nothing live): **`/setup`** checklist (bot · staff-group · staff · rules, "N of 4 done") · **`/bot`** guided BotFather + verify/auto-configure (`adapters/telegram_provision.py`) · **`/groups`** auto-discovered groups + tag the staff group (`core_org_groups`, single-occupancy roles; `adapters/telegram_onboarding` records groups + stages from the staff-mapped one) · **`/staff`** add/**edit**/remove (name·role·senior·skills·hours incl. overnight+split) + discover-confirm fills it · **`/expertise`** skills+min+overrides. So a new tenant: connect bot → tag staff group → bot finds staff → confirm 1-by-1 → tweak. ~30 onboarding tests (flow, group single-occupancy, editors, provision-mock, adapter-mock). Design → `docs/ONBOARDING_DESIGN.md`.
**▶ ONBOARDING POLISH + 2ND DOMAIN (Jun 23, deployed wizard; bots untouched).** ① **Templates** (`wizard/templates.py` — bakery/cafe/retail one-click presets → `/templates`) · ② **staff consent + `/start` self-link** (silent staff tap the bot/link → staged + consent Yes/No → carried to the staff record; `adapters/telegram_onboarding` `cmd_start`+consent callback; `core_onboarding_candidates.consent`) · ③ **bulk import** (paste "Name, role, HH:MM-HH:MM, skills" on `/staff`) · ④ **Accountant domain config** — `categories.accountant` now models receipt-read/vendors/payables/food-allowance (INERT; the platform's 2nd domain, shown in admin + a customer Accountant section). So 3 staff-entry paths (discover-confirm·manual·bulk) + the wizard is multi-domain. **⚠ KEY FINDING: the whole Telegram onboarding is BUILT but UNVALIDATED end-to-end — no real bot has run it (mock-tested only). The highest-leverage next is to VALIDATE on a real test bot (owner provides a BotFather token → `run_onboard_demo.py`) before building more on it.**
**▶ SECURITY / W3 FOUNDATIONS (Jun 23, deployed wizard; bots untouched).** Did the safe security items: ① **`core_org_secrets` ENCRYPTED at rest** (Fernet when `ORG_SECRET_KEY` set; plaintext+warning till then; fail-safe) — the flagged secret-store gate CLOSED (owner: set `ORG_SECRET_KEY` in secrets.py to activate). ② **basic auth/logins** (`core_org_users` hashed pbkdf2; `WIZARD_AUTH=1` → `/login`+session; **OFF by default** so the localhost tunnel is unchanged; no-users→no-lockout, seed via `core.db.create_user`). **⚠ FINDING: the repo `secrets.py` SHADOWS the stdlib `secrets` module** → broke werkzeug password-hashing (used hashlib pbkdf2 instead). Could bite other libs that `import secrets`; renaming is a big change (global rule mandates `secrets.py`) → worked around. **Before PUBLIC exposure (W3): set `ORG_SECRET_KEY`, add CSRF + login rate-limit + HTTPS.** **STILL the KEY thing:** VALIDATE the Telegram onboarding on a real bot (owner token).
**▶ WEB CHECK-IN/OUT CHANNEL (Jun 23, deployed wizard; bots untouched).** The "some want browser, not Telegram" channel: a staffer opens their private `/checkin/<token>` link → a one-tap **Check IN / Check OUT** page (JS geolocation) → `core.attendance.check_in/out` (verdict via the tenant verdict config; worked-minutes). `core_staff.checkin_token` (unique) + `ensure_checkin_token`/`staff_by_checkin_token`; a "link" button per staff on `/staff`; `/checkin`+`/checkout` are auth-exempt (the token IS the staffer's identity). **Records to the PLATFORM (`core` attendance_events), NEVER TWB's live attendance.** Proves channel-agnostic OPERATION (not just onboarding) — same brain as Telegram + the replay. 4 tests. ⚠ reachable only via the localhost tunnel until public hosting + W3 (auth/CSRF/HTTPS). **The platform now has Telegram + Web channels for both onboarding AND daily check-in.**
**▶ 5 CORE DOMAINS + BONUSES/FINDINGS LEDGER (Jun 23, deployed wizard; bots untouched).** The wizard now configures **5 core domains** — attendance (live-mirrored) + **accountant · stock · POS · HR/payroll** (modelled, INERT; each = a `categories.*` block + schema group + a customer section, the cheap recipe). Upsell de-duped. **▶ STANDING PRACTICE (owner): always capture bonuses + findings to `docs/BONUSES_AND_FINDINGS.md`** (the running ledger; pinned in the "▶ BONUSES & FINDINGS" rule near the top) — now holds this whole session's wins/gotchas/decisions.
**▶ BUILD-BATCH (Jun 23, "build build build" — deployed wizard; bots untouched).** Six safe features, all config/UI/read-only, nothing live: ① **what-if preview** (`core/whatif.py` — "set grace to 9 → N recent check-ins reclassify"; read-only over the platform's own events; `/whatif`) · ② **config-change audit log** (`core_config_audit`; auditability law #5; `/audit`; secrets log the act not the value) · ③ **FIX: partial-form bool reset** (a checkbox sends nothing when off → a partial Apply mass-reset bools; fixed with a hidden `_scope` field — the audit log surfaced it; **applies to any HTML checkbox form incl. retail/b2b/hire menus → PARKED for owner, HIGH-RISK live**) · ④ **staff "my recent check-ins"** on the web page · ⑤ **admin dashboard** (tool nav + at-a-glance) · ⑥ **config export/import** (portable tenant setup; import reuses Apply's whitelist) + a **platform e2e smoke test** (org→staff→config→web check-in→history→what-if→export connects). All in `docs/BONUSES_AND_FINDINGS.md`.
**▶ SELF-SERVE TOOLS + AUDIT + CEILING (Jun 23, deployed wizard; bots untouched).** ⑦ **config health-check** (`core/health.py` — flags likely setup mistakes: expertise on/no skills · OT bank/0 cap · 0 approvers · dup names · no staff group · …; `/health` + a dashboard count) · ⑧ **go-live readiness** (`/setup` = N-of-5, 5th = clear warnings, "🎉 Ready" only when all green) · ⑨ **readable export diff** (default→your-value) · ⑩ **operator quickstart** (`docs/WIZARD_QUICKSTART.md`). **Live-bot menu audit (read-only): the checkbox bool-reset class is ABSENT in retail/b2b/hire** (retail no settings menus · b2b COALESCE-guarded · hire `_update(**fields)` only-passed) → the wizard fix needs no porting. `docs/PLATFORM_COVERAGE.md` refreshed with the platform build-state. **▶ CEILING REACHED — the safe-autonomous build is comprehensive (config engine · wizard · 5 domains · Telegram+web onboarding & check-in · security · what-if/audit/health/export · e2e), TWB live UNTOUCHED throughout. The remaining high-value work all NEEDS the owner: VALIDATE on a real bot (`run_onboard_demo.py` + a BotFather token) · cut over check-in (READY) · the sick/leave per-channel FLOW (HIGH-RISK money) · public hardening (W3: `ORG_SECRET_KEY`+CSRF+HTTPS) · decisions (name/B2B). Everything captured → `docs/BONUSES_AND_FINDINGS.md`.**
**▶▶ WIZARD / CONFIG-DRIVEN PLATFORM — owner direction (Jun 23): every edit from now is a config setting + `core` reads it (no per-tenant code); the wizard produces the config; TWB = tenant #1 (its rules → its config); the shadow validates `core(config=TWB)` vs live across the FULL menu. Deep brainstorm (14 categories, sub-tables, AI-Power tiers, channels, integrations, cross-category unlocks, bonuses incl. shadow-run-as-a-sellable-feature) → `docs/WIZARD_DESIGN.md`. LINEUP: 1✅ config spine · 2✅ AL ladder · 3⏳ wire full shadow (3a✅ settle/money path) · 4⏳ wizard UI (W1✅ viewer · W2✅ customer editor — explanations + Apply/Cancel draft, admin/customer views) · 5 migrate other live domains (accountant/b2b/retail/hire/pos) as the shadow beats live. **SECURITY now a LAW (▶▶ PRODUCT SECURITY & IP) — brain server-side, thin clients, auth+tenant-isolation, localhost/tunnel until authed.**
**▶ STEP 1 — CONFIG SPINE (commit `9e5a98f`, inert/no-deploy).** `core/tenant_config.py` = the nested category model (attendance fully specced — verdict/ot/leave/points-catalogue/the complete APPROVALS table; other domains stubbed); deep-merge get/set + accessors (`verdict_cfg`/`points_catalogue`/`approval_rule`); `core.channel`/`points`/`onboarding` read it. DEFAULTS = TWB's rules → zero behaviour change. Complete schema written ONCE → no double-edit (owner's sequencing point).
**▶ STEP 2 — AL RE-PING LADDER DEPLOYED (tag `session-52h-al-reping-ladder-20260623` = `c765242`; gm active NR=0; 936p/2s).** The FIRST config-driven feature, fixing the Heng-stuck class. `core/approvals.py` reping_decision (pure rule, parity-tested) + `tenant_config.approval_rule('twb','al')` config (re-ping every 6h ×4 · delete-prior · skip responders · escalate to owner after #4 · auto-expire past-window). `gm_bot/_al_reping_job` (every 30min) executes it; `al_pings` table persists message-ids (delete-prior survives restarts); auto-logged (`gm_events`+`[AL-LADDER]`). **Heng's stuck #434 (pending 4 days) is being AUTO-EXPIRED by the new ladder on its first run (window passed)** — the fix resolving the real case itself. **(VERIFIED: #434 status=expired, gm_events al_expired, `[AL-LADDER]` log.)**
**▶ STEP 3a — SETTLE SHADOW WIRED LIVE (tag `session-53a-settle-shadow-20260623` = `d7b3662`; gm active NR=0; 942p/2s).** Extends the shadow beyond check-in to the MONEY path (the cut-over gate). At every real redefine checkout (`_settle_redefined_shift`, isolated + gated by shadow_run=ON), core's settle math is compared to live's → `shadow_comparisons(kind='settle')`. `core/shadow_hook.shadow_settle` runs `core.settle` UNCAPPED (= live `gm_bot.ot.settle_shift`, drift-guarded) on the same inputs, compares worked/ot_banked/pb_cleared; a **payback-slot**'s ext-worked window isn't modeled in core yet → recorded *informational* (the next port, #5). `build_digest` is now **per-action-type** (check-in · settle · …), check-in still the readiness gate. Verified: refactored digest runs on real prod data (per-type rollup), check-in shadow healthy post-restart (recent AGREE logs). The `settle:` line appears at the next redefine checkout (sparse; nightly digest 21:45 reports it). **NEXT 3b: points + AL-verdict + sick + schedule hooks (the rest of the menu).**
**▶ WIZARD WEBPAGE — STAGE 1 (read-only config viewer) LIVE ON SERVER (tag `session-53b-wizard-viewer-20260623` = `b1106be`; service `twbshop-wizard` active; bots UNTOUCHED — empty diff, no restart).** Owner's idea: see (later tweak) every live config decision on a webpage, no terminal. Built SECURITY-FIRST (CLAUDE.md ▶▶ PRODUCT SECURITY law): the brain stays server-side, the page serves rendered views only, binds **127.0.0.1:8090 ONLY** (verified — not 0.0.0.0), READ-ONLY, no secrets in any page. `wizard/app.py` renders the effective config with every knob badged **LIVE / SHADOW / PLANNED** (`wizard/status.py` = the cut-over map — only the AL ladder is LIVE today; the rest SHADOW) + `wizard/catalog.py` (the menu: categories · integrations · packages · AI-power). **ACCESS (owner): `ssh -L 8090:localhost:8090 twbshop` → open http://localhost:8090 (admin) · /customer (the product view).** Stage 3 = per-customer logins + HTTPS + cut-over controls. flask added (server venv).
**▶ WIZARD W2 — TWO VIEWS + CUSTOMER EDITOR (Apply/Cancel draft, explanations).** Owner Jun 23: the page must be customer-ready + let them play without changing things. Now TWO views off one engine: **`/` admin** (you — internal LIVE/SHADOW/PLANNED badges, raw, the catalog) vs **`/customer`** the PRODUCT — plain-English **explanation next to every setting** (`wizard/schema.py`: label · help · what True/False means HERE · enum-option meanings · the approval **if-conditions** spelled out), edited in a **DRAFT with “Apply changes / Cancel changes”** (nothing commits until Apply). SECURITY: the customer view leaks **NO internal badges** (verified 0), Apply writes **ONLY whitelisted SHADOW knobs** (server-side type/range/enum validation — LIVE knobs shown locked, unknown/LIVE/PLANNED keys rejected), still localhost+read-views. Locked categories show as upsell ("available in package X"). 8 wizard tests (incl. apply-clamps/rejects/ignores-LIVE, no-badge-leak). Suite 945p/2s+W2.
**▶ LIVE FIX DEPLOYED (tag `session-52f-leaveearly-sick-20260622` = `76de47d`): leave-early sick gets NO −15.** Owner Jun 22: a staffer who CHECKS IN then falls ill mid-shift (leave-early sick) must not get the −15 late-informing penalty (that's for late-informing an ABSENCE). Per-arc sweep deployed (gm active, NR=0): `_sickme_book` gate · `v_late_sick_penalty` exemption (checked_in set) · the "told us late" display nudge suppressed · `core/sick.py` shadow rule. **Long's erroneous Jun-21 −15 (points_events id 138) REMOVED** (vetted script, before/after independent: late_sick_inform 2→1; net −28→−13); his Jun-19 −15 (genuine absence) kept; **post-fix prod audit = 0 problems / 0 LATE-SICK flags.** Suite 928p/2s. **▶ PAYBACK HALF ALSO DONE (tag `session-52g-leaveearly-payback-20260623` = `50e7efd`).** Leave-early sick now pays back only the REMAINING unworked tail (`remaining_shift_min` + `_sickme_book` branch), not the full shift — pay model honoured (still paid the shift, repays only the missed tail; no checkout, which would underpay). **Long's #154 corrected 1094 → 856** (= 540 Jun-19 absent + 14 Jun-21 late + 302 Jun-21 sick-remaining; vetted script, independent before/after; booking #69 540 ≤ 856 no over-book). Post-fix prod audit = 0 problems. Suite 930p/2s. **The whole leave-early sick fix (−15 + payback) is complete, deployed, data-corrected, audit-clean — live + shadow (`core/sick.py`).**
**▶ NEW PLATFORM — FIRST SLICE BUILT (`core/`, INERT — parallel to live, acts on NOTHING, not deployed).** The product (per `docs/PLATFORM_VISION.md`) now exists in code, built on the bedrock laws: tenant-scoped (`org_id`), channel-agnostic (commands+events, no Telegram), entity+event (shift=stable id, date=label, append-only `attendance_events`), INTERVAL-ONLY time (overnight by construction), atomic-claim-at-the-write (UNIQUE-as-claim). Files: `core/db.py` (orgs·shifts·attendance_events·shadow_comparisons) · `core/shifts.py` (shift_window/ensure_shift/shift_for_instant) · `core/attendance.py` (check_in/check_out) · `core/shadow.py` (compare_checkin). **9 staging tests** incl. THE overnight proof (post-midnight check-in binds to the prior-day shift by construction), idempotency, tenant isolation, comparator. **▶ OPEN LOOP (owner Jun 22, "in case I forget"): MOVE IN DAYS NOT WEEKS.** Don't wait calendar-weeks for the shadow to prove out — use (1) the REPLAY accelerator (`scripts/replay_checkins.py` — compare weeks of real check-ins in seconds) + (2) COVERAGE (every scenario-type agreeing, not elapsed time) + (3) the readiness score. Loop: digest shows gap groups → port the gap → re-replay → gaps shrink → READY. First replay (131 real check-ins) gave the porting roadmap instantly: **rounding(~1m) · early-grace/threshold · redefine-awareness (payback/OT moved start)** — port these into `core.check_in`, re-replay, watch agree-rate climb. (Replay caveat: uses CURRENT schedule on historical rows — some mismatches are that, not logic.)
**▶ SHADOW SELF-REPORTING DEPLOYED + the verdict-parity port (tag `session-52c-verdict-parity-20260622` = `1501c13`, shadow on).** Nightly digest DM (`_shadow_digest_job` 21:45 PP — carryover + grouped mismatches + proposed fix + readiness) live; live hook moved AFTER the staff reply (zero latency). **PORT #1 DONE — `core.attendance.verdict` matches live (GRACE 5 / EARLY 5 / minute-of-day), per-tenant config; SHADOW-ONLY (live's `gm_bot/checkin` untouched).** **Replay loop PROVEN: 24% → 84% agree** (135 real check-ins, re-measured in seconds, confirmed on deployed server code). All gm restarts this morning clean (NR=0); shadow isolated — zero live interference. **▶ REDEFINE PORT DONE → CHECK-IN VERTICAL PROVEN ~EQUIVALENT (tag `session-52d-redefine-shadow-20260622` = `74deb2b`).** The shadow now feeds live's `resolve_day` resolved start (redefine-aware) in BOTH the replay and the LIVE hook. **Result (replay vs prod, post-launch): 98–100% agree** — redefine days 16/16 (was 69%), normal days 99/101; the ONLY remaining "mismatches" are the one-time go-live launch day (2026-06-16 grace, never recurs) + **2 minor 'early-5' boundary edges on Jun-17 (to investigate — likely seconds/first-ping nuance, 1.7%)**. The whole loop drove **24% → 98%** THIS session, every measurement via local replay (zero deploys to measure; all gm restarts clean NR=0). **The first vertical (check-in) is verified equivalent to live.** **▶ THE LINEUP → `docs/PLATFORM_ROADMAP.md`** (verticals sequenced by the shadow loop + risk + bonuses): #2 points (LOW) · #3 checkout (MED) · **#4 OT settle · #5 payback · #6 AL/sick (HIGH-RISK money — fresh focused sessions, atomic-claim-first)** · #7 schedule-changes · then web adapter + onboarding wizard + multi-tenancy + integrations. **Digest refined (deployed `a33ef1b`):** the nightly DM now splits the LIVE stream (readiness signal + carryover + fixes) from the REPLAY backtest (gap-analysis) + shows COVERAGE — so it reports a meaningful READY/not. Shadow live; DMs the digest 21:45.
**▶ PARITY-MATH PHASE COMPLETE — the whole attendance computation mirrored + parity-locked (commits `4dddcf2`·`06f36ff`·`2127d3d`; suite 903p→906p/2s/0f).** **#2 points** (`core/points.py` vs `gm_bot.points`) · **#3/#4/#5 settle** (`core/settle.py`: worked_minutes·ot_earned·split_ot_pb·settle_shift + honest bank-cap, vs `gm_bot.ot`) · **#6 AL/sick** (`core/leave.py`: charged-days·day-count·the S1 FROZEN deduction-map·short-notice·fractional, vs `gm_bot.al`) — each a DRIFT-GUARD parity test so the platform's own copy can't silently diverge from live. So the platform mirrors check-in (proven on real data 98–100%) + points + settle + leave math, ALL SHADOW-ONLY/parity-locked, acting on nothing. **Why safe to keep going (owner asked):** every port is shadow-only + parity-tested → a bug can only ever be a shadow MISMATCH, never live harm; the one genuinely HIGH-RISK gate is the future CUT-OVER (the live flip), far off + gated by shadow agreement.
**▶ ATTENDANCE BRAIN COMPLETE — + #7 resolver ported + the COVERAGE report (commit `edb1cdd`).** Added `core/schedule.py` (the resolver precedence leave>redefine>swap>day-off>normal, parity vs `gm_bot.attendance_ui.resolve_day` across the full space incl. ordering). **So the platform now mirrors the ENTIRE attendance brain** — verdict (PROVEN on real data) + points + settle + leave + resolver, all parity-locked/shadow-only. **▶ STUDY COVERAGE → `docs/PLATFORM_COVERAGE.md`** (owner asked "90%?"): honest answer = **NOT 90%** — the dominant daily flow (check-in) is PROVEN on real data; the whole computation brain is mirrored (parity); but by behavior BREADTH ~half remains GAP: the atomic ORCHESTRATION (the money-moving mechanism), the resolver's event-DERIVATION (self-derive), sick/no-show/special FLOW (per-channel adapter, not core math), and non-Telegram channels. **FINDING: channel-agnosticism already proven** (replay drives core with zero Telegram; hook drives it from Telegram — one brain, two channels). **▶ REMAINING (big-architectural / data-gated):** the atomic ORCHESTRATION (highest-stakes, atomic-claim-first, staging proof) · resolver self-derive via core EVENTS · web adapter + onboarding wizard (needs product decisions) · sick/no-show flow per-channel · **+ DAYS of real shadow data = the pacing constraint for cut-over (the nightly digest reports it 21:45).** → `docs/PLATFORM_ROADMAP.md`.
**▶▶ ATTENDANCE PLATFORM NOW BUILT END-TO-END (autonomous run; suite 923p/2s/0f; HEAD `6213023`; all SHADOW-ONLY, live untouched).** Since the brain: **both money mechanisms ATOMIC + staging-proven** — `core/ledger.py` (OT/payback: settle-once claim + CHECK constraints make over-bank/over-credit impossible + reversible S1; proven no-double-bank/cap/buyback-refusal/clean-reverse) and `core/leave_ledger.py` (AL deduct↔refund, frozen-map, exact reversal) → **the bedrock over-book/double-bank bug-class is now structurally impossible**. **Self-derive resolver** `core/derive.py` (core decides a day from its OWN `core_day_overrides` — cut-over-ready). **Sellable shell:** `core/channel.py` (channel-agnostic spine + a guard that fails the build if a channel SDK leaks into core) · `core/tenant_config.py` (per-tenant knobs on `orgs.config`) · **3 channels** (Telegram hook · replay · `adapters/web.py` HTTP) · `core/onboarding.py` (the self-serve wizard ENGINE; starter steps, owner refines questions/packages) · `core/points.py` full catalogue+derivation. **FINDING+FIX:** `early_bonus_min=0` mislabeled late→early (surfaced by the config layer); guarded; TWB 5/5 unaffected (no redeploy). **COVERAGE → `docs/PLATFORM_COVERAGE.md`:** the attendance platform is ~comprehensively built (parity-locked/staging-proven); EMPIRICAL live-data proof is still only check-in (money paths await real events = the days-of-study). **▶ GENUINE "NEED-YOU" POINT REACHED:** everything buildable WITHOUT owner input is done. NEXT needs the owner: (a) the wizard's real questions + **packages/bundles/pricing** (business), (b) **which domain next** (POS / stock / back-office). Meanwhile the shadow gathers real-data agreement + DMs the digest 21:45 (the cut-over clock). Lower-value leftovers: per-channel sick/no-show UI, the live→core sync bridge (redundant with the working fed path during the study).
**▶ SHADOW WIRING DEPLOYED + INERT (tag `session-52-shadow-20260622` = `f09743f`).** `core/shadow_hook.py::shadow_checkin` wired as the LAST step of the live gm check-in (`if first:` block), gated by `gm_state 'shadow_run'` (currently None=OFF → inert), fully isolated (try/except — can NEVER break live or reach Telegram), every line tagged `[SHADOW]`. Verified on prod: core tables (orgs/shifts/attendance_events/shadow_comparisons) created, tenant `twb` seeded, gm active NR=0, no errors. **▶ TO START THE SHADOW:** `gm_set_state('shadow_run','on')` (no restart — hook reads it live) → each real check-in also runs the new core + records new-vs-live in `shadow_comparisons`; watch via `[SHADOW]` logs + `core.shadow.comparison_stats()`. Early MISMATCHES are EXPECTED discoveries (new exact-interval vs live grace/rounding), not live bugs. After weeks of agreement → cut over. **THEN:** port lateness/AL/OT/payback, add a web adapter + the onboarding wizard.
**(prev, session 51d)** whole-system bedrock audit + F1 OT-buyback fix + token-leak hardening, deployed.
**▶ BEDROCK AUDIT (whole system) + FIXES DEPLOYED (tag `session-51d-audit-fixes-20260622` = `da2b022`).** 2 parallel code-audit agents + a live-prod data reconciliation. **Verdict: the LIVE GM attendance/payroll core is sound + live data is CLEAN (0 integrity issues across 15 money tables); real exposure is in DORMANT/DISABLED paths (landmines, not fires).** Full report → `docs/BEDROCK_AUDIT_2026-06-22.md`.
- **FIXED + DEPLOYED:** **F1** — the OT-rest buyback over-book (the un-fixed TWIN of the payback over-book): `ot_bank_spend`→`ot_bank_claim_spend` (ATOMIC conditional debit; refuses over-spend + double-tap; claim-first then book). Dormant on prod (ot_bank empty) but class closed. · **Token-leak**: `install_log_hygiene()` now on ALL bots (retail+B2B leaked their token to the journal) — verified retail journal = 0 token lines post-restart, gm = 0. Restarted gm/retail/listener/hire (all active, NR=0); b2b stopped (code updated, applies when started). · (earlier 51d-bundled: OT-vs-payback audit label.)
- **⚠ LANDMINES (not fixed — flagged):** **B2B money path has 3 HIGH bugs** (non-atomic apply_payment · no payment-dedup UNIQUE · `_do_confirm` flips status after moving money → double-credit). **B2B IS DISABLED — DO NOT RE-ENABLE until F2/F3/F4 are fixed.** · **Accountant** (inert) F5/F6/F7 (vendor merge re-merge guard · duplicate-vendor race · the P2 matcher stub must be built claim-first) → fold into the accountant build.
- **ROOT CAUSE (one disease):** caps/single-application enforced in the CALLER, not atomically at the DB write. Cure already proven in-codebase (flip-status-first `UPDATE…WHERE…RETURNING`, or UNIQUE-as-claim). **Adopt "atomic-claim-at-the-write" as a platform law** → the entity+event model + per-event verifier kills the whole class by construction (validates the platform direction).
**▶ WATCHDOG OVERNIGHT FALSE-POSITIVE FIXED + DEPLOYED (tag `session-51c-audit-overnight-20260622` = `6c4a024`).** The live watchdog DM'd at 2am: Nak #273 / Chantrea #274 "APPROVED for 2026-06-21 but never settled." FALSE ALARM — both work 21:00–06:00; their Jun-21 overnight shift runs until 06:00 Jun 22 (sessions still OPEN), and the payback slots settle at checkout. `audit.v_shift_changes` used `when_date<today`, which trips at MIDNIGHT for an overnight shift still being worked → a nightly 2am alarm for any overnight worker with a payback/OT slot. FIX: skip the "never settled" flag while the session is OPEN + recent; a CLOSED-but-unsettled (real settle failure) or OLD dangling redefine still flags — so the safety net is intact. Verified: local fixed audit vs REAL prod data = 0 (was 2); server audit after deploy = 0; gm active, NRestarts=0. 4 tests + 89 audit/shift regression green. **Self-heals at ~06:00 checkout (or the 07:00 closer); if a slot genuinely fails to settle after checkout, the now-correct watchdog WILL flag it.**
**▶ REASON-FIRST DEPLOYED + VERIFIED (tag `session-51b-reason-first-20260621` = `6a2e50e`, quiet window 16:4x PP Sun).** Sick ladder now STARTS with the reason: Sick → Me/Child/Spouse/Parent → "What's wrong?" (relationship-aware, mandatory) → THEN the time/date ladder → file (reason in FYI). Built: `attendance_ui._arm_sick_reason` (uid-keyed `sick_reason` flow_state, live+test, restart-safe) on the armed who-pick; `bot._private_text_router` captures the typed reason first (both actors) → stashes `sick_reason_val` → shows the next screen; `_att_dispatch` reuses the stash (confirm = a normal tap) with the mandatory gate as backstop. Verify: HEAD==tag, active, NRestarts=0, code carries it, no startup errors. 8 reason tests + full suite **875p/2s**. **⚠ NEEDS OWNER TEST-MODE WALK** (I can't tap Telegram): `/testmode` → Sick → Me → type reason → time screen → file → confirm FYI carries the reason; repeat for a family member. Rollback = redeploy tag `session-51-gm-20260621`.
**▶ DEPLOYED + VERIFIED (tag `session-51-gm-20260621` = `32ae8f4`, quiet window 16:12 PP Sun).** Restarted twbshop-gm only; server HEAD==tag, active, NRestarts=0, running code carries every change, `gm_events` table + `sick_cases.reason` column created on prod, no startup errors. **DATA-FIXES APPLIED (HIGH-RISK, independent before/after proof):** HENG debt #148 → **96/96 cleared** + phantom booking #62/sc #268 **cancelled** (over-book gone); LONG **−15 #130** recorded (bot teaches + offers 540 payback at next check-in). Audit now clean except **THYDA** (pre-deploy −15 miss, 13:52 PP before the 16:12 deploy — owner decision: fix too or leave per "just Long"). **GROUP POST still HELD** for owner go (Heng balance genuinely 0 now → ready). **Live-walk to confirm:** the mandatory sick-reason flow + the −15 firing on the NEXT real post-deploy own-sick.
**▶ ⑨ Bug B RESOLVED (settle verified correct + guarded).** Staging repro PROVED the settle happy-path credits a worked overnight tail (06:00–06:07 → debt 89→96→cleared). Heng's prod 0-credit was an EMERGENT symptom of his over-book tangle (many bookings on one debt + the phantom overbook + late-to-slot + a claim/timing race), NOT an independent settle bug — the enabler is now structurally prevented by the `book_room` guard, Heng's data is fixed, and `tests/test_settle_payback_tail.py` locks the tail-credit. (No static uncredited-detector — it false-positives on legit partial credit.) **Session 51 fully closed; nothing open.**
**▶ SESSION 51 — ATTENDANCE FORENSICS + DETECTOR LAYER (mix of shipped-inert + HIGH-RISK live fixes still to deploy).**
- **GUARD (shipped `54ae4f7`):** `highrisk_guard.py` now lets READ-ONLY staff/payroll queries through (a SELECT can't corrupt payroll); every WRITE + every other rule still hard-blocks. Also blocks `Copy-Item/cp` into `.claude/`. Source-of-truth = repo `.claude/hooks/`; owner copied to `~/.claude/hooks/`.
- **INVESTIGATION (read-only prod, all 3 confirmed):** **Heng** (id37) debt#148 owed96/paid89 — TWO real bugs: (a) a PHANTOM Jun-21 89-min slot (booking#62/sc#268) booked Jun19 20:08 BEFORE the Jun-19 89 credited (~23:00) → the bookable-remainder gate ignores a worked-but-uncredited same-day slot (stale-push hits the same gap); (b) the Jun-20 7-min TAIL (6:00–6:07, he checked out 06:07 = worked it) never credited. **Chenda** (id7) — CLEAN, owes nothing (59 cleared); only display/UX glitches (overnight-tail label "6am" under date 20/06 is really Sun 21 morning; missed checkout = left 31min before extended end). **Long** (id1) — paperless own-sick Jun19 → 540-min debt, the −15 DIDN'T FIRE. early_arrival is +10/event (the "+1" was event-count; not a bug).
- **−15 ROOT CAUSE — CORRECTED + FIXED (the big find):** NOT the pre-shift-window theory. `_sickme_book` computed lateness AFTER `sick_create`; once the case exists `resolve_day` reports the day not-working (start_min=None) → `_sick_late_mins` returns None → −15 silently skipped (self-cancellation/ordering). **⚠ It NEVER fired for ANYONE since go-live (Jun 16).** **FIX SHIPPED-INERT `d09e00c`** (capture lateness before sick_create; 3 tests incl. regression guard). **FAMILY-sick note VERIFIED built + NOT affected** (computed at screen-build before the case). **OWNER: retro = JUST LONG + going-forward.**
- **SHIPPED-INERT this session (all pushed, NOTHING deployed — one batched quiet-window GM deploy pending):** guard read-only `54ae4f7` · `gm_bot/events.py` `gm_events` log `52112c3` · `audit.py::v_late_sick_penalty` detector (DMs owner; flags Long) `be74a00` · **day-off 2h gate** `e5d0b75` (never offer a rest day for a debt <2h; owner rule) · **−15 self-cancellation fix** `d09e00c` · **token-out-of-logs** `shared/log_redact.py` (redaction filter + httpx→WARNING; wired into run_gm_bot).
- **REJECTED (important):** a `v_pb_uncredited` heuristic — FALSE-POSITIVES on correct partial credit (Nak/Chantrea came late to come-early slots; only Heng's full-tail-no-credit is real). Precise detection belongs in the Heng credit-fix, not a static heuristic.
- **TAIL-CHASING (owner ANSWERED):** a 1-min working-day slot is fine (it just extends a shift they're on); the rule is **don't offer a DAY OFF for a debt under 2h** — BUILT (day-off 2h gate above).
- **▶ STILL TO BUILD (HIGH-RISK live → staging proof + the batched deploy):** ② sick-reason mandatory (who→relationship-aware FREETYPE reason→confirm→FYI-at-confirm; reason stored on sick_cases) ③ return-announcement fix (don't say "back tomorrow" if already checked in; show day-of-week+date+start) + overnight-tail display (incl. Supervisors FYI: "Sat 20/06 shift → Sun 6:00–6:59am") ④ Heng gate-fix (count worked-but-uncredited slots) + 7-min credit-fix ⑤ instrument `log_event` everywhere + `init_events_db` on startup. **OWNER RUNS (vetted scripts, after deploy):** Heng data-fix (cancel #62/#268 + credit 7 → debt 0) · Long −15 + message + payback. **HELD:** both Supervisors posts. (ledger Open.)
- **⚠ PROD NETWORK was DOWN from dev at session end** (timeouts to the DO droplet DB+SSH; GitHub fine) → staging-integration re-run of the fixes + the deploy + the owner data-scripts all PENDING network + a quiet window. **FORENSICS GAP:** GM logs only scheduler/HTTP/errors — no per-staff events (→ ⑤ fixes it). Flaky F14 tests = pre-existing managed-PG connection flakiness, NOT a regression (clean code passes in 3.7s).
**(prev, session 50)** accountant receipt-read made deterministic + honest display (Khmer-handwriting wobble fix).
**▶ ACCOUNTANT READ FIX (session 50, INERT — staging/local only; the accountant is not a server service → nothing deployed).** Owner reported the SAME handwritten Khmer receipt reading differently each time (item names flipped "Mango/fruit"→"Chicken/Pork" while the $ numbers stayed identical). Root cause: `extract_receipt` (Sonnet, the accountant's read) ran at the DEFAULT **temperature=1.0** → it re-sampled low-confidence Khmer names every call. Numbers were stable because digits are unambiguous; names wobbled because the read is genuinely low-confidence AND sampling was wide open.
- **FIX 1 — `temperature=0`** on `extract_receipt` (`shared/ai_client.py`): same receipt → same output, the single most-likely read. (grep-confirmed ONLY the inert accountant calls `extract_receipt` → no live service changed → nothing to deploy.)
- **FIX 2 — honesty display** (`accountant/capture.py` `render_card` + `bot.py` `_card_text_kb`): a fresh, unconfirmed translation now renders `<as-written> → <guess>?` (the Khmer + a tentative guess) instead of a confident invented English word; a learned/confirmed alias drops the `?`. Stable numbers still show plainly.
- **PROOF:** full suite **792p/2s** (was 789; +3 render guards, zero regression); `git diff` = 4 files, +52/−2; staging DB lifecycle tests ran. **NOT empirically round-tripped on the live API** (would spend API on a contrived input) — owner confirms in the staging walk: send the same receipt twice → identical lines now.
- **▶ STEP 2 (durable handwriting fix) — IN BUILD → `docs/REPORT_SYSTEM_DESIGN.md §G`.** Feed each vendor's learned items + typical price bands *into* `extract_receipt` as soft context + a price "did-you-mean" ranking in the ✏️ Fix flow for low-confidence names. **Owner-locked:** (i) cold-read + post-read did-you-mean (no two-pass) · did-you-mean in Fix (card stays clean) · new-supplier = create-immediately behind a fuzzy dedup gate → **lean interim `needs_review` flag** (not the full Pending queue yet). **No new tables, no new API call** (priors = query over `acc_item_aliases` + `acc_receipt_lines`; ranking pure Python).
  - **✅ BUILT (session 50, vendor-identity layer — `accountant/{db,capture,bot}.py`):**
    • **V1/V2 foundation (§G7):** `vendor_by_name` alias-aware + deterministic (no false-match guessing) · `find_similar_vendors` fuzzy dedup gate (catches Altas→Atlas before a dup) · `add_vendor_alias` self-healing.
    • **V3 capture UX (§G7):** unresolved vendor → 🏷 Set supplier → button picker (fuzzy candidates of the read name) → pick existing OR ➕ add-the-read-name-as-new (no typing, works in-group) · `needs_review` non-blocking flag · owner DM one-tap ✅ Confirm · `/vendors` list.
    • **V3.5 channel + once-off (§G9):** 🔗 link the supplier's existing **group OR DM** by tapping a **listener-suggested** match (no scrolling 100s) · groupless first-class · 🗑 once-off `kind` flag (off the payable run) · **NON-BLOCKING throughout** (owner ask — staff never wait on a confirm).
    • **Proof:** accountant suite **green** (pure picker/ranking + vendor/channel/kind lifecycle tests); `bot.py` imports clean; schema additive (`needs_review`/`created_by`/`kind`/`channel_kind` on vendors, `read_vendor` on receipts), staging-only.
  - **✅ §G READ-PRIORS BUILT (session 50 — the original handwriting win, INERT/accountant):** (A) `extract_receipt(vendor_priors=…)` + `_vendor_priors_block` feeds the vendor's aliases + usual items/prices into the read as a SOFT hint (anti-anchor: "read what is ACTUALLY written") — wired into the candidate-promote flow (vendor known); Expense-group capture stays a cold read (decision i). (B) the ✏️ Fix flow now shows **price-based "did-you-mean" buttons** for low-confidence lines (`capture.dym_rows` + `did_you_mean` + `vendor_item_history`), one tap = rename + learn (re-derived server-side by idx). Foundation: `vendor_item_history` / `vendor_priors_for` (read-only). 13 §G tests; full suite 834p/2s.
  - **✅ V4 BUILT (session 50 — vendor rename/merge, §G7, INERT/accountant):** `rename_vendor` (old name → self-healing alias) · `merge_vendors` (OWNER, **ONE atomic transaction**: repoints receipts/payments/candidates + item-aliases dup→canonical, folds the dup's name/aliases in, moves its group if canonical has none, deactivates the dup, writes an `acc_vendor_merges` audit row with the moved ids) · `undo_vendor_merge` (reverses the financial repoint + reactivates; idempotent). Commands: `/vrename` (allowed), `/vmerge` + `/vmergeundo` (owner). Also tightened `vendor_by_name`/`find_similar_vendors` to **active-only** (a merged/deactivated dup never shadows the canonical). 4 V4 tests (before/after on real rows) + full suite **838p/2s**. **▶ NEXT:** all 🟢 safe builds done; remaining = the owner items (food go-live · the accountant staging walk · Bakong). **Design parked:** §H price-why-higher · rare-market-item tracking.
  - **FOOD MONEY (session 50): event-driven staging core BUILT + INERT; live wiring PENDING (ROADMAP §G).** Owner answers LOCKED: 500៛/**scheduled** shift hour ÷4000 HALF-UP (9h→$1.13, validated vs the real $11.92 sheet), no OT/PB, no-show→$0 · assignment **event-driven** (a give is OPEN, attaches to the next report STORED — `gm_daily_reports`) NOT a clock · bot **SHOWS** a "Day/Night staff food" list, never touches the drawer count · menu = the **listener↔bot private DM only** (`1271537077`). Built: `gm_bot/food_money.py` + `gm_bot/food_money_db.py` — calc · open gives (partial-UNIQUE no-double) · `close_food_period` · **`food_menu_rows` (ARRIVED-only + exclude-given + amount)** · **`food_arrived_staff` (CHECKED-IN via `attendance_sessions`⋈`staff_registry`)** · self-migrating init. **19 tests.** **ARRIVED RULE (owner):** menu = `checked_in_at IS NOT NULL` (actually arrived), NOT `_present_now` (schedule) — a scheduled-but-absent staffer never shows. **LIVE WIRING BUILT but GATED OFF:** `gm_bot/food_money_ui.py` — `/menu` in the **Expenses TWB group** (`-5417163768`, owner OR listener — owner's choice for a shared group) → 1 button "🍚 Food Allowance" → give flow [server-recomputed amount, name disappears] + close hook (posts the list to that group) + 3 `gm_bot/bot.py` touch-points. **Salary-leak guard:** owner menu now PRIVATE-only; food entry fully handles `/menu` in-group so the owner menu can't leak there. **`_food_gate_on()` = `att_test_on()` OR `gm_state 'food_money_live'='on'`, OFF by default** → deployed-but-off fully inert. 26 food/UI tests + **full suite 829p/2s**; `gm_bot.bot` imports clean. **⛔ GO-LIVE (needs owner):** (0) **add the GM bot to the Expenses TWB group** + privacy off (it's NOT in it per config), (1) quiet-window deploy, (2) `/testmode` walk in that group, (3) flip `gm_set_state('food_money_live','on')`. Checkout-only timing parked.
  - **PRICES = a PRIMARY goal (owner, §G8):** per-supplier price TREND + cross-supplier CHEAPEST comparison for ordering → the build keeps per-line prices + the canonical `item_id` path open (no vendor-only shortcut). Guardrails: a ranked guess never beats a confident read · learn only from HUMAN corrections · priors soft not anchors · prices a signal, the receipt number = truth.
**(prev, session 49)**
**▶ DUE-DILIGENCE SWEEP (session 49, read-only — code+docs only, ZERO prod connection, ZERO data writes; no deploy).** Owner asked: is our data mapped correctly for the new (truth-registry) system? **Verdict: YES** — registry internally consistent AND matches code ground truth (config.py eyeballed); subsystem statuses agree across CLAUDE/MAP/SUBSYSTEMS/registry; map-integrity + doc-staleness + integration-audit + full suite (789p/2s) all green; the old attendance contradiction stays uniformly LIVE. The registry is a deliberate seed, not a census (earn-it) — design, not a gap.
- **SEEDED +4 group-ID facts** (`supervisors_chat_id` -4980513319 · `management_chat_id` -865916135 · `comms_chat_id` -4248492531 · `staff_group_id` -1003457945308), all `config`-sourced (AST-self-verify), money-free. reconcile now **11 facts clean**; 13 registry tests pass. Honest value = **reference + mirror-drift** (none are doc-copied → no doc-drift surface): a queryable `whatis` home, not high-stakes protection.
- **AUTO-SEED future groups = NO (pinned).** It's the GENERATE pattern we rejected: a machine can only write the low-value half (no `mentions`), it bloats the curated registry into noise, and it cracks the "checker NEVER writes" invariant. Future groups earn a hand-seed WHEN their value starts living in 2+ places. (Candidate surfacer stays permanently deferred.)
- **FINDING (RESOLVED) — `twbshop-hire` deployed + running since 2026-06-17 but IDLE.** Read-only log dig: ZERO applicant interactions, ZERO AI calls — only a 10-min heartbeat + one self-healed network blip (`NRestarts=0`). Owner confirms pre-launch ("launching soon"). So: intentionally deployed/warming, NOT processing real people or spending — no action. Notes list corrected (it had omitted hire). `twbshop-b2b` currently DISABLED/stopped (known state).
- **`CUSTOMER_GROUP_ID` is dead** (0 code refs; customers order by DM — there is no customer group). Delete was **BLOCKED by the HIGH-RISK guard on config.py** and left in place: a cosmetic dead-constant cleanup does NOT justify a deliberate HIGH-RISK override of live config. Remove by hand if tidiness matters.
- **PARKED this session → `docs/ROADMAP.md` section F (NOT started):** marketing automation (Telegram Channel first · FB/IG via Meta Graph API · TikTok gated) · AI order-taker (AI-assist behind a human, no auto-userbot) · **WOC customer-number extraction** — a read-only DB dig CONFIRMED the archive: `WOC DELIVERY PICTURES` (chat_id `-715759659`) = **123,776 photos, 2022-01-07 → now**, already in `ops_messages` as metadata (image files still need downloading to extract); ~$250 Haiku to scan all; data model = number-keyed, names accumulate (one number → many names). ⚠ privacy/legal flag on the outreach stage.
**(prev, session 48)**
**▶ TRUTH REGISTRY (session 48, INERT — tooling/docs only, nothing live, no deploy).** One home for machine-knowable facts so a fact can't live in 2+ places and drift (the disease behind the "points" slip). Full design + the 4 holes → `docs/SIMPLIFICATION_STRATEGY.md` "TRUTH-CONSOLIDATION".
- **Artifacts:** `facts.json` (THE one home; 7 seeded facts that have bitten us — attendance status/go-live/live-flag, owner id, expense/report/stock group ids) · `scripts/facts.py` (`reconcile` read-only checker · `explain` value+provenance+lineage · `set_fact`/`append_lineage` the only writers) · `facts_lineage.jsonl` (append-only "how we got to each truth", merge-safe) · `scripts/whatis.py` (ONE-call lookup: registry+map+index) · `scripts/reconcile_facts.py` (CLI) · `.githooks/pre-push` (surfaces a doc↔registry contradiction + doc-staleness `tests/test_doc_refs.py` every push — loud, exits 0/never-blocks; `exit 1` = hard gate).
- **Key decisions:** **ASSERT > GENERATE** (a read-only checker can FLAG a wrong value but never WRITE one — reverses the earlier "generate beats assert"; generate only 100%-derived no-meaning artifacts like `MAP_INDEX.md`) · config/code facts AST-self-verify (no `secrets.py` coupling) · runtime (`attendance_live_flag`) freshness-flagged not value-asserted (no prod hit) · human statuses = cross-doc agreement only.
- **Proof:** suite **789 passed/2 skip/0 fail** (9 facts + 4 whatis tests, proven to bite on planted value/doc/pointer drift) · integration audit CLEAN (also mapped the prev-unowned `MAP.md`/`MAP_INDEX.md`) · pre-push hook real-path tested (clean→silent · contradiction→surfaces+exit0 · restored). Fixed a pre-existing calendar-coupled test (`test_now_pp_only_overrides_in_test_mode` false-failed on the real date 2026-06-20).
- **4 LEFTOVER HOLES (bounded, not closed):** traversal-not-enforced · chat-unchecked · wrong-at-birth (mostly closed for config/code) · unseeded-facts. Ceiling: a confident verbal aside about a never-seeded fact (shrinkable, not zero). **▶ NEXT:** grow the seed as facts bite/are corrected (don't pre-load) · deeper design-doc SEMANTIC sweep (human-adjudicated) · OPTIONAL candidate surfacer (defer until it bites).
- **PINS + CLEANUP (session 48 cont):** the holes were stress-tested → verdict **they're load-bearing (features of our own lean/earn-it/honest philosophy), do NOT "fix" them** — pinned in `docs/SIMPLIFICATION_STRATEGY.md` so a future session can't over-fix; candidate surfacer **permanently deferred**. **Money rule pinned** (HIGH-RISK): a live balance/payroll/price never enters as a cached `human` fact — money is `runtime` (point to live read) or omitted (keeps wrong-at-birth harmless). **MAP.md clarified** (post second-opinion pass): "the map points to truth, it is NOT the truth — verify VALUES against the code/`facts.json`; ground-truth-first" (additive, backstop intact). **Retired the old hand-kept repo tree REPO_STRUCTURE.md** — already stale (missing gm_bot/accountant/stock/hire_bot/ops_intelligence), now fully subsumed by the generated `MAP_INDEX.md`; its one good sentence ("one repo, one business…") lifted into `MAP.md`.
**(prev, session 47)**
**▶ SIMPLIFICATION PASS (session 47, INERT — `shared/database.py` + MAP only; nothing live changed, no deploy).**
**HONEST FINDING (validates "map, don't remodel"):** no big *safe* win exists — the only overloaded files are
the LIVE HIGH-RISK core (`gm_bot/bot.py` 7554, `shared/database.py` now 5708) which must NOT be split; the
safe surface was ~120 dead lines. **DONE — removed 11 confirmed zero-caller functions** from
`shared/database.py`, each with a LIVE replacement traced + (money/leave ones) owner-confirmed:
• **Batch 1 (non-money):** `staff_active_uids`, `categorize_stock_items` (kept `_STOCK_CATEGORIES`), 3×
`hiring_*` (hire_bot wires those tables itself across 11 files).
• **Batch 2 (money/leave, owner-confirmed each via menu):** `get_b2b_payment` + `update_b2b_payment_status`
(paid-state = balance `apply_payment` + `b2b_markpaid_requests`; `b2b_payments.status` vestigial, born
'applied') · `al_cancel_day` (superseded by atomic `al_cancel_and_refund`, `database.py` ~4200) · `ot_grant_create/get/set`
(old grant model RIPPED — HISTORY.md:2301; OT now = Give-OT/change-shift `shift_change_create`).
**PROOF (both batches):** suite **775 passed/2 skip = pre-change baseline** (zero regression) · each `git diff`
audited (only the targets; `ot_now_end_times` correctly kept) · grep = **0 code references** · `MAP_INDEX.md`
regenerated, both map guards green.
**▶ "POINTS" MAP-GAP — owner caught it, FIXED:** I mislabeled `gm_award_points` as "the staff-points feature" —
WRONG. **TWO systems:** LIVE `points_events`/`points_rules` (`gm_bot/points.py` + `points_record`;
early/late/no-show/sick/AL — counting fine) vs DORMANT `gm_staff_points` (`gm_award_points` + `/points`, old
recognition, never wired). Root cause: I grepped one table instead of drilling the map. **Fixed:** MAP.md
"points" entry now names BOTH (a don't-confuse gotcha; guards green). **Left untouched (owner):** the dormant
`gm_staff_points` recognition feature; also `seed_staff_registry`, `recompute_all_superseded` (manual tools,
callerless by design).
**▶ NEXT (owner-requested) — TRUTH-CONSOLIDATION / MAP CLEANUP:** the points slip exposed the disease = one
fact living in 2+ places that drift apart. Plan (full detail → `docs/SIMPLIFICATION_STRATEGY.md`
"TRUTH-CONSOLIDATION"): (1) sweep repo + docs + map, **list every spot with 2+ differing infos** → owner says
which is true → remove the untrue; (2) trim map/CLAUDE.md to **pointers-only** (one fact, one home); (3) type
docs *current-truth* vs *history-log* (HISTORY ≠ authority on "now"); (4) build a duplication detector. Rule:
machines fix STRUCTURE only; a human adjudicates MEANING (never auto-delete a true thing).
**▶ TRUTH-CONSOLIDATION — FIRST PASS DONE (session 47):** swept current-truth docs + map + numbers. Result:
mostly mechanical staleness + **1 real contradiction** — `docs/SUBSYSTEMS.md` said attendance "IN BUILD"
while CLAUDE says LIVE → **fixed to LIVE**. Stamped `docs/VERIFICATION_RECORD.md` as a session-33 historical
snapshot (its "564 passed / attendance_live=OFF" figures are frozen-in-time, not current). **Migrated session
44–46 blocks → `docs/HISTORY.md`** (current-truth vs history-log typing — that's why Current Status is short
now). Verified: moved phrases now in HISTORY only, boundary clean, dangling `(above)` refs repointed.
**▶ STALENESS GUARD BUILT (session 47):** `tests/test_doc_refs.py` — current-truth docs can't cite a
deleted/moved file or a gone `file::symbol` (proven to bite on the deleted `al_cancel_day`; history-logs
excluded). The structural half of the duplication detector; the semantic "same prose-fact in 2 places" half
stays human-adjudicated (a prose detector would false-positive — noise worse than the disease). **STILL OPEN
(owner resuming on the other PC):** (1) the duplication **"can we make it 100% safe?"** discussion — full
pros/cons + the promising **`facts.json` generated-single-source** path (turn statuses/dates/IDs structural so
they can't diverge by construction); (2) the deeper design-doc SEMANTIC sweep. Both detailed under
`docs/SIMPLIFICATION_STRATEGY.md` → "DUPLICATION DETECTOR — OPEN DISCUSSION".

**▶ STANDING OPEN LOOPS — the live threads (detail for completed work → `docs/HISTORY.md`):**
1. **Multi-lane operation (current focus)** — hub (`twbshop`/`main`) + 3 lane worktrees (`twbshop-accountant`/`-gm`/`-stock`). Portable method · toolkit · build sequence (Phases A–F) · lane layout/recreate → **`docs/MULTI_LANE_PLAYBOOK.md`** + `docs/PARALLEL_LANES.md`. Monitor (`scripts/monitor_bot.py`, owner-only): `/board /health /issues /crossings /audit`.
2. **Accountant bot** — P1.5 done (detail → `docs/HISTORY.md`); **NEXT = live-walk on staging → then P2 (HIGH-RISK money matcher)**. INERT (no server service imports it; nothing deployed). Design → `docs/REPORT_SYSTEM_DESIGN.md`. Key IDs: Expense group `-5417163768` · TEST Supplier `-5406470751`.
3. **Stock lane** — C2 foundation done (detail → `docs/HISTORY.md`); **NEXT (owner gate) = create the AppSheet app** → `docs/STOCK_APPSHEET_SETUP.md`. INERT. Then the GM↔stock cutover (remove `gm_bot/stock.py`; drift-guarded by `tests/test_stock_brain_no_drift.py` until then).
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
- B2B bot: `python run_b2b_bot.py` — systemd: `twbshop-b2b` (installed but DISABLED/stopped as of 2026-06-20 — the "intentionally stopped at times" state; start it when b2b goes live again)
- Listener: `python run_listener.py` — systemd: `twbshop-listener`
- Hire bot: `python run_hire_bot.py` — systemd: `twbshop-hire` (deployed + running since 2026-06-17 but IDLE — read-only log dig 2026-06-20 found zero applicant traffic + zero AI calls, only a 10-min heartbeat; pre-launch warming, owner confirms launching soon)
- GM bot: `python run_gm_bot.py` — systemd: `twbshop-gm`
  Groups the GM bot is IN: Stock Checks (-1003952029131), Supervisors, Management, COMMS & Transfers, TWB REPORT (-5136886404)
  Groups it monitors but does NOT post to (except TWB REPORT receipt checks): all of the above
- Wizard config viewer: `python run_wizard.py` — systemd: `twbshop-wizard` (read-only, **localhost:8090 ONLY** — reach via `ssh -L 8090:localhost:8090 twbshop`). Not a bot; serves the config viewer. Restarting it never affects the bots.
- Price list fetcher: `python run_fetch_pricelists.py` — run manually to refresh supplier files
- Set ANTHROPIC_API_KEY in config.py to enable AI features (retail bot only for now)
- B2B customers: 24+ active customer groups identified in ops_messages DB; none have the bot yet — all ordering manually
- Bakong/KHQR registration pending — need passport (on other PC); check ABA app merchant QR first
- Personal project created at `C:\Users\Papa\Personal` — secretary bot command centre (separate repo)

---

---

## B2B Orders Bot — b2b_bot/
*Working on the B2B wholesale bot? Full design rules, repo structure, and build phases → `docs/B2B.md`.*
