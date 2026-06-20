# Bakery Automation System — Project Rules & Status

> **🗺️ START HERE — open `MAP.md` for ANY task** (Layer 1: entry files · law-doc · `docs/HISTORY.md`
> section · ⚠ gotcha per area). **Need any other file / "where's function X"? → `MAP_INDEX.md`** (Layer 2:
> auto-generated complete inventory). **Before claiming anything exists / works / is missing / is a gap,
> check the records the map points to and cite them — or say "let me check" and check.** An unverified
> gap-claim is a violation, same as a false "done" (2026-06-19). On any file add/move/rename: run
> `python scripts/gen_map_index.py` (Layer 2 freshness is build-enforced) and fix any Layer-1 entry you
> changed — guards: `tests/test_map_integrity.py` + `tests/test_map_index_fresh.py`.

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

**Last updated:** 2026-06-21 (session 50 — **accountant receipt-read made deterministic + honest display (Khmer-handwriting wobble fix)**).
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
  - **▶ NEXT:** V4 rename(staff)/merge(owner) · then §G priors-into-read + Fix did-you-mean. **Owner walk** the V3/V3.5 button flows on staging (handlers aren't unit-testable). **Design parked:** §H price-why-higher · rare-market-item tracking.
  - **FOOD MONEY (session 50): event-driven staging core BUILT + INERT; live wiring PENDING (ROADMAP §G).** Owner answers LOCKED: 500៛/**scheduled** shift hour ÷4000 HALF-UP (9h→$1.13, validated vs the real $11.92 sheet), no OT/PB, no-show→$0 · assignment **event-driven** (a give is OPEN, attaches to the next report STORED — `gm_daily_reports`) NOT a clock · bot **SHOWS** a "Day/Night staff food" list, never touches the drawer count · menu = the **listener↔bot private DM only** (`1271537077`). Built: `gm_bot/food_money.py` + `gm_bot/food_money_db.py` — calc · open gives (partial-UNIQUE no-double) · `close_food_period` · **`food_menu_rows` (ARRIVED-only + exclude-given + amount)** · **`food_arrived_staff` (CHECKED-IN via `attendance_sessions`⋈`staff_registry`)** · self-migrating init. **19 tests.** **ARRIVED RULE (owner):** menu = `checked_in_at IS NOT NULL` (actually arrived), NOT `_present_now` (schedule) — a scheduled-but-absent staffer never shows. **⛔ REMAINING (HIGH-RISK live):** the listener-DM menu UI (assemble via `food_menu_rows(food_arrived_staff(dates), food_money_open_ids())`) + the **close hook** after `save_daily_report` in `_store_daily_report_if_any` (~bot.py:1055) + flag-gate + owner `is_test` walk + quiet-window deploy. Checkout-only timing parked.
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
- Price list fetcher: `python run_fetch_pricelists.py` — run manually to refresh supplier files
- Set ANTHROPIC_API_KEY in config.py to enable AI features (retail bot only for now)
- B2B customers: 24+ active customer groups identified in ops_messages DB; none have the bot yet — all ordering manually
- Bakong/KHQR registration pending — need passport (on other PC); check ABA app merchant QR first
- Personal project created at `C:\Users\Papa\Personal` — secretary bot command centre (separate repo)

---

---

## B2B Orders Bot — b2b_bot/
*Working on the B2B wholesale bot? Full design rules, repo structure, and build phases → `docs/B2B.md`.*
