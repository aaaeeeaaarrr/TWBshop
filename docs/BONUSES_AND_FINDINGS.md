# Bonuses & Findings — running ledger

> **Standing practice (owner, 2026-06-23):** as we build, ALWAYS append the **bonuses** (unexpected wins,
> sellable angles, leverage) and **findings** (discoveries, gotchas, decisions) here — capture everything,
> shave/improve later. This is the home; one line per item + a tag. Newest section on top.

Tags: `[ship]` shipped/true · `[idea]` worth doing, not built · `[sell]` a sellable angle · `[gotcha]`
a trap to remember · `[needs-validate]` built but unproven · `[decision]` a choice made.

---

## Session 55 — A-Z due-diligence audit (ultracode, 44-agent, read-only)
Full report: workflow `wf_7bb0f25d-3e6`. Verdict: LIVE production core is sound + suite really green
(1081p/2s); ONE CRITICAL credential to rotate; the rest are INERT platform fixes on the harvest.

### 🎁 Bonuses
- **Atomic-claim discipline is REAL where it matters** `[sell]` — att_check_in CAS · no_show ON CONFLICT
  DO NOTHING RETURNING · shift_change_claim_settle CAS · ot_bank_claim_spend conditional CAS ·
  al_approve_and_deduct advisory-lock + frozen map · payback_book single-txn chokepoint. "over-bank/
  double-credit impossible by construction" is TRUE on the live path, not just claimed.
- **One cheap primitive kills the live own-sick race AND any flow double-dispatch** `[idea]` — make
  flow_clear a claim (`DELETE … WHERE uid=%s RETURNING uid`), dispatch only on a won delete. The project's
  own flip-first cure, turning the flow dispatcher into a single-winner like check-in/settle.
- **core/till.py is a reusable reference S2/S3/S4 implementation** `[ship]` — partial-unique atomic claim +
  flip-status-first idempotent close + derived-not-stored expected_cash + every move hash-chained. Lift its
  UNIQUE-as-claim / flip-first pattern straight into payroll/stock/dedup.
- **DB-level CHECK constraints already refuse over-credit** `[sell]` — core_ot_bank balance>=0,
  core_payback_debts paid<=owed. "storage-layer guarantees, not trust-the-caller" — extend to OT cap, AL
  floor, on_hand>=0 to make the payroll-product claim fully true.
- **Two-layer audit catches a DB-admin re-chain + anchor forgery** `[sell]` — "tamper-evidence the DB admin
  themselves can't quietly defeat"; hashes NOT NULL from row 1 (better than the harvested source).
- **Shadow-run = a paid de-risking offering** `[sell]` — double-wrapped try/except + own logger + own tables
  + off-by-default + separate connection ⇒ it can NEVER roll back or block a live txn.
