# Bakery Automation System — Project Rules & Status

---

## Real-Path Precision Standard — UNIVERSAL, ENFORCED (full local copy — self-contained)
REAL_PATH_PRECISION_STANDARD_VERSION: 2026-06-08-A

> This is a FULL copy (not a pointer) so the project carries its own enforcement even if the global
> `~/.claude/CLAUDE.md` fails to load, is stale on another machine, bootstrap wasn't run, the secrets
> repo is unavailable, or a future session only sees this repo. Reliability > elegance for operating
> constraints. Same text lives in the global file.

Not values — constraints. The bar is EVIDENCE, never promises ("100% precision" as a slogan is
banned). Keep the chat style fast and friendly; never let that soften proof on real work. The user
may demand the evidence block at ANY time; its absence = NOT done. Words are not trusted — only evidence.

### MODES — pick by what the task touches. If it isn't clearly CHAT or TRIVIAL, default UP to SHIPPABLE.
- **CHAT / THINKING** — explaining, planning, questions, reviews. Fast, no ceremony.
- **TRIVIAL EDIT** — comments, wording, formatting, docs; CANNOT change runtime behavior. Light
  proof: files changed + a quick check.
- **SHIPPABLE CODE** — any behavior / UI / API / DB / Telegram-bot / report / deploy change. FULL
  real-path evidence required before saying done.
- **HIGH-RISK** — money, payments, payroll, staff/customer records, audit logs, deletions, DB
  migrations, permissions, irreversible writes, production deploy, external integrations. No
  shortcuts, no "probably," no done without real-path proof.

### HARD RULES
1. **Real system only — NO BEHAVIOR FORK.** Test the SHIPPED path. Isolate data/users/routing/env/
   test-records; NEVER fork logic, permissions, validation, or UI/API/DB/message paths. A preview/
   mock/stub/shortcut is not proof unless the real path also passed.
2. **No fake success.** Never say done/fixed/working/ready without running the real path and showing
   evidence to the depth the mode requires.
3. **PUSHED ≠ LIVE.** Server/service code: same turn → commit+push → deploy (pull) → restart →
   VERIFY (deployed ref == origin, service up, running artifact actually contains the change).
4. **Never blame state you can verify.** When something "isn't showing," verify the deployed/running
   state YOURSELF first — no "maybe a restart/pull/sync."
5. **Files are truth; chat is disposable.** Persist decisions/specs/results to repo files as you go;
   a restart or compaction must lose nothing; prove safety from git, don't reassure vaguely.
6. **User-path first + every actor's view.** Exercise the path the real actor uses (button, Telegram,
   screen, report, approval); surface every recipient's output so all are visible. Backend-only proof
   is NOT enough for a user-facing feature.
7. **No dead buttons.** Every action does the real thing, or faithfully advances to its real
   consequence via the real code path.
8. **Exact, reversible isolation + teardown.** Test writes tagged, reversible, cleaned EXACTLY; never
   pollute real data; never wipe-and-forget.
9. **Test once → ship the same code.** Go-live only flips routing/config, never behavior. If code
   changes after the test, re-run the real-path test.
10. **Cover the whole surface + every branch** (success/fail/cancel/invalid/permission/duplicate/edge)
    — ONE harness PER WORKFLOW, not one monster harness.
11. **Fixes become permanent guards** — a fixed bug gets a regression test/constraint/validation.
12. **Shortcuts: default to the correct real-path implementation.** In HIGH-RISK, none. Elsewhere,
    state the tradeoff + real-path alternative FIRST. Never make the user repeat themselves.
13. **Don't ask unless needed — but report assumptions + evidence AFTER acting.** Ask only when truly
    ambiguous or HIGH-RISK; otherwise proceed real-path and state what you assumed and proved.
14. **Verify inputs against context** (translations, data, suggestions); flag mismatches BEFORE applying.
15. **Report faithfully.** For SHIPPABLE / HIGH-RISK, end with: files changed · commands run · real
    path verified · evidence (logs/DB/output) · cleanup · regression guard · remaining risk · next step.

