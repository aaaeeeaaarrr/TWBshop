# Bonuses & Findings — running ledger

> **Standing practice (owner, 2026-06-23):** as we build, ALWAYS append the **bonuses** (unexpected wins,
> sellable angles, leverage) and **findings** (discoveries, gotchas, decisions) here — capture everything,
> shave/improve later. This is the home; one line per item + a tag. Newest section on top.

Tags: `[ship]` shipped/true · `[idea]` worth doing, not built · `[sell]` a sellable angle · `[gotcha]`
a trap to remember · `[needs-validate]` built but unproven · `[decision]` a choice made.

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
