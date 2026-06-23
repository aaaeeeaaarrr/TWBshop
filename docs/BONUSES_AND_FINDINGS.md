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

### 📌 Owner decisions still open (for review)
- Company **name** (shortlist in `docs/COMPANY_NAME_IDEAS.md`) · **cut over** check-in · **B2B re-enable** ·
  set **`ORG_SECRET_KEY`** · public hosting + W3.