### TWBshop HIGH-RISK paths (no shortcuts, real-path proof mandatory)
- Payments / KHQR / Bakong · payroll & salary (staff_registry, slips, pays) · staff records &
  ex-staff offboarding / bans / permissions · DB migrations & deletions · deploys to the twbshop-*
  services (retail / b2b / gm / listener / hire) · attendance go-live (`attendance_live`).
- Attendance test harness design: `docs/ATTENDANCE_TEST_MODE.md`.

---

## Connectivity Reference (run only when something seems broken)

| # | What | Check command | Good result |
|---|------|--------------|-------------|
| 1 | SSH — server | `ssh twbshop "echo ok"` | `ok` |
| 2 | GitHub push access | `git ls-remote origin` | lists refs |
| 3 | DigitalOcean API | `curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $DO_API_TOKEN" https://api.digitalocean.com/v2/account` | `200` |
| 4 | DO Droplet | `curl -s -H "Authorization: Bearer $DO_API_TOKEN" https://api.digitalocean.com/v2/droplets \| python3 -c "import sys,json;d=json.load(sys.stdin);print(d['droplets'][0]['status'])"` | `active` |
| 5 | DO Database | same but `/v2/databases` | `online` |
| 6 | Anthropic API | `curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" https://api.anthropic.com/v1/models` | `200` |
| 7 | Telegram retail | `curl -s "https://api.telegram.org/bot$BOT_TOKEN/getMe"` -> `.result.username` | `WineB_bot` |
| 8 | Telegram B2B | same with `$B2B_BOT_TOKEN` | `twb_b2b_bot` |

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

## After Every Pull

**Read the "Current Status" section of this file immediately.** It is the only source of truth for what to work on next. Never use memory notes — they are local to one machine and go stale across machines.

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

---

## Tech Stack
- **Language:** Python 3.11+
- **Telegram:** `python-telegram-bot` library
- **Database:** PostgreSQL on DigitalOcean (managed) — `psycopg2`, connection via `DATABASE_URL` in secrets.py
- **Fuzzy Matching:** `difflib` (standard library)
- **Logging:** `RotatingFileHandler` — 5MB cap, 3 backups. Unmatched orders log to `logs/unmatched.log`

---

## Repo Structure
One repo, one business. Each system gets its own folder. Shared infrastructure lives in `shared/`.

```
TWBshop/
├── CLAUDE.md                   ← project-wide rules and status
├── config.py                   ← tracked in git; imports secrets from secrets.py
├── config.example.py           ← reference template
├── requirements.txt
├── run_bot.py                  ← retail entry point
├── run_b2b_bot.py              ← B2B entry point
│
├── shared/
│   ├── database.py             ← PostgreSQL: all tables and queries
│   └── ai_client.py            ← Anthropic client (vision + text)
│
├── telegram_bot/               ← retail bot
│   ├── bot.py                  ← handler registration and scheduled jobs
│   ├── orders.py               ← order intake, menu matching, confirmation flow
│   ├── menu.py                 ← menu items, aliases, synonym tables
│   ├── summaries.py            ← production totals and fulfillment lists
│   ├── photos.py               ← photo receiving, storage, AI analysis
│   ├── staff_monitor.py        ← staff message logging and AI monitoring
│   └── reminders.py            ← missing photo deadline checks
│
├── b2b_bot/                    ← B2B wholesale bot (see section below)
├── deploy/                     ← systemd service files + server setup script
├── archive/                    ← removed code kept for reference
├── photos/                     ← shared photo storage (gitignored)
└── logs/                       ← shared logs (gitignored)
```

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