- **core/* imports ZERO channel SDKs / legacy bot modules, build-guard-enforced** `[sell]` — the brain can be
  lifted out cleanly; the rebuild-clean goal is enforced, not just claimed.
- **Tenant isolation is consistently org_id-scoped across every core domain query** `[sell]` — no
  cross-tenant leak found in the sweep; reinforced by the single-tenant-per-process wizard model.
- **Turn the negative/abnormal cash_event hole into a feature** `[idea/sell]` — a "negative/abnormal
  cash_event" detector feeds the existing shrinkage/investigation suite: a gate-bypass bug → a sell point.
- **One auto-discovery change fixes the map-completeness gap AND both its guards** `[idea]` — the map tooling
  itself recurs the signature bug-class (a value hardcoded in the caller, here PKG_DIRS, not derived from the
  filesystem). Closing it makes "check the map before claiming a gap" trustworthy for the whole repo.
- **The AL deduct/refund pair is a clean reusable S1 template** `[ship]` — deduct-at-approval + frozen per-day
  map + ONE shared inverse reused by Cancel-AL and in-txn supersede. The model for porting OT/payback/POS-till
  money paths to core/.
- **Near-zero-cost lever: wire the already-rendered wizard knobs into core math** `[idea]` — ot.bank_cap_min +
  leave.short_notice_days are display-only today; wiring them into core.settle/core.leave makes two settings
  genuinely functional per-tenant AND kills a duplicate-constant drift class.
- **One lock-key per actor across all balance-moving features** `[decision]` — the advisory-lock namespace
  (911, staff_id) already serializes AL vs shift-change vs swap vs supersede; document it as a platform
  invariant to harden every future multi-writer (S5) feature.
- **conftest forces TWBSHOP_ENV=staging before the pool builds** `[ship]` — no test can mutate prod;
  test_till.py + test_audit_chain.py are model harvest tests reusable as the re-test template for the rest.

### 🔍 Findings (severity / where → fix)
- ⭐⭐⭐ **SEC-01 (CRITICAL/live):** live GM bot token in `tests/test_log_redact.py:6` == `secrets.py:16`, in
  git history (commit 89a2bd2) → **ROTATE via BotFather**; working-tree literal scrubbed to a synthetic
  same-shape token (done s55). Deleting the line can't undo history.
- **F4 (HIGH/b2b-disabled):** `_do_confirm` moves money before flipping request status → claim-first
  `UPDATE … WHERE status IN('draft','pending') RETURNING`.
- **F2 (HIGH/b2b-disabled):** `apply_payment` non-atomic (3 commits) + non-idempotent → one _db() txn +
  idempotency key + Decimal/integer-cents.
- **F3 (HIGH/b2b-disabled):** `b2b_payments` has no dedup UNIQUE (racy check-then-write) → partial UNIQUE on
  file_unique_id/message_id + ON CONFLICT DO NOTHING.
- **SICK-RACE (MED/live-gm):** own-sick auto-resolve vs typed-reason race doubles payback debt + dup
  sick_case → flow_clear-as-claim. PARK deploy for owner quiet-window.
- **HIRE-TOK (MED/live-hire):** `create_session` raises AttributeError on the secrets.py stdlib shadow
  (sessions.py:50) → os.urandom token + a create_session test. PARK deploy.
- **INIT-ORDER (MED→fixed-in-tree s55):** core/db.py ALTERed core_sales before CREATE (:311 vs :367) →
  fresh/DR DB crash-loops the live gm boot. **Reordered + run_gm_bot init wrapped try/except** (deploy gated).
- **LEDGER-CAP (MED/inert):** OT 14h cap enforced in caller from an unlocked read (ledger.py:62-78); two
  same-staff shifts over-bank → FOR UPDATE + `SET balance=LEAST(cap, …)`.
- **LEDGER-PHANTOM (MED/inert):** debt read not FOR UPDATE; concurrent settle logs phantom pb_cleared and
  reverse_settle corrupts the winner's credit → log RETURNING delta only.
- **AL-SIGN (MED/inert):** leave_ledger no-row UPSERT writes +total (credits) instead of −total on a first AL
  approval; cancel asymmetric → insert 0-total + symmetric refund + CHECK>=0 (leave_ledger.py:54-57).
- **AUDIT-FORK (MED/inert):** chain head ordered by pre-lock wall-clock `at` + random uuid (false FAIL +
  genuine fork undetected) → BIGSERIAL seq under the lock + UNIQUE(org_id,previous_hash) + branch detection.
- **AUDIT-TXN (MED/inert):** audit row written in a separate txn after the money/config commit; a missing row
  is undetectable by verify_chain → thread a caller cursor into audit.write (same-txn).
- **PAYROLL-IDEMP (MED/inert):** run_payroll non-idempotent, re-run double-creates payslips → UNIQUE(org_id,
  period) + ON CONFLICT + UNIQUE(run_id,staff_id) + a re-run test.
- **STOCK-NEG (MED/inert):** on_hand has no >=0 CHECK; record_sale subtracts blindly → negative stock corrupts
  shrinkage/suspect output → CHECK(on_hand>=0) or guarded decrement.
- **DOMAIN-IDEMP (MED/inert):** record_sale/receive_purchase/add_expense/record_count have no idempotency key
  (the planned offline queue makes this real) → client_key + partial UNIQUE + ON CONFLICT (phase 3).
- **WEB-ADAPTER (MED/inert):** adapters/web.py takes org_id from the request body + serve() binds 0.0.0.0 with
  no auth → server-side org from authed session + reject body org_id + 127.0.0.1 default + import-guard test.
- **GUARD-REGEX (MED/na):** secret_guard.py:33 token regex misses the bot-prefixed leak form (leading \b
  blocks anchoring) → drop \b / add (?:bot)? + a regression case; align with log_redact.py:15. (owner-gated:
  editing .claude/hooks/ is guard-blocked for me.)
- **SHADOW-VACUOUS (MED/inert):** settle shadow agrees by construction (re-runs identical source on live
  outputs; payback-slot never compared) → "settle 100% agree" is NOT a money cut-over signal → model the
  payback-slot for real / label informational rows; parity-lock verdict.
- **GUARD-SKIP (MED/inert):** over-book/double-bank/tail money guards pytest.skip on an empty staging
  staff_registry → self-provision an is_test staff row so they can't silently skip.
- **MAP-INCOMPLETE (MED/na):** MAP_INDEX/gen_map_index PKG_DIRS + test_map_integrity _PACKAGES omit
  core/wizard/adapters/telegram_bot (~50 files incl. a LIVE retail-bot dir) while claiming "can never omit a
  file" → auto-discover dirs containing .py; refresh MAP.md core/ section.
- **TILL-ACTOR (LOW/inert):** cash events/closes audited as the shift opener not the actual actor → actor
  param/column + thread _current_user (before any multi-cashier go-live).
- **REFUND-ASYM (LOW/inert):** till refund reconciles the drawer but isn't symmetric with sale/stock (no void
  → revenue overstated S4 + stock decremented S1) → void_sale/refund_sale one-txn resolver (phase 2b).

### 🛠 BUILD — audit fixes shipped to staging (inert; live deploys PARKED for the owner)
All on staging, each with a regression test; nothing deployed to a live bot. Live-service code is prepared +
proven but the DEPLOY is owner-gated (own-sick race · hire token · init-order · token rotation).
- ✅ **leave_ledger AL-SIGN** `[ship]` — a first-ever AL approval now DEDUCTS from an implicit zero (was a
  silent over-CREDIT); cancel made symmetric (recreates a missing row). *Decision:* declined a `CHECK>=0` on
  core_al_balance — AL over-draw is a caller-side approval gate, not a storage invariant (unlike OT bank where
  a negative balance is meaningless); a negative AL balance is a recoverable "took more than entitled" state.
- ✅ **ledger over-bank + phantom credit** `[ship]` — a per-staff advisory lock (the live `911,staff_id`
  pattern) serializes a staff's concurrent settles + `FOR UPDATE` + a `LEAST(cap,…)` structural belt; the
  event records the ACTUALLY-applied payback (RETURNING) so reverse_settle can't un-credit a phantom. Proven
  with a real threaded race test.
- ✅ **audit chain same-txn + un-forkable** `[ship/sell]` — `audit.write(cur=…)` writes the chain row in the
  caller's transaction (no applied-but-unaudited window); a `BIGSERIAL seq` (assigned under the lock) is the
  one true order; a partial-UNIQUE(org_id, previous_hash) makes a fork physically impossible (DB-enforced CAS)
  + verify_chain gained fork detection. The "tamper-evident money audit" claim is now airtight.
- ✅ **2b void/refund** `[ship/sell]` — `pos.void_sale`: one txn marks the sale voided (single-void), gives the
  stock back, fires a 'refund' drawer event so the till reconciles, same-txn audit; revenue excludes voided.
- ✅ **offline-idempotency (S2) across the domains** `[ship]` — an optional client_key + partial-UNIQUE +
  ON CONFLICT on record_sale / receive_purchase / add_expense / record_count → a crash-redelivery / double-tap
  re-applies NOTHING (the offline-queue cure, ready for harvest Phase 3).
- ✅ **STOCK-NEG + PAYROLL-IDEMP** `[ship]` — a sale clamps on_hand at 0 (`GREATEST`) + a `CHECK(on_hand>=0)`
  belt → shrinkage math can't be corrupted; UNIQUE(org,period)+UNIQUE(run,staff) + claim-first run_payroll →
  re-running a period creates no duplicate run/payslips.
- ✅ **map completeness** `[ship]` — the generator + integrity test now DERIVE the package list from the
  filesystem (one source of truth) → MAP_INDEX 190 entries incl. core/wizard/adapters/telegram_bot (was blind
  to ~50 files incl. a live retail dir while claiming "can never omit a file").
- ✅ **money-guard skip closed** `[ship]` — the over-book/double-bank/tail guards self-provision a dedicated
  ex_staff test staffer → they can never silently skip on a fresh/empty staging DB.
- ✅ **web adapter hardened** `[ship]` — rejects a client-supplied org_id (403, cross-tenant guard) · serve()
  defaults to 127.0.0.1 · 1MB body cap · an import-guard test fails if a run_*.py wires it without W3 auth.
- ✅ **TILL-ACTOR + voids/refunds log** `[ship/sell]` — cash events/closes now record the real actor (not the
  shift opener); `investigate.voids_refunds_log` surfaces voided sales + refund/payout drawer events + who did
  them = the parked loss-prevention "voids/refunds log", now real.
- ✅ **own-sick double-book RACE closed (LIVE-prep, deploy PARKED)** `[ship]` — `flow_clear` is now an atomic
  CLAIM (delete-and-return): exactly one of a racing typed-reason + the 30-min auto-resolve books the payback.
- ✅ **hire-token break fixed (LIVE-prep, deploy PARKED)** `[ship]` — `create_session` mints via os.urandom,
  not the stdlib `secrets` the repo's secrets.py shadows.

### 🎁 New bonuses surfaced during the build
- **flow_clear-as-claim is a one-line, reusable single-winner primitive** `[ship]` — `DELETE … RETURNING` turns
  any flow dispatcher into a race-safe single-winner; the same shape can guard any future "two callers, one
  effect" path (the project's flip-first cure generalized to the flow layer).
- **The void→refund→audit chain is a sellable loss-prevention story** `[sell]` — every void gives stock back,
  reconciles the drawer, AND writes a tamper-evident, actor-attributed audit row in one transaction; the
  voids/refunds log reads straight off it. "Nobody can quietly void a sale" is now demonstrably true.
- **Map tooling itself had the signature bug-class** `[gotcha]` — a hardcoded package list in the CALLER instead
  of derived from the source of truth (the filesystem). Fixing it makes "check the map before claiming a gap"
  trustworthy for the WHOLE repo, and is a clean example to cite when teaching the bug-class.

### 🛠 s55 continuation (live swap fix + max-effort run: deferred bits + investigation)
- ✅ **swap rule → overlap-based + config-driven** `[ship/sell]` — the day-off swap picker now matches by shift
  OVERLAP (≥ half the shorter shift) instead of "starts within 3h", de-duplicated to ONE function, made a
  config-driven setting (3 rule types + tweakable threshold in the customer config editor, gm reads it live,
  fail-safe). Fixed a real owner case (Norin 13-23 ↔ Chomreun 09-21, 8h overlap but 4h apart at the start).
- ✅ **verdict parity-lock** `[ship]` — a full-minute-grid test locks core.attendance.verdict == live
  gm_bot.checkin.verdict, so the platform check-in verdict can't silently drift from live (shadow integrity).
- ✅ **domain→audit-chain** `[ship/sell]` — sale/count/receive/expense/payroll mutations now each write a
  tamper-evident hash-chained audit row (verify_chain stays PASS); "every move on the platform is
  who-did-what-when, un-tamperable" is now true across ALL domains, not just the till.
- ✅ **cash-drawer over/short + voids/refunds surfaced** `[ship/sell]` — `investigate.cash_drawer_report` + the
  voids/refunds log now show on /investigate (the two classic POS shrinkage vectors), completing the
  loss-prevention suite (shrinkage · suspects · after-hours · repeat-pattern · over/short · voids/refunds).
- 🔍 **the GM-token incident → a standing lesson** `[gotcha]` — rotating a BotFather token in DEV secrets.py
  doesn't reach the server (push-then-pull); the running bot also needs a restart to load it. The server's
  GitHub PAT was dead too, so `--sync` failed — fixed by an SSH copy + restart. Diagnosis path: getMe(401) +
  token-fingerprint dev-vs-server. (Full proof → docs/ACTIONS_LEDGER.md.)
- ✅ **onboarding questionnaire (packaging per client-type)** `[ship/sell]` (owner) — a `/welcome` flow: 3
  information-gain-ordered questions (industry → size → biggest pain) → a starter template + package tier +
  enabled domains (a tunable table), skippable any time, then 'Customize your experience'. The 'stupid-proof
  self-serve wizard' North Star made concrete; built on the existing apply_template/packages/config levers.
- ✅ **automations recipes** `[ship/sell]` (owner) — `core/automations.py` + `/automations`: 8 one-tap plain-words
  recipes (condition → action) riding the EXISTING detectors (insights.attention_feed + investigate) so they're
  computer-tier (NO model cost), config-driven, with a 'would fire now' preview. The lean Fin-borrow: a simple
  front door (recipes) onto ONE {condition,action} engine; the custom builder is the advanced door (next), and
  the live SEND (adapter/gm dispatch) is the follow-up. Both doors compile to the same shape.
- ✅ **comms-responsiveness brain (deterministic)** `[ship/sell]` (owner) — `gm_bot/comms.py`: detect a staffer
  who was @-mentioned / replied-to and never answered within the window, matched by Telegram ID — not a text
  guess — with a nudge→escalate ladder. Gated off; group MESSAGES only (calls are out of scope).
- ⭐ **FINDING — we were DISCARDING structured signals the listener already receives** `[gotcha]` (owner caught it)
  — ops_messages stored only name+text+time, so I'd planned a FUZZY text detector; the listener actually gets the
  sender id, the @-mention ids (tap-mentions carry the user id), and reply-to per message. Capturing them (a tiny
  listener change: 2 columns + 2 lines) makes "addressed + unanswered" a deterministic FACT, killing the
  false-positive risk that made auto-complaining about staff dangerous. **Lesson: check what the source ALREADY
  gives before settling for a heuristic.** (1-to-1 Telegram calls stay invisible — the listener isn't a party;
  cellular calls need a phone app.)

---

## Session 53 — config-driven wizard · onboarding · channels · platform

### 🎁 Bonuses
- **Shadow-run as a SELLABLE feature** `[sell]` — "run the new system beside your current way risk-free, cut
  over when YOU'RE convinced." Our internal cut-over tooling → a sales line ("try it in parallel, 2 weeks").
- **Bot-IN-groups as the listener** `[ship]` — drop the Telethon user-account session; the tenant just adds
  their bot to the group and it reads. Safer (scoped), simpler, "approve a link = add the bot."
- **Bot-as-approver** `[ship]` — "Computer/AI Power" applied to approvals: the bot auto-decides on coverage
  ("approve leave only if min skill coverage still holds"), humans handle judgement calls. A differentiator.
- **The cut-over dashboard** `[ship]` — the wizard shows shadow agreement per vertical = a go-live control panel.
- **"DISCOVER don't dictate, CONFIRM don't type"** `[ship]` — the onboarding principle; turns TWB's months of
  manual setup into an afternoon. The contrast IS the pitch.
- **LIVE-FIXED-editable** `[ship]` — editing a not-yet-cut-over knob is a harmless SAVED PREFERENCE (zero live
  effect till cut-over), so a customer configures everything freely + safely.
- **Templates = a 60-second start** `[sell]` — bakery/cafe/retail presets; and sellable **industry packs**.
- **"Approve a link" everywhere** `[ship]` — `/start` deep-link (silent staff), Google OAuth (planned), the
  web check-in token. Minimise typing, maximise tap.
- **The web channel proves channel-agnostic OPERATION** `[ship]` — staff check in/out via a browser link, same
  brain as Telegram + the replay. Not just onboarding — daily use, any channel.
- **FIVE core domains in one wizard** `[ship/sell]` — attendance (live-mirrored) + accountant + stock + POS +
  HR/payroll (modelled). The "total business platform" pitch is now concrete: one wizard configures the whole
  shop. Adding a domain = a config block + schema group + a customer section + 1 test (~15 min each).
- **Per-customer shadow + test-mode as a de-risked go-live** `[idea/sell]` — each tenant validates before cutover.
- **"What-if" config preview** `[ship/sell]` — "if you set grace to 9 min, N of your last M check-ins
  reclassify (late→on_time)." A customer SEES a change's effect on their REAL data before applying — removes
  the fear of changing a rule. A genuine confidence/sales feature; more what-ifs (OT cap, AL ladder) slot in.
- **Config change log (auditability)** `[ship/sell]` — every config edit logs who-changed-which-knob-when
  (`core_config_audit`); PRODUCT SECURITY law #5. Trust + forensics + the multi-tenant story. Secrets log the
  ACT, never the value. A `/audit` page (+ a link from the customer view).
- **Staff "my recent check-ins"** `[ship]` — the web check-in page shows the staffer their last few check-ins
  (date + verdict); a small transparency/trust touch that completes the staff web view.
- **Admin command-center dashboard** `[ship]` — the admin home now has a full tool nav (all ~12 routes
  reachable; the new what-if/audit/templates were orphaned) + an "at a glance" status (staff/groups/channels/
  last change). Ties the sprawling wizard together. (Also fixed a stray `<\code>` typo in the admin header.)
- **Config export / import** `[ship/sell]` — a tenant's setup is portable: export their customizations (JSON,
  no secrets) to back up or CLONE onto another tenant; import reuses Apply's whitelist (only safe knobs,
  audited) so it's as safe as the editor. A multi-tenant lever — template a setup, onboard a similar shop fast.
- **Platform e2e smoke test** `[ship]` — one test walks org→staff→config(audited)→web check-in→history→
  what-if→export; proves the pieces CONNECT (integration regressions the units miss) + a PARTIAL answer to the
  "unvalidated" gap — the platform's own flow is now proven; only the live-bot Telegram leg stays unproven.
- **Config health-check** `[ship/sell]` — read-only validation surfacing likely setup mistakes (expertise on
  with no skills · OT banking with a 0 cap · no staff group · Telegram with no token · AL=0 · …); a `/health`
  page + an at-a-glance count on the dashboard. Lets a customer self-correct before it bites — a support-cost
  reducer + trust signal. Add a check = one line in `core/health.py`.
- **Go-live readiness gate** `[ship]` — `/setup` folds the health-check in as a 5th step ("clear config
  warnings") and shows a "🎉 Ready to go live!" banner ONLY when all 5 are green. A clear, honest "you're
  done" signal for onboarding (not just "4 of 4 checkboxes" — it also means the config is sane).
- **Readable config diff on export** `[ship]` — the export page shows "default → your value" per customized
  knob in plain English (not just JSON), so a customer sees exactly what they've changed at a glance.
- **Customer sees their OWN config health** `[ship]` — warn-level issues now show as a banner at the top of
  the customer view (not just the admin `/health` page), so a tenant self-corrects. Health-check is now
  customer-facing — more valuable wired into the place they actually edit.
- **Customer view links to ADMIN + shares tool navs** `[gotcha/parked]` — the `/customer` view has a
  `← admin` link and the what-if/audit/health pages carry admin-style navs. Harmless while owner-only on
  localhost, but for a REAL multi-tenant customer the customer surface must expose NO admin links / internal
  pages. Tie to auth-roles (W3): serve customer-appropriate navs when authed as a customer. PARKED (W3).
- **Security response headers** `[ship]` — `X-Frame-Options: DENY` · `X-Content-Type-Options: nosniff` ·
  `Referrer-Policy: no-referrer` on every wizard response (anti-clickjacking / MIME-sniffing; W3-prep, zero
  behaviour change). CSP deferred — the inline check-in JS/styles need a nonce or refactor first (parked W3).
- **Dashboard onboarding progress** `[ship]` — the admin "at a glance" now shows **setup N/5** (linked) +
  warnings, via a shared `_setup_state` so `/setup` and the dashboard can't drift (truth-consolidation by
  construction). The owner sees how close a tenant is to go-live without opening /setup.
- **Request-body size cap** `[ship]` — `MAX_CONTENT_LENGTH = 2MB` (a >2MB POST → 413); a memory-DoS guard for
  the import/forms. W3-prep, zero behaviour change.
- **What-if current breakdown** `[ship]` — the what-if now shows "Currently: X on-time, Y late, …" for context
  beside the change count.
- **Onboarding chain e2e (REAL core)** `[ship/needs-validate]` — a test drives the Telegram adapter → REAL
  core → DB across 3 paths (confirm · consent "approve-a-link" carries to the staff record · skip). The
  integration the mock-only adapter tests don't cover. Strongest de-risking of the unvalidated onboarding
  short of a real bot (the Telegram TRANSPORT is still mocked — a live BotFather run remains the final proof).
- **Config↔schema consistency guard** `[ship]` — a test asserts every customer-facing descriptor maps to a
  real config knob in DEFAULTS (the UI can't show an unsettable knob; apply can't silently drop one).
  Truth-consolidation by construction — catches drift in the suite.
- **Shadow agreement / cut-over readiness page** `[ship/sell]` — `/shadow` shows the empirical agreement the
  shadow gathered on real data (overall + per-vertical: check-in/settle/…), via `comparison_stats_by_kind`.
  Gives the owner the data to DECIDE a per-vertical cut-over (the key gate) — and a sellable "watch the new
  system match your current one before you switch" story. + **recent mismatches** (live→new diff) so the
  owner sees WHAT differs + **data span** (how many days/comparisons gathered) + a per-vertical **cut-over
  suggestion** (✓ ready / ⏳ watching, heuristic ≥98% · ≥30 · ≥5d — owner's call) — the full cut-over
  criterion, actionable, on one read-only page.

### 🔍 Findings
- ⭐ **`secrets.py` shadows the stdlib `secrets` module** `[gotcha]` — it crashed werkzeug password-hashing
  (`import secrets` → no `choice`). Worked around with hashlib pbkdf2. WILL bite any library that imports the
  stdlib `secrets`. Renaming `secrets.py` is a big change (the global rule mandates it) → work around, don't fight.
- ⭐⭐ **The whole Telegram onboarding + the web channel are BUILT but UNVALIDATED end-to-end** `[needs-validate]`
  — mock-tested, wired to no live bot, reachable only via the tunnel. Validate on a real test bot before more.
- **Check-in vertical is shadow-READY** `[ship]` — the open mismatches were stale pre-grace-port artifacts
  (reconciled). A real cut-over candidate — owner's call, NOT flipped.
- **The "PLANNED" badge conflated "not built" with "live-but-not-config-driven"** `[ship]` — fixed with a 4th
  state **LIVE-FIXED**.
- **BotFather can't be automated** (anti-abuse) `[gotcha]` → guided creation + Bot-API auto-config is the path.
- **The shift-id / interval model gives overnight + split shifts FOR FREE** `[ship]` — a 2am check-in binds to
  the prior-day shift by construction; no date confusion (owner validated).
- **deep-merge replaces lists, merges dicts** `[gotcha]` → modelled `expertise.roles` as a list for clean
  add/remove; templates/accountant config merge cleanly.
- **Wizard deploys never touch the bots** `[ship]` — empty gm/core diff verified on every deploy; a clean
  isolation guarantee (only `twbshop-wizard` restarts).
- **Secrets must live OUTSIDE the readable config** `[ship]` — `core_org_secrets`, encrypted at rest (Fernet);
  activates when `ORG_SECRET_KEY` is set. Before public: also CSRF + HTTPS + login rate-limit (W3).
- **Accountant landmines F5/F6 FIXED** (atomic claim-by-construction); **B2B F2/F3/F4 = a ready plan**
  (HIGH-RISK money, with owner at re-enable) `[ship/decision]`.
- **Adding a domain to the wizard is now a known, cheap recipe** `[ship]` — config block + schema descriptors
  + a group + a customer section + 1 test (~20 min). Stock followed accountant 1:1. So POS/HR/marketing/
  delivery/rostering/CRM are quick to model when wanted.
- **Stock supplier price-compare = a PRIMARY goal** `[decision]` — modelled as a config knob
  (`supplier_price_compare`); keep per-item price + a canonical item path open (no vendor-only shortcut).
- **Config-section vs upsell duplicate** `[gotcha]` — a domain promoted to its own editable section was ALSO
  still listed in the "add more" upsell (catalog `live=False`). Fixed via `_CONFIGURABLE_DOMAINS` exclusion.
  Watch this whenever a catalog category becomes a config section.
- **What-if runs on the platform's OWN events** `[ship]` — `core.whatif` reads `attendance_events` + recomputes
  `verdict()` (the pure fn); read-only, self-contained per tenant, no live-TWB-data coupling. The pure verdict
  fn paid off again (reusable for previews).
- **The 5 unbuilt catalog domains belong as UPSELL, not config** `[decision]` — marketing/delivery/rostering/
  crm/payments are honestly "available, not built"; inventing config for them would be padding + a wrong model.
  Keep them as the upsell hook; promote to a config section only when actually built.
- ⭐ **Unchecked checkbox = absent (partial-form bool reset)** `[gotcha]` — an HTML checkbox sends nothing when
  off, so a partial Apply read "absent" as "off" and would mass-reset every bool to False. **The audit log
  SURFACED it** (it logged the spurious resets). Fixed with a hidden `_scope` field naming the bools the form
  carried → Apply flips only those. Applies to ANY checkbox form (retail/b2b/hire menus too — worth a look).
- ✅ **Live-bot menu audit (read-only): the bool-reset class is ABSENT** `[ship]` — swept retail/b2b/hire.
  Retail has NO settings/toggle menus (single-row INSERTs). B2B's `upsert_b2b_customer` already `COALESCE`-
  guards optional fields (the correct fix in place). Hire's `_update(intake_id, **fields)` only SETs the keys
  passed (safe by construction; all 17 call sites pass 1-3 changed fields). So the wizard fix needs NO porting.
  Adjacent (different class, already known): b2b money F2/F3/F4 (disabled, documented); hire counter races
  (low impact, not a flag reset). Verdict: 0 confirmed issues, 0 owner-review candidates.

### 🎴 Customer dashboard → task-card / completion redesign (owner idea, 2026-06-25)
Owner: the long category/sub-category lists feel heavy; show them as BOXES with a completion rate + a
rewarding 1-2-word name + the short reward each gives. Less reading, more ease. (Ref: Meta growth-tasks UI.)
- 🎁 **Cards = benefits, not categories** `[idea/sell]` — name each card by the OUTCOME ("Track your team",
  "Money sorted"), reward as a one-liner. The customer view then SELLS the product back to them — doubles as
  a demo/upsell surface. The single highest-leverage reframe of the idea.
- 🎁 **Gamified completion drives self-serve activation** `[idea]` — a progress nudge gets customers to finish
  setup; directly serves the North Star (stupid-proof self-serve wizard). Proven onboarding pattern.
- 🎁 **Locked modules become aspirational upsell cards** `[idea/sell]` — "🔓 Cut waste · Stock (Pro plan)".
- 🎁 **~70% of the data already exists** `[idea]` — `/setup` (N/5), health-check (warnings), per-domain config.
  The cards are mostly a PRESENTATION layer + a per-domain completion calc, not new logic. Cheap to prototype.
- 🔍 **Config ≠ tasks** `[gotcha]` — a knob (grace=5) isn't "50% complete". Completion fits SETUP steps +
  per-domain READINESS, never invented tasks to pad a %. Model it as setup-completeness, or it feels fake.
- 🔍 **Keep it professional, not cartoonish** `[gotcha]` — payroll/ops tool: subtle bars + benefit copy + a
  quiet "✓ ready", NOT confetti/"Quest complete!". The Meta tone is for casual social growth.
- 🔍 **Two audiences, one view** `[decision]` — cards = the "less reading" front door; the existing long-list
  config = the power-user drill-down behind each card. Keep BOTH; don't lose the depth.
- 🔍 **Reward copy is the real work** `[decision]` — the 1-2-word benefit names + ultra-short rewards per
  domain/task are a copywriting task (owner-led; I can draft a full set to shave).
- ✅ **Prototype BUILT + RANKED** `[ship]` — `/dashboard`: benefit cards + colour-shifting bars
  (grey→amber→teal→green) + REAL per-card progress, ALONGSIDE `/customer` (nothing replaced). **Owner restructure
  (2026-06-25): rank by REWARD-PER-EFFORT** — the highest-impact card (biggest cascade for least work) sits top;
  finishing it unlocks the most; done cards sink, next-biggest rises. **Module cards now show real N/M progress**
  (turn-on + each config step), not just on/off. Top card = "Track your team" (→ late-tracking·payroll·scheduling),
  the core that lights up the whole live system. Copy/value-weights are starter drafts to shave.
- 🎁 **Reward-per-effort ranking = activation engine** `[idea/sell]` (owner) — order cards so one small task
  cascades into many benefits ("finish the top → most happens"); the dashboard becomes a self-driving setup
  funnel that maximises the customer's first-win feeling. Each card's `value` weight is the tunable lever.
- ✅ **Dashboard is the customer LANDING** `[ship]` (owner, 2026-06-25) — `/customer` now serves the dashboard;
  the detailed long-list editor moved to **`/customer/config`** (module cards · "detailed view" · apply→saved ·
  cancel all point there; admin nav = ⚡dashboard + config). Card dashboard = front door, editor = drill-down.
  Tests repointed. `/dashboard` kept as an alias.
- 🎁 **Cascade copy wired** `[ship]` (owner, 2026-06-25) — each box has a **"what you unlock ›"** tap-reveal
  (native `<details>` → works desktop+mobile, doesn't clutter the grid; stop-propagation so it doesn't open
  the card) showing the CHAIN one task unlocks. 14 starter cascade lines drafted in `_CASCADES` (e.g. Connect
  bot → "staff clock in by phone · switches on every attendance feature below"). Sells the leverage on demand.
- 🎁 **Sticky category filter / index** `[ship]` (owner, 2026-06-25) — a sticky "All tools + named categories"
  bar (follows scroll, minimal height, horizontally scrollable) filters the boxes to one category → reach a
  setting fast. Ergonomics, not just looks. Un-folded the 6 capabilities into **~14 categorized task boxes**
  (each real completion, sub-steps gated on the module being on) so the filter is meaningful. JS-only filter
  (no reload). 🔍 the box set is the lever for "what shows where"; more boxes = more filter value.
- 🎁 **Stable grid + "Do this next" spotlight** `[ship]` (owner refinement, 2026-06-25) — the BEST pattern:
  grid order is FIXED by value (never reshuffles → muscle-memory to find/re-tweak anything, even at 100%), and
  a top **👉 Do this next** box surfaces the 3 biggest incomplete wins as one-click chips (the funnel, without
  moving the layout). Done cards stay put (show the win) but drop out of the spotlight. Becomes "✓ all set up"
  when nothing's left. (`dashboard_cards` returns `cards` [stable] + `next` [top-3 incomplete].)
- 🎁 **Colour-shifting progress bars** `[idea]` (owner) — the bar changes colour the closer to 100%/5-5
  (e.g. red <34% → amber → teal → green at done), so the customer reads the whole dashboard at a GLANCE by
  colour — exactly the "less reading" goal. 🔍 pair colour WITH the number (5/5) not colour alone
  (colour-blind safe); keep the palette calm (no harsh red — a soft amber→green reads as "progress", not "error").

### 🧭 Card restructure — strategy + competitive read (2026-06-25)
What emerged from the dashboard restructure, and how it sits vs what other services give clients.
- 🎁 **The card/checklist IS the industry-standard activation pattern** `[ship]` — Shopify setup guide, Stripe
  activation checklist, Meta growth tasks (the ref), Square, Notion/Linear getting-started. We're adopting a
  PROVEN, familiar UX → low risk, instantly legible to anyone who's used a modern SaaS.
- 🎁 **Our PERSISTENT stable dashboard > the norm** `[sell]` — most tools HIDE the setup guide once you're done
  (Shopify dismisses it), then bury settings in menus. The owner's "stable order, always there, re-tweak
  anytime + a spotlight for what's next" keeps it as the permanent home → genuinely MORE ergonomic than the
  typical vanishing onboarding checklist. A differentiator, not a copy.
- ⭐ **BIG IDEA — the evolving card (setup-task → live widget)** `[idea/sell]` — a card you finish at 100% can
  FLIP from "set me up" to a live status tile ("Track your team → 12 in · 1 late today"). Most products split
  a SETUP view from an OPERATING dashboard; ours could be ONE surface that grows with the customer. Closes the
  gap below and is a strong, ownable design.
- 🎁 **In-card contextual upsell = an integrated marketplace** `[sell]` — the locked module cards ("turn on
  Stock — Pro") upsell in context, where the value lands. Shopify/Square use separate app stores + pricing
  pages; contextual in-card upsell converts better and avoids app-store fragmentation.
- 🎁 **Cascade copy = value/outcome onboarding** `[sell]` — framing a step by what it UNLOCKS (not the feature)
  is the Stripe/Slack playbook; the "one task → many things" leverage is the strongest activation lever.
- 🔍 **Market position: we're BROAD; most rivals do 1-3 dimensions** `[decision]` — Deputy/Homebase/When-I-Work
  = workforce only · QuickBooks/Xero = accounting only · Square/Toast/Lightspeed = POS-first (+some stock) ·
  Gusto/Rippling = HR/payroll (Rippling broadest, but enterprise/Western). Few do the WHOLE shop (attendance +
  accounting + stock + POS + HR + back-office) for an SMB — our breadth-in-one is rare at this segment.
- 🔍 **Telegram-native = a distribution moat** `[sell]` — nearly every competitor assumes a dedicated app/web
  login; SMBs (esp. SE-Asia) resist adopting yet another app. Meeting them on a channel they ALREADY live in
  is a real edge most can't easily copy.
- 🔍 **Shadow-run cutover is rare** `[sell]` — most tools are rip-and-replace; "run beside your current way,
  prove it, then switch" de-risks the scariest part of changing systems.
- 🔍 **GAP/opportunity — we have a SETUP dashboard, not an OPERATING one** `[idea]` — once configured, customers
  expect a "today" view (who's in, sales so far, low-stock, cash). The evolving-card idea (above) is the
  cleanest way to deliver it without a second surface.
- 🔍 **What to BORROW from the leaders** `[idea]` — micro-interaction polish (Linear/Stripe) · reporting/
  analytics depth (QuickBooks/Toast) · a native app (everyone) · eventual third-party extensibility (Shopify
  app store) · in-app contextual help/docs (Intercom/Pendo). Ours wins on breadth + channel + ergonomics;
  these are where the polished incumbents are ahead.

### 🏗️ Build update + Salesforce/ServiceNow (2026-06-25)
- ✅ **Evolving card BUILT** `[ship]` — `core.attendance.today_summary` + a **"🟢 Live today"** tile on the
  dashboard (N in · M late) that appears once there's activity — the setup→operating FLIP, proven. Generalises:
  each set-up domain gets a live tile (attendance first, real data).
- ✅ **Dashboard e2e coherence test** `[ship]` — one test walks the whole flow (industry template → plan
  locks/unlocks → enable module + sub-option from the card → dashboard reflects → reports) so the now-complex
  dashboard can't silently regress.
- ✅ **Card master enable** `[ship]` (gap I found) — each card's inside now has a master "this module is ON/OFF"
  toggle (not just sub-options), so the card is the module's CONTROL CENTER: turn it on, configure its options,
  set the AI tier — all in one place. (`_CARD_ENABLE` per card; saved + audited via the card form.)
- ✅ **AI-power tier surfaced** `[ship]` — the owner's "Computer / AI Power" tier (computer · ai · mixed,
  per-decision rules-vs-model) is now selectable on the AI assist card (saves `ai_power`, audited). The
  AI-power concept is now configurable, not just modeled.
- ✅ **Templates set the plan** `[ship]` — picking an industry (bakery/cafe → Ops · retail → Back-office) now
  also sets the package, so the dashboard immediately shows the right active cards. Ties templates + packaging
  → genuine one-click industry setup.
- ✅ **Packaging / lean-per-client BUILT** `[ship/sell]` — the dashboard package-gates: in-plan cards stay
  active, out-of-plan show **🔒 locked** (upsell → `/packages`); locked cards don't count toward progress/
  spotlight. A `/packages` page (each plan · what it unlocks · switch). Switching the plan adapts the
  dashboard live — "a client only sees their slice" made real (attendance · ops · back_office · total).
- ✅ **Planned options BUILT OUT → toggles** `[ship]` (owner: "build out the planned options next") — 15 planned
  options across accountant (expense-categories · invoices · reconciliation · financial-reports) · stock
  (item-catalog · purchase-orders · stock-movements) · pos (product-catalog · discounts · refunds · cash-drawer)
  · hr (wage-structures · pay-runs · deductions) · coverage (warnings) are now real `tenant_config` flags +
  on/off **toggles** on each card's inside page (save → config, audited, whitelisted to non-LIVE knobs;
  behavior follows per option). The card insides are now CONFIGURABLE surfaces, not just menus.
- ✅ **Per-card "inside" pages BUILT** `[ship]` (owner: "many cards show the same settings") — every domain +
  frontier card now opens **`/card/<key>`** = its OWN industry-standard menu of options (built/planned/idea
  badges), not the generic editor. `wizard/card_details.py` = ~80 standard options across 11 capabilities,
  ref'd to QuickBooks/Xero · Square/Toast/Loyverse · Deputy · Gusto/Rippling · Salesforce/ServiceNow · Shopify.
  It's the REVIEW MENU: owner takes a round turn, marks what to wire. The 5 remaining frontier cards (AI assist,
  Automations, Learn, Marketplace, Mobile app) now each have a real inside too — "build out the rest" done as
  option-menus (full functional builds follow once the owner picks from the menu).
- ✅ **HARVEST Phase 1 SHIPPED — tamper-evident audit hash-chain** `[ship/sell]` — first POSBusiness harvest, into
  `core/audit.py` (re-derived for psycopg2, **re-tested from scratch** — its design was ChatGPT-planned). Each
  audit row carries `entry_hash`=SHA-256(canonical) + `previous_hash`=prior row's hash (per-org chain, genesis
  `0*64`) → content edits AND row deletions are detectable; `verify_chain` re-walks it (PASS/FAIL). `core_audit`
  table; `log_config_change` now writes the chained mirror; `/audit` shows "🔗 Tamper-check: PASS/FAIL"; a
  `verify_audit_core` CLI. Adversarial pass → a **per-org advisory lock** (no fork under concurrency) + honest
  limits (JSON-safe changes; full re-chain needs the external **anchor = Phase 1b**). 6 tests. The harvest
  pattern is proven: reference an external design → adapt to our stack → re-prove with our own tests.
- 🔍 **Fin.ai competitor read + lean borrow** `[sell/decision]` (owner asked) — Fin = Intercom's AI customer-support
  *agent* (resolves support convos across chat/email/voice, grounded in docs, takes actions via "Procedures";
  patented RAG; outcome-priced $0.99; ~65% resolution; **50+ updates/yr**). Different category from us (a *feature*
  vs our *platform*), but the "simple front / deep back" framing is exactly our dashboard philosophy. **Our edge:**
  AI grounded in LIVE OPS data (not docs), Telegram-native, whole back-office, lean. **Borrow leaner, ranked:**
  ① "Ask your business" (NL over our real data — DONE below) · ② Automations (plain-words trigger→action, the
  leaner "Procedures") · ③ an "optimize" view + an outcome metric ("X% handled automatically"). Don't chase their
  breadth (big team, years) — borrow the *playbook*.
- ✅ **"Ask your business" assistant — computer-tier + ai-tier** `[ship/sell]` — `core/ask.py`: a NL question →
  a real answer over the tenant's OWN data (attendance · stock · sales · expenses · payroll · shrinkage · needs-
  attention). COMPUTER tier = a keyword intent-router straight to the existing reports/insights functions (NO API
  cost); unmatched questions stay off the model unless the tenant's AI-power is ai/mixed, then it escalates to
  Haiku (`ai_client.ask_business`, grounded in a data snapshot). Dashboard ask-box + `/ask` page. The single
  leanest Fin-borrow — the structured answers already existed, we just added the natural-language front door. 3 tests.
- ✅ **HARVEST Phase 2a SHIPPED — POS till / cash-drawer money model** `[ship/sell]` — `core/till.py` (shifts ·
  cash drawer · Z-report) harvested from POSBusiness `shift_service`, adapted to cash-only, re-tested on real rows.
  **State-Integrity Laws proven:** S3 atomic one-open-shift claim (partial-unique `uq_one_open_shift` → 2nd open
  rejected by the DB, not a race) · S2 idempotent close (flip-status-first) · S4 `expected_cash = float + drawer
  events` · variance-reason gate (≥ $2 needs a note). `core_shifts`/`core_cash_events` + `shift_id` on sales + a
  `/till` UI (open→sell→events→close→Z-report). All shift events → the audit chain. 6 tests. **2nd-opinion findings
  (recorded):** float→Decimal when 2b adds tax/discounts · audit in a separate txn (atomic-audit = a clean
  hardening). Money LOGIC correct + proven; the deepest, most dangerous harvest slice, shipped safely.
- ✅ **HARVEST Phase 1b SHIPPED — external audit anchor** `[ship/sell]` — `core/audit_anchor.py` appends each org's
  chain head to a JSONL file OUTSIDE Postgres (HMAC-signed if `ANCHOR_HMAC_KEY` set) → catches the one thing the
  in-DB chain can't: a DB-admin who rewrites AND re-chains the whole log (a re-chain erases the old anchored heads
  → `verify_anchors` FAIL). `scripts/anchor_audit.py` (cron) + `verify_audit_core.py --anchors`. 3 tests
  (anchor+verify · full-re-chain→FAIL · HMAC file-tamper). Ops to activate: `ANCHOR_DIR` off-host + `ANCHOR_HMAC_KEY`
  in secrets + nightly cron + offsite copy. **Both audit tamper-layers now exist** — production-grade auditability.
- ⚠️ **FINDING — new files need `gen_map_index` + plan docs need the doc-refs DENY** `[gotcha]`: the Phase-1 gate
  caught 2 fails — a stale `MAP_INDEX.md` (added `core/audit*.py` without regenerating) and `test_doc_refs` flagging
  the harvest plan's cross-repo/forward paths. Fixes: run `scripts/gen_map_index.py` on any file add; a plan that
  cites another repo's files goes in the doc-refs `DENY` set. (Both guards did their job.)
- 🔍 **POSBusiness = a harvest goldmine** `[sell/decision]` — the owner's *other* project (`aaaeeeaaarrr/POSbusiness`)
  is a near-production full-stack POS far deeper than our sales-log: hash-chained tamper-evident audit (+ external
  anchor), shifts/Z-report/drawer-reconcile/cash-variance-gates, refunds/voids/credit-notes, ABA PayWay/KHQR
  (sandbox-verified), offline-first (IndexedDB queue + idempotency), ESC/POS printers, RBAC, 652 backend + 60
  Playwright tests, 12 migrations, full go-live pilot docs. **Owner's prior criticism FOUND** (its `advisor-round.md`
  §5): the GUI is *"clean but shallow — an average POS"* → resolved "evolve don't rewrite" (UI = cheap layer,
  backend = the moat). **Decision: HARVEST into `core/`, don't merge** (two stacks; FastAPI/SQLAlchemy vs our
  psycopg2 config-core) — and **re-test from scratch** (it was planned by ChatGPT + tested for ITS stack; we
  re-prove on ours). Plan → `docs/POSBUSINESS_HARVEST_PLAN.md`; **audit hash-chain is Phase 1** (self-contained,
  no money, upgrades our security/auditability LAW).
- ✅ **Repeat-pattern correlation** `[ship/sell]` — `investigate.repeat_offenders` tallies who was on shift
  across ALL stock shortfalls → ranked; a "🔁 Repeat presence at shortfalls" box on `/investigate`. The signal:
  one name at the top of several shortfalls = look closer. The cross-domain edge, made into a lead.
- ✅ **Unattended / after-hours detector** `[ship/sell]` — `investigate.unattended_activity` flags sales/counts
  recorded when **no one was clocked in** (~16h-before window) → a 🌙 section on `/investigate` + an
  attention-feed alert. The off-the-books / after-hours catch.
- 🟢 **FINDING — dev↔DB DNS blip (resolved)** `[gotcha]`: mid-session the dev machine lost DNS (couldn't resolve
  github.com OR the managed-PG host) → couldn't push/gate/deploy for ~minutes. Held (didn't pile up un-gated
  commits); recovered on retry. The deployed wizard was unaffected (it's on the DO network). Lesson: a dev-side
  DNS outage blocks all of push/gate/deploy at once — wait it out, don't deploy un-gated.
- ✅ **Shrinkage → SUSPECT LIST (owner's original idea, fully realized)** `[ship/sell]` — `stock_variance` now
  carries the window [prior count → this count]; `investigate.who_in_window` names who was on shift in it; the
  shrinkage alert AND the `/investigate` shrinkage box now show **"on shift: [names]"**. So a shortfall →
  the time + the suspects → straight to the camera. Exactly "who was available / in-charge."
- ✅ **STOCK-VARIANCE / SHRINKAGE detector BUILT (the killer investigation)** `[ship/sell]` — `record_count` now
  captures **`book_before`** (the system's on-hand the instant before a physical count overwrote it = last count
  + receipts − sales); `stock.stock_variance` flags any item whose latest count came up **short of the book**
  (counted < book = theft/waste/error) with the variance + when. Surfaced in the **"needs attention" feed** AND a
  **⚠️ Shrinkage section on `/investigate`**. Turns "something feels off" into "Gin short by 5 on [date]" → drill
  into its history + who was on shift → camera. *Schema:* 1 additive column. (A matching recount clears the flag.)
- ✅ **INVESTIGATION card BUILT (forensic / loss-prevention)** `[ship/sell]` (owner idea) — `/investigate` +
  `core/investigate.py`: **who was working on a day** (camera-check anchor) · **item timeline** (when an item was
  last counted/sold + by whom) · **cross-domain activity feed** (last 48h of check-ins/counts/sales/expenses,
  newest first). + **actor tracking** added (`actor` on counts/sales/expenses, threaded from the logged-in user)
  so actions name a person, not just a time. A dashboard card. Purpose: pinpoint WHEN + WHO → jump to the camera
  fast, without scrubbing hours of footage.
- 🔎 **More investigation ideas (owner asked — the menu)** `[idea]`: **stock variance / shrinkage** (counted vs
  expected = last count + receives − sales; a negative gap flags theft/waste + the window to review — the killer
  one) · **voids / refunds / discounts log** (the classic POS shrinkage vector — who, when, how much) · **cash
  drawer over/short** (counted vs expected by shift/person) · **after-hours / off-shift activity** (a sale or
  count when no one should be working) · **config / price / salary change audit** (we have `core_config_audit`;
  surface it) · **large/unusual outliers** (a huge expense, a suspiciously big discount) · **repeat-pattern
  correlation** (same staffer on shift at EVERY shrinkage event — the cross-domain edge) · **no-sale / drawer-
  open** events · **edit/delete-after-the-fact** log.
- 💼 **Competitor read — loss prevention is a whole industry** `[sell]`: **Solink · Envysion · DTT · Interface ·
  March Networks** = POS-transaction + VIDEO (a flagged event → the camera clip at that timestamp — EXACTLY this
  card, productized; Solink lets you search "every void > $20 + its clip"). **Lightspeed/Toast/Square** =
  built-in exception/void/refund/discount-by-employee reports. **Restaurant365 · MarketMan** = inventory
  variance / waste / shrinkage. **ServiceNow · Salesforce** = audit trail / field history. **OUR EDGE:** we hold
  attendance + stock + sales + expenses together, so we answer **cross-domain** ("who was on shift when this
  stock went missing") that single-domain video-POS tools can't. **Future bonus:** store a camera deep-link per
  zone → an alert/event links straight to the clip (be Solink, lean — we give time+who, they keep their own DVR).
- ✅ **Reorder loop closed (2nd cross-domain link: stock↔accountant)** `[ship]` — `stock.receive_purchase`
  restocks an item AND logs the cost as a `stock` expense in ONE transaction; a "📥 Receive a purchase" form on
  `/stock`. Closes the low-stock → reorder → received → restocked + expensed loop (the "needs attention" feed
  flags it, this acts on it).
- ✅ **CROSS-DOMAIN intelligence layer** `[ship/sell]` — `core/insights.py` `attention_feed` scans every ON
  domain for notable conditions (lateness spike · stock at/below par · spend spike · sales drop) → one **"Needs
  attention"** feed on the AI card + a **dashboard banner** (⚠️ N need attention). The 5 real domains now feed
  proactive cross-domain insights, NO model cost. Extends the AI-assist anomaly check across all domains.
- ✅ **LIVE operating dashboard (all 5 domains)** `[ship/sell]` — the "🟢 Live now" strip (`_live_tiles`) shows
  REAL status per ON domain: attendance (in/late today) · stock (items/low) · expenses ($ 30d) · sales ($ 30d)
  · payroll ($ last run). The dashboard is now a **live multi-domain operating view**, not just a setup
  checklist — the owner's "evolving card" vision realized across all 5 real domains.
- ✅ **PAYROLL domain made REAL → ALL 5 domain cards now real + Reports → 5** `[ship/sell]` — `core/payroll.py`
  + `core_pay_runs`/`core_payslips` + `core_staff.monthly_salary` (ALTER) + a `/payroll` manager (set salaries →
  run a pay run → a payslip per active staffer → view runs/payslips) + a **💼 Payroll** section in `/reports`.
  The HR card opens it. **The platform now has 5 real working domains (attendance · stock · accountant · pos ·
  payroll) + unified 5-domain Reports + a cross-domain integration.** *Schema:* 2 tables + 1 column (init_core_db).
- ✅ **POS domain made REAL + cross-domain (sale → decrement Stock) + Reports → 4** `[ship/sell]` —
  `core/pos.py` + `core_sales` table + a `/pos` manager (record a sale → revenue, **auto-decrementing the
  item's Stock on-hand** — the first cross-domain integration) + a **🛒 Sales** section in `/reports`. 3rd
  non-attendance domain; the POS card opens it. Now Reports spans attendance · stock · expenses · sales.
  *Schema:* 1 additive core table (init_core_db).
- ✅ **ACCOUNTANT domain made REAL (expense log) + Reports → 3 domains** `[ship]` — `core/expenses.py` +
  `core_expenses` table + a `/expenses` manager (record by supplier/category · spend summary · by-category ·
  recent) + a **🍚 Expenses** section in `/reports`. The 2nd non-attendance domain; the Accountant card opens
  it. Shadow-style (own table, not TWB's live accountant lane). *Schema:* 1 additive core table (init_core_db).
- ✅ **Multi-domain Reports** `[ship]` — `/reports` now shows a **📦 Stock** section (items · low · $value +
  low-stock list, link to manage) alongside attendance, when stock is on. The Reports vision (all domains in
  one place) realized across 2 real domains — sales/expense slot in the same way as they record data.
- ✅ **Stock PRICE-COMPARE (the PRIMARY goal, real)** `[ship/sell]` — `core_stock_prices` + `add_price` /
  `item_prices` / `cheapest_overview` (cheapest supplier per item) + a "💲 Price compare — cheapest supplier"
  section + add-price form on `/stock`. The owner's "buy from the cheapest" made real on the platform (per-
  supplier price trend/history is the data; cross-supplier cheapest is shown).
- ✅ **Stock VALUE (unit cost)** `[ship/sell]` — per-item `unit_cost` (idempotent ALTER) → stock **value**
  (Σ on-hand × cost) + a summary line (items · low · $value) on `/stock`. Toward the owner's "prices = PRIMARY
  goal" (per-supplier price compare is the bigger next piece — needs a suppliers/prices table).
- ✅ **STOCK domain made REAL (1st non-attendance domain)** `[ship]` — `core/stock.py` (item catalog · par
  levels · stock counts · low-stock reorder list) + `core_stock_items`/`core_stock_counts` tables + a `/stock`
  manager page (gated by `categories.stock.enabled`; the Stock card opens it). **Shadow-style: its OWN tables,
  NOT TWB's live stock** (`gm_bot/stock.py` untouched). Proves the platform can grow a real domain beyond
  attendance. *Schema:* 2 new additive core tables, created idempotently by `run_wizard.py`'s `init_core_db()`.
- ✅ **AI assist made REAL (anomaly check)** `[ship]` — `core.reports.attendance_anomalies` (pure statistics
  over attendance: lateness-spike + low-turnout vs the trailing baseline, NO model cost) surfaced on the AI card
  as a **"🔔 Live anomaly check"**. The first AI-assist feature actually working (computer-tier; the model tiers
  are the upsell). Depth, over data we already have.
- ✅ **Roadmap / idea-overview page** `[ship]` (owner: "good to give me more ideas") — `/roadmap` lists every
  option across all 11 cards grouped by status (✓ built · planned · ideas) — the whole idea menu in one scan,
  linked from the dashboard. Reads the static catalog (no tenant data).
- ✅ **Frontier sub-options WIRED (preview)** `[ship]` (owner: "have the frontier sub-options too — good to give
  me more ideas") — all 28 frontier-card sub-options (reports · ai_assist · automations · learn · marketplace ·
  mobile_app) wired as preview toggles via a `frontier_options` config block. **Now EVERY card option (domain +
  frontier) is switchable — "wire it all in" is 100% complete**, and the card insides double as an idea menu.
- ✅ **Idea options WIRED as "preview" toggles** `[ship]` (owner: "wire all things in, I'll switch off") — the 8
  domain idea options (tax/VAT · multi-currency · barcode · recipes/BOM · valuation · tables · contracts/e-sign
  · auto-schedule) are now `tenant_config` flags + toggles on their cards, marked **"idea — preview"** (honest:
  switchable but not a ready feature). Now EVERY domain card option (built/planned/idea) is switchable.
  *Remaining:* the FRONTIER-card sub-options (AI/automations/learn/…) need a structured frontier-options pass.
- ⚠️ **`max(..., default=1)` ≠ floor** `[gotcha]` — `weekday_pattern` always returns 7 rows, so an org with NO
  check-ins gives `max([0,0,…])==0` (default only applies to an EMPTY list) → `/reports` divided by zero (500).
  Fixed with `max(...) or 1` + a `test_reports_empty_org_no_crash` guard. **Caught by the dashboard e2e** (its
  org has no check-ins) — the value of the coherence test, proven on its first real run.
- ✅ **Reports — by-weekday pattern** `[ship]` — `core.reports.weekday_pattern` + a "By weekday" section
  (check-ins + lateness per weekday, Mon→Sun) — a staffing-pattern view (busy/late-prone days). Reports now =
  daily trend · per-staff punctuality · by-weekday · selectable period · CSV export.
- ✅ **Reports CSV export** `[ship]` — `/reports/export?days=N` downloads the daily trend + per-staff data as a
  CSV (a real report-feature; QuickBooks/Salesforce export lineage). Export link on the page.
- ✅ **Reports made REAL (2nd report type + period)** `[ship]` — added `core.reports.staff_attendance_report`
  (per-staff punctuality — who's late most, on-time% per staff, names from `core_staff`) + a **selectable
  period** (7/14/30 days) on `/reports`. Reports now = daily trend + per-staff, period-controlled, from data we
  already have. Expense/stock/sales reports follow as those domains record data.
- ✅ **Reports — first frontier card BUILT OUT** `[ship]` — `core.reports.attendance_report` + a `/reports`
  page: daily attendance trend (check-ins · late · on-time %) with colour-graded volume bars (greener = fewer
  late). The Reports card now links there. Expense/stock/sales reports slot in beside it as those domains
  record data. Read-only; the pattern is set for the rest.
- ✅ **Frontier capabilities WIRED IN (off)** `[ship]` — `tenant_config.frontier` flags + 6 dashboard cards in a
  **"Coming soon"** category: Reports & trends · AI assist · Automations · Learn · Marketplace · Mobile app.
  Owner sees the FULL breadth + where the shop is 0% (all off today); flip on per client when ready (owner's
  "build early, evolve switched-off, unleash when right").
- 🔍 **Salesforce/ServiceNow — what's worth taking** `[idea]` (owner asked):
  • Salesforce **Reports & Dashboards** + ServiceNow **Performance Analytics** → our **Reports & trends** (over-time).
  • Salesforce **Einstein** + ServiceNow **Now Assist** → **AI assist** (suggestions/anomaly alerts; we have AI tiers).
  • Salesforce **Flow** + ServiceNow **Workflow** → **Automations** (customer's own if-this-then; our bot-rule is the seed).
  • Salesforce **Trailhead** → **Learn** (gamified in-app how-tos — sits right beside our cards).
  • Salesforce **AppExchange** + Shopify store → **Marketplace** (extensibility/add-ons).
  • ServiceNow **Service Catalog** → our module cards ALREADY are this (formalise later).
  • ServiceNow **CMDB** (single source of truth) → our entity+event model ALREADY is this.
  • ServiceNow **SLAs/escalations** → our AL re-ping ladder ALREADY is this. (So several are done; the new ones
    are Reports/AI/Automations/Learn/Marketplace/App — now scaffolded off.)
- ⭐ **LEAN- for-broad-clients principle** `[decision]` (owner) — breadth lives in the ENGINE; the SURFACE stays
  lean per client via (1) package gating (show only what their plan/type includes), (2) the sticky filter,
  (3) progressive disclosure (card → drill-down → cascade), (4) the spotlight (one next thing). The more we
  wire in, the more these keep a given client's view simple. **A client only ever sees their slice.**

### ⏸ PARKED — owner will review after seeing the whole thing (2026-06-25)
Sensible defaults are live; these wait for the owner's eyes on the full build, then comment:
- **Wire TWBshop's real live data into the dashboard** — do AFTER the setup is complete enough (owner's call),
  so the dashboard mirrors TWB's actual shop (real staff, today's real check-ins), not just platform-migration.
- **Shave the copy** — the card names + 20 cascade lines (all my drafts).
- **Tune the dials** — `value` weights (ranking) + colour thresholds + which frontier cards to flip on.
- **Packaging** — which cards show for which client type/plan (so "lean per client" is real per segment).
- **Build out the other frontier cards** — AI assist · Automations · Learn · Marketplace · Mobile app (Reports
  done first; the rest follow the same pattern when wanted).

### 📌 Owner decisions still open (for review)
- Company **name** (shortlist in `docs/COMPANY_NAME_IDEAS.md`) · **cut over** check-in · **B2B re-enable** ·
  set **`ORG_SECRET_KEY`** · public hosting + W3.