## REPORT Finance Tracking (GM bot) — LIVE
TWB REPORT group (chat_id in Connectivity). Business day 06:00→06:00; ~16:00 mid + ~05:00 final report.
GM parses each report, recomputes the drawer (600 + cash in − cash out; Over/Lost = count − expected),
flags Lost>$2 in-group + opens a clarification, DMs owner anomalies. FX margin (4000 riel=$1) → a small
"Over" is EXPECTED, never flag. Level-1 reconciliation LIVE (cash sheet / POS / ABA vs report).
OPEN (remind owner): #1 overexpense-carryover model (deficit carried to next day off the $600 float —
owner wants cleaner). Sales-anomaly framework built; activates once years of FB Messenger reports import.
Full decoded format + resolved decisions → docs/HISTORY.md.

---

## Supervisors / Management — Lateness · AL · Tagging — mostly BUILT
Global staff tagging: config.STAFF_CALL_NAME + call_name_for() + _staff_mention (call-name + tg://user
ping). Group lateness ladder BUILT but SILENCED (config.GM_ATTENDANCE_GROUP_ACTIVE=False) — all
attendance moved to the private-DM system (below). AL math + accrual (+1.5/mo arrears) PENDING owner
seeding balances. Full owner spec + build detail → docs/HISTORY.md.

---

## Delivery System (WOC) — SHELVED
Mine the WOC delivery-photo archive into structured data (customers/phones/orders/food catalog/prices).
Parked by owner; pilot validated (~$500–800 full-year API). ⚠ Grab/Foodpanda privacy-law flag on
customer numbers. Full design + pilot findings → docs/HISTORY.md.

---

## Staff Registry · Ex-staff Offboarding · Paperless /stock — BUILT
staff_registry (canonical/call/aliases/uids/status/schedule/salary). /exstaff or plain owner DM → confirm
card → mark ex_staff (history kept) + ban from internal groups WHERE the bot is admin (currently
mark+report only — promote an admin account to enable auto-kick). Paperless /stock overhaul + the
143-item order CSV import are PENDING. Full spec → docs/HISTORY.md.

---

## Private-DM Attendance Overhaul — IN BUILD (current focus)
Button-driven private-DM attendance: check-in (live-location geofence) · late+payback (time-bank) ·
AL + senior approval · Special Leave (sick/marriage/death/birth) · day-off swap · Give-OT time-bank ·
points · no-shows · payroll. Replaces the silenced group ladder. Full spec → docs/ATTENDANCE_SYSTEM_DETAILED.md
+ docs/ATTENDANCE_SYSTEM_MAP.md. Test harness → docs/ATTENDANCE_TEST_MODE.md.

---

## STRATEGIC — POS convergence (owner, session 27)
> Owner is building a separate UNIVERSAL CLOUD POS (cloud source-of-truth + local-PC backup so ops don't
> break when internet is down). Endgame: fold tested features (stock, attendance, GM brain) into the POS.
> DECISION: stock staff-entry starts on **AppSheet** as a THROWAWAY/BRIDGE front-end (validate workflow fast),
> NOT the destination. GUARDRAILS: (1) keep OUR Postgres the SOURCE OF TRUTH — sync AppSheet→Postgres; the
> brain (order list, minimums, suppliers, points) stays in our code, AppSheet is just a data-entry skin →
> migration = swap front-end only, no rebuild. (2) Shape the data model to POS inventory needs (item id,
> unit, count, min, order_qty, supplier, counted_by, timestamp). FUTURE: when POS basics exist, cross-
> reference BOTH repos (add POS as a 2nd working dir / share its design) to design the convergence with both
> codebases in hand. Keep everything TWBshop-side POS-friendly meanwhile. Custom-own beats AppSheet long-term
> because inventory IS a POS module and offline-sync is the same hard problem the POS must solve.

---

## GM Backlog & Roadmap
The remaining GM "shop-brain" roadmap (finance brain · attendance brain · stock/ops brain · cross-group
knowledge brief · added ideas) → docs/ROADMAP.md (reference only, not an auto-run task list).

---

## Operations Intelligence System — mostly BUILT (Phase 3)
Telethon listener + historical import + AI analysis tiers + hiring bot are built/live. Original Phase-3
plan → docs/HISTORY.md.

---

## Current Status
> Update this at the end of every session. The only source of truth for what's next. Old session logs (19–28) → docs/HISTORY.md.

**Last updated:** 2026-06-08 (session 29 — /test shell hardening: deployment-drift audit, OT WHEN-step
+ card window, every ladder walks to the END, full Khmer review export)

**Session 29 (Jun 8):**
- **DEPLOYMENT-DRIFT AUDIT (owner feared lost work):** verified ALL last-night work safe — 20 commits
  pushed, server HEAD==origin, 19 attendance tables live in prod, attendance_live=OFF, all 5 services
  running current code. Root cause of "Give OT shows no time": fixes were pushed to GitHub but the
  twbshop-gm service was never restarted. LESSON: after any gm_bot/ push, `ssh twbshop pull + systemctl
  restart twbshop-gm` — code on GitHub ≠ code running. coverage_requirements is NOT a table (hardcoded
  in coverage.window_target).
- **OT /test flow fixed:** added the missing WHEN step — 📅 Later now picks day + start-time before the
  owner card; ⚡ Now skips it (it's now). Owner card + stub show the real chosen window.
- **EVERY LADDER WALKS TO THE END (no more "Next build" dead-ends):** new generic walkthrough engine in
  attendance_ui (att:walk:{name}:{idx}) + step sequences for late→payback, AL, day-off swap, sick(me/
  family), marriage, family-death, wife-birth. Each stub has "▶️ See the rest of this flow" stepping
  through every following message (senior cards, group notices, final staff confirm) — preview only,
  gated. Personal OT view points to My schedule; dead Emergency "Later" stub removed.
- **FULL KHMER REVIEW EXPORT for ChatGPT:** C:\Users\Papa\Documents\khmer_full_review.txt — Section A =
  195 EXISTING bilingual messages (the "21" was only last-night's new strings; ~174 were already done in
  prior sessions), Section B = 61 genuine staff-facing English-only gaps (mostly the just-extended
  walkthrough lines, marked "(KH pending)"). Owner translating via ChatGPT. NEXT: regenerate the export
  after this batch to capture the new walkthrough lines; then wire Khmer into the walkthroughs.
- Suite green: 369.

**▶ RESUME HERE (session 29): TEST HARNESS COMPLETE — ready for the owner's single role-play test.**
All 8 flows are wired test-aware AND drivable from /test in test mode: AL · late/payback · check-in ·
Give-OT · day-off swap · sick (declare + papers) · marriage · death/birth. In /testmode on, every
flow runs the REAL submit_* code; every message (staff/senior/group) routes to the OWNER labeled
[→ role]; the owner taps the other roles' buttons (actor-override); every write is is_test-tagged;
real balances/data are NEVER touched. Commands: /testmode on|off · /teststatus · /testreset.
Mechanism: shell terminals set att_test_pending {flow, persona, picks} + prompt the reason → bot
_att_test_dispatch fires the real submit_* (no-reason flows use 'type go'). Safety: PreToolUse
HIGH-RISK guard (.claude/hooks/highrisk_guard.py, per-action ask, fail-closed) + scripts/verify_live.py
(ground-truth deploy check) installed; live hook-wiring needs a fresh-session check by the owner.
Dry-runs/walkthroughs DEMOTED to read-only previews (persona picker says trust /testmode).
NEXT: (1) owner runs the single role-play test (walk every topic, tweak wording/Khmer). (2) Then
go-live: /testreset → /testmode off → send the greeting (Documents/gm_greeting_FINAL.txt) + attach the
persistent 📋 Menu button → flip attendance_live='true' (live-location requirement waits until owner
explains it + all staff pressed Start). Design: docs/ATTENDANCE_TEST_MODE.md.
attendance_live=OFF, attendance_test_mode=OFF.

**⏰ DATED CHECKPOINT (set 2026-06-08): stand up a staging/local Postgres so the prod DATABASE_URL
is NOT present during normal development.** Today dev and prod share the managed DO Postgres — every
migration/query in dev hits live payroll/staff data. The HIGH-RISK hook (.claude/hooks/highrisk_guard.py)
is a BACKSTOP, not the fix; the real lock is a missing prod credential in dev. Target: before the next
migration/payroll/payment task, and no later than **2026-06-30**. Don't let it become "never."

**Phase:** Retail complete · B2B Phases 1+2 · GM Manager live · Ops listener live · Hiring intake+quiz+assessment built. Attendance system in build (gated OFF).

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

Handles wholesale orders from restaurant and bar customers via their own Telegram groups.

### B2B Design Rules
- Group chat = the customer. Anyone in the group can order.
- **Multi-user policy (intentional):** State is keyed by group chat_id, not by individual user_id. Any member of the group can build, edit, confirm, or cancel the group's order. This is by design — B2B customers are businesses where multiple staff may need to interact. Actor (name + user_id) is logged at every confirm/edit/cancel/location-change for audit purposes.
- Re-order same day: bot asks "is this extra?", then re-confirms full merged order.
- Gram-required items: pulls from history first, falls back to standard grams (shown in confirmation).
- Attributes (e.g. sesame type): pulls from history first, falls back to menu standard.
- Delivery/pickup: stored per group. New group asked once on first order.
- 10:10:10pm Phnom Penh (UTC+7 = 15:10 UTC): nightly summary to B2B staff group.
- No AI in Phase 1 — rule-based matching only.

### B2B Repo Structure
```
b2b_bot/
├── bot.py              ← handler registration and 10:10pm scheduled job
├── menu.py             ← B2B menu items, grams, attributes, aliases
├── menu_keyboards.py   ← cart state dicts, all keyboard builders
├── menu_handlers.py    ← menu command + callback handlers, _do_confirm
├── menu_flow.py        ← facade (re-exports menu_keyboards + menu_handlers)
├── order_parsing.py    ← parsing, history resolution, confirmation formatting
├── order_handlers.py   ← state dicts, notifications, order save + callbacks
├── orders.py           ← facade (re-exports order_parsing + order_handlers)
├── customers.py        ← group chat ID → business name registry
├── summaries.py        ← nightly production total + per-customer breakdown
├── cake_menu.py        ← cake menu data
├── pricing.py          ← pricing helpers
└── billing.py          ← billing functions
run_b2b_bot.py          ← entry point: python run_b2b_bot.py
```

### B2B Build Phases
- [x] Phase 1 — Foundation + full order flow
  - Menu, customers, history resolution (grams, attributes), confirmation gate
  - Delivery/pickup stored per group; Grab Express cost via OSRM ($0.68 base + $0.025/90m)
  - Auto-registration: trusted admin adds bot → location pin prompted → cost calculated
  - Bakery coordinates set (11.5387774, 104.9147998)
  - Free delivery threshold ($10+), delivery fee shown when under
  - 9pm pre-summary (totals only, deleted when full fires), 10:10pm full summary
  - 4:30am + 6:10am dispatch reminders (replied to 10:10pm message); 9am 48h mini-order reminder
  - Payment photos/PDFs: AI classifies → billing or order flow; forwarded to OWNER_TELEGRAM_ID
  - Billing: unpaid balances tracked per customer, marked paid oldest-delivery-date-first
  - Daily 6am payment reminder (yesterday's unpaid) + weekly Monday 6am (accumulated balance)
  - /balance and /summary staff commands
- [x] Phase 2 — Recurring daily/weekly orders
  - DB: b2b_recurring_orders + b2b_recurring_confirmations
  - 7am/1pm/6pm reminders the day before fulfillment
  - [Confirm] / [Skip tomorrow] buttons; auto-skip at 10:10pm if still pending
  - Grace period: no reminder if order created ≤1 day before fulfillment
  - Permanent cancel: status = 'cancelled', record kept, bot never sends again
- [ ] Phase 3 — Claude API for smarter matching and future AI features
