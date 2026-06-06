# Bakery Automation System — Project Rules & Status

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

## REPORT Finance Tracking — Design Notes & Pending Decisions (GM bot)
> Gathering/design phase (Opus). NO rules built yet. Read this every session and remind the owner of the pending list.

**Group:** TWB REPORT (chat_id -5136886404). Replaced Facebook Messenger daily reports. Live data since 2026-05-27.

**Confirmed business model:**
- **Business day = 06:00 → 06:00** (24h). Café/bakery trades late.
- **~05:00:** staff post the final 24h total — deliberately 1h before the 06:00 close so there's a buffer to hunt down any discrepancy.
- **05:00–06:00:** mistake-hunting hour. If clean, books close.
- Receipts posted **after the ~05:00 close but before 06:00 roll into the NEXT day.**
- A final total posted ~05:00 and labelled e.g. "28/05" closes the window that ran 06:00 27th → 06:00 28th. **File it under the day that just closed (the 27th), not the morning-of-writing label.**
- Two reports per day: **afternoon mid-report (~16:00, ≈ day-shift handover)** + **05:00 final (full 24h).** Keep BOTH, label mid vs final, so a discrepancy can be localised to a shift (night ≈ final − mid).

**Daily total report format (decoded + verified on 3 days):**
```
DD/MM/YYYY
Cash on hand : $ 600        ← starting float (constant)
cash income  : $ X          ← cash sales
Aba income   : $ Y          ← bank-app (ABA) sales
total sales  : $ X+Y        ← revenue
Cash expense : $ Z          ← cash paid out
ABA Expense  : $ W          ← bank paid out
Total        : $ ___        ← expected drawer = 600 + cash income − cash expense
Cash count   : $ ___        ← physically counted
Over / Lost  : $ ___        ← cash count − expected  (Over = surplus, Lost = short)
```
- ABA money never touches the cash drawer reconciliation (bank-app, tracked separately).
- **FX margin is BY DESIGN:** peg is 4000 riel = $1, but $1 usually buys a bit more than 4000 riel. Staff are encouraged to pay local riel expenses, so the float more often than not ends with a small surplus. **A small "Over" is EXPECTED and benign — never flag it.** Real signals = "Lost"/shortfall and sales dropping.

**GM behaviour (owner-gated — same pattern as concern cards):**
- GM parses each report, recomputes the drawer math (600 + cash in − cash out), catches staff arithmetic slips (e.g. May 27 was off by 10¢) and format breaks.
- For NOW: GM reports computed errors + anomalies **to the OWNER privately only.** Owner reviews daily, we tune over the terminal. GM does **NOT** tell staff about calc errors until owner explicitly says "GM can now inform them."
- Also wanted: daily/weekly digest (sales, expenses, cumulative Over/Lost trend) + anomaly flags (Lost over threshold, sales drop).

**PENDING DECISIONS (discuss with owner over terminal — remind every session until resolved):**
1. **Overexpense carryover** — OPEN (session 25: owner wants to "think of something" — REMIND next session). Current practice: when a day's cash out > cash in, the deficit is carried into the next day as an expense taken from the $600 float. Owner wants a cleaner model. Opus to propose options when owner is ready.
2. **Float restoration** — ANSWERED (session 25): owner normally NEVER tops up the float except in extreme cases. The drawer "tops itself" back toward $600 from cash income most days (because of the 4000=$1 FX margin → daily small surplus). So: do NOT model a top-up source; the float self-restores from the FX-margin surplus. Only an extreme/unusual shortfall would involve a manual top-up. Tied to #1.
3. **Thresholds** — ANSWERED (session 25) + BUILT & LIVE (session 26): flag "Lost" > $2 (config.GM_LOST_FLAG_THRESHOLD). _maybe_ask_lost posts "Cash short by $X... does anyone know why?" with the FX framing (4000 riel=$1 so drawer should run a little OVER), gated by report_corrections_to_staff, opens a 'cash_lost' clarification on the ladder. finance.lost_exceeds() pure helper. Sales-drop % still TBD after more baselining.
4. **Shift cutoff** — ANSWERED (session 25): confirmed. Mid-report ~16:00 = day-shift handover cutoff. night ≈ final − mid uses the 16:00 boundary.
5. **Dedup prerequisite** — DONE (session 26). It was a ONE-TIME overlap on 2026-05-27 only (Telethon listener initial capture coincided with GM bot go-live on REPORT); zero dup groups after 2026-05-28, so only one collector writes REPORT now — NOT an ongoing leak. Cleaned REPORT ops_messages 88→81 rows (7 dup pairs removed), 0 dup groups left, 0 orphaned gm_daily_reports pointers. Reusable helper shared.database.dedupe_ops_messages(chat_id, prefer_message_ids, dry_run) + dedup_keeper (pure, prefers gm_daily_reports-referenced id else min id) + gm_daily_report_message_ids. 5 tests test_dedup.py. Re-run for other chats if a future listener/bot overlap recurs.
6. **Go-live switch** — DONE 2026-05-31: gm_state report_corrections_to_staff='true'. GM now posts worked-out math corrections IN-GROUP (tagging the report) and opens a clarification so the ladder records staff reasons.

---

## Supervisors / Management — Lateness, AL & Tagging (owner spec, session 25)
> Build spec from owner. Tagging foundation DONE; lateness ladder + AL engine PENDING build.

**Staff tagging convention (GLOBAL — applies to every GM tag everywhere):**
- When the GM tags a staff member, show the name WE CALL them by next to the account tag.
- EXCEPTION: if the call-name already matches the account display name (ignoring case/punctuation/emoji), show only the tag.
- DONE & GLOBAL: config.STAFF_CALL_NAME (display→nickname, 2026-05-27 roll-call) + config.call_name_for() + config.display_for_call_name() (reverse) + gm_bot/mentions.py (format_mention / mention) producing HTML `tg://user?id=<uid>` inline mentions (pings without a @username; send parse_mode=HTML). bot._staff_mention(name,uid) is the canonical resolver — resolves uid via gm_get_staff_uid (latest sender_id in ops_messages) or the reverse call-name map. USE _staff_mention FOR EVERY GM TAG OF A STAFF MEMBER, not just lateness (owner instruction, session 26). Audited: lateness is currently the only pinging path; no other inline-mention code exists. 9 tests test_mentions.py.

**Lateness / pay-back ladder (Supervisors + Management) — BUILT & LIVE (session 26):**
- shared/ai_client.py: detect_lateness_report (Haiku) → {is_lateness_report, late_person, payback_day, confidence}; extract_payback_day (Haiku) for replies. Both fail safe.
- gm_bot/lateness.py: PURE ladder logic decide_lateness_action (awaiting_payback 30min→ask_group; group_asked 24h→escalate) + text builders. 10 tests test_lateness.py.
- shared/database.py: gm_lateness_cases table + init_gm_lateness_db (wired in run_gm_bot.py) + create/get_open/get_open_in_chat/mark_group_asked/resolve/escalate + gm_get_staff_uid.
- gm_bot/bot.py: _handle_lateness (live, Supervisors+Management) = free pre-gate (len + ATTENDANCE_KW) → Haiku detect (conf≥0.55) → if payback day given, log resolved; else open case + ask senior (tagged). Resolution: a reply to the case msg or GM question with a payback day (extract_payback_day) → resolved. _lateness_ladder_job every 120s drives ask_group/escalate. Staged-model design exactly per owner: logic owns timers, Haiku reads, Sonnet reserved (not needed here), Opus for future weekly digest.
- Tagging: all tags via _staff_mention (call-name + ping, drops call-name when == account name).

**Annual Leave (AL) tracking — PENDING build (engine now, seed later):**
- Staff announce off/AL → GM deducts from their AL leftover balance.
- Accrual: every new month each staff +1.5 days.
- New-staff rule (CONFIRMED session 25 — arrears): accrual is credited in arrears. A full calendar month worked earns 1.5, credited on the 1st of the NEXT month. Mid-month start → start month is partial (earns 0); the month immediately following the start also shows 0 (they are earning it); the first 1.5 lands the month after the first FULL month. Example: start Mar 15 → Mar 0, Apr full → +1.5 credited May 1. (Existing/active staff: +1.5 on the 1st of every month.)
- Build schema + accrual/deduction logic + a balance command NOW, but DO NOT start counting until owner fills current AL balances and says "begin counting from today."
- REMIND OWNER: fill current AL balances.
- Align with existing attendance memory [[gm-attendance-policies]]: short-notice AL ok if rare, vague "off tomorrow" → GM asks "Is this AL?", sudden sick full-day → suggest 0.5 AL + half-day, all notices must be BEFORE shift start (else ask for screenshot of when staff told their senior).

**Hiring papers + Khmer refinement workflow (owner, session 25 — re #7/#12):**
- Owner will send more hiring questionnaire papers. GM/Opus generates ALL outputs (replies, analysis, targeted messages, salaries). Owner + ChatGPT review/judge → corrections saved into GM "knowledge" (examples store). Over time, accumulated approved examples refine the Khmer output AND every GM output. This is the path that eventually unblocks Khmer (#12) — manual-approved examples become the training set, not auto-generated Khmer.

---

## Delivery System (WOC DELIVERY PICTURES) — design (SHELVED session 26, pilot validated)
> STATUS: SHELVED by owner (parked, not abandoned). Design + pilot findings below; resume when owner asks.
> PILOT FINDINGS (80 photos downloaded, 22 read by Claude-on-Max at $0 API, then ALL pilot photos+scripts
> DELETED from server+local for PII hygiene):
> - Extraction WORKS well. 3 platforms, each distinguishable: Foodpanda (USD, #52xx/#8xxx, pink panda),
>   GrabFood (RIEL, GF-xxx, green, shows Customer+Driver), E-GetS (#N).
> - DRIVER EXCLUSION confirmed: Grab app explicitly labels "Customer:" vs "Driver:" with both numbers →
>   exclude driver by label (e.g. excluded Leang Panharith, Ros Chanthea).
> - DEVICE-vs-TICKET cross-check corrects misreads (Mali→Matt, Buonn→Bunna, $4.50→$3.50). RULE: device
>   screen is PRIMARY, dedup by order #, tickets/food confirm. Same order appears 2-3× (device+ticket+food).
> - Item modifiers captured ("No Tomato/No Raw Onion") for the wrong-food check. Kitchen tickets show ✓ ticks.
> - 6 brands seen (Café Wine O'clock, Burger 50/50, Paris Croissants, The Wine Bakery, Pasta House, +E-GetS).
>   Foreign customers exist (+63 PH, +44 UK) — phone-as-ID still holds.
> - ⚠️ UNRESOLVED PRIVACY/LEGAL FLAG (decide before building any customer-contact DB): Grab app states
>   verbatim its numbers "can only be used for confirming changes to an order. Saving them or using them for
>   any other reasons will violate privacy laws and your contract with Grab." Foodpanda likely similar.
> - COST: ~$0.004/photo Haiku, ~$0.011/photo Sonnet; 22-photo table ≈ $0.28 if API. Full year (64,919) naive
>   ~$750-850, but dedup-by-order (extract once per order, -40-60% Sonnet) + food-only→Haiku-only →
>   realistic ~$400-600. Measure real cost-per-order with a true ~50-photo API batch before any full run.
> - WOC scale: chat_id -715759659, 64,919 photos last 365d. Telethon download works (stop listener ~30s,
>   run via /root/venv/bin/python with PYTHONPATH=/root/TWBshop, restart — resumes clean).

> The "Delivery System": mine the WOC delivery-photo archive into structured business data.
> Built the wise way: cheap EXTRACTION (metered API, automated) → structured tables → expensive
> SYNTHESIS (Opus-on-subscription = Claude-in-terminal, over rows not raw photos). Never loop the
> archive through bot API. Same pattern feeds the Knowledge Brief.

**Scale (measured session 26):** WOC DELIVERY PICTURES chat_id = **-715759659**. 120,226 photos total
(range 2022→now); **64,919 in the last 365 days** (180d=35,015; 90d=18,718). Server: 40G free / 48G.
**Window to process = last 365 days** (owner: closest to current two-ticket double-check standard;
older data = weaker past habits, skip).

**Owner decisions (session 26):** (1) process last 1 year, newest. (2) Take ALL customer numbers
(exclude drivers by logic). (3) Storage = rolling download→extract→DELETE, batch-by-batch, ~1-month
auto-purge (full year ≈16GB would fit but tight; rolling keeps peak ~1-2GB). (4) Start Phase 0+1.

**COST REALITY (the real budget — NOT Claude Max hours):** the 65k-photo vision extraction runs on the
ANTHROPIC API KEY as a checkpointed background batch (NOT through Claude Max terminal sessions). Rough
full-year estimate: Haiku classify 65k (~$80) + Sonnet extract ~60% tickets/devices (~$400) + Opus on a
SAMPLED few-thousand hard cases (~$250) ≈ **$500-800 API spend**, hours-to-a-day runtime. Claude Max
(terminal) is only for building code + synthesis over distilled rows — light, fits normal windows.
**MANDATORY PILOT FIRST:** process a random ~400-photo sample end-to-end (~$5-8) to measure
classify/extract accuracy + real cost-per-photo, extrapolate the full-year bill, and get owner approval
on the number BEFORE the full run. Pilot also tunes prompts on real photos.

**Pipeline (staged models/logic per stage):**
- Stage 0 Inventory/download/dedup — LOGIC: Telethon resumable bulk-download; SHA-256 + pHash dedup.
- Stage 1 Normalize — CV/LOGIC: EXIF auto-orient, OpenCV deskew/auto-rotate (handles non-90° angles), denoise.
- Stage 2 Classify photo — HAIKU vision: kitchen_ticket|order_ticket|device_screen|food_plate|receipt|other (skip 'other').
- Stage 3 Extract — SONNET vision: phones+name+addr+app+items+price (devices/papers), items+addons+TICKS (tickets); food components on a sample.
- Stage 4 Cross-check/judgment — LOGIC compares kitchen vs order ticks; OPUS (sampled) for blind-tick, wrong-food (e.g. "no bacon" but bacon present), food-looks-right + builds the food-appearance reference library.
- Stage 5 Aggregate — LOGIC into tables: woc_customers, woc_phone_observations, woc_orders, woc_ticket_items, woc_errors, woc_food_catalog, woc_price_history.
- Stage 6 Synthesis — OPUS-ON-SUBSCRIPTION (me, terminal): rolling food catalog+latest prices, off-menu candidates (not ordered in N months → owner confirms), customer intelligence, error/demand trends. Refreshed incrementally.
- Stage 7 Owner-in-the-loop — off-menu confirm, ambiguous customers, wrong-food disputes (gated like concern cards).

**COST MODEL — who looks, not where (owner clarified session 26):** API $ is incurred whenever the
SERVER's code looks at a photo (it calls the API key = metered $). When CLAUDE-IN-TERMINAL (me, on the
owner's Claude Max subscription) looks at a photo, there is NO extra API charge (Max already paid), but
it's bounded by the Max window + my context (~dozens of photos per session, not hundreds) and is manual/
unrepeatable. So: Max-me = piloting/tuning/learning + synthesis (free-ish, small batches); server+API =
production scale (the only practical engine for the full 64,919). PILOT PLAN (owner: use Max not API):
Stage 0 download is free (Telethon); I read ~30-40 local photos here per window at ZERO API to validate
accuracy + tune prompts; then owner decides continue-via-Max (slow, free) vs flip-to-server-API (scale).
Photos must be downloaded to local disk for me to Read them.

**Customer DB:** phone = permanent ID (names change on app, number doesn't). Customer name/number often
ALSO appears on the order ticket itself (not just the device) → cross-check (same number on ticket+device
= high confidence). DRIVER number on the device is labelled with the word "driver" nearby → LOGIC rule:
exclude any number with "driver" adjacent; we do NOT collect driver numbers for now. Driver vs customer
also = LOGIC (number recurring across many distinct orders = driver/platform → exclude; one-order context
= customer).
Normalize E.164 KH. woc_phone_observations logs every sighting+confidence+source photo for audit before
promotion. Link per customer: order history, RFM (recency/frequency/monetary → best + LAPSED customers),
favorite items, preferences/allergies ("no bacon"), delivery brand/app + area, avg spend, peak time, LTV,
complaint history, name variants. Export later as phone contacts "Customer — {name}".

**8 development ideas (the "Delivery System" roadmap, owner approved to track):**
1. Per-staff error scorecards (wrong input / blind-tick / error types + trend) → feeds GM recognition/correction.
2. Demand forecasting (item velocity by day/time) → prep planning + waste reduction.
3. Plating/portion drift QC vs reference library.
4. Price-integrity check (same item sold at inconsistent prices).
5. Menu lifecycle (new items appear, off-menu detection, seasonality).
6. Leakage/fraud signal (food photographed but no matching POS/report entry).
7. Channel timeline (which delivery apps/companies over time → which channels are profitable).
8. Reactivation campaigns (lapsed-customer lists + their favorite item).

**Build order:** Phase 0 download+dedup → Phase 1 classify+phones+Customer DB (fastest payoff: reactivation)
→ Phase 2 ticket extract → food catalog + price history + off-menu list → Phase 3 cross-check/wrong-food/
scorecards (Opus sampled) → Phase 4 fold into Knowledge Brief. **START: Phase 0+1 after the pilot.**

**Knowledge Brief (the big one) — same method, all groups:** apply distill→synthesize to ALL operational
groups (3,619 chats, prioritized by importance), not just WOC/REPORT: cheap classify → targeted extract →
Opus-on-subscription folds distilled rows into a rolling living brief incrementally. Never re-read raw
archive through bot API. WOC structured tables are the first big input to the brief.

---

## Staff Registry + Ex-Staff Offboarding + Paperless /stock (owner spec, session 26 — PENDING)
> Shared foundation: a STAFF REGISTRY with status. Both features below sit on it. Build registry once.

**STAFF REGISTRY (foundation):** one record per person — canonical name, call-name, aliases, telegram
user_id(s), status (active | ex_staff), groups seen, joined/left dates. Ties together the existing alias +
call-name maps, lateness, AL/leave, points, tagging.

**EX-STAFF OFFBOARDING (owner priority, session 26):** owner tells GM "X no longer works here" → mark
ex_staff in registry. Effects: (1) loses ALL staff privileges; (2) historical data KEPT (becomes
history-only); (3) no bot ENGAGES them — GM (and internal bots) ignore an ex-staff/non-staff sender;
(4) removed from ALL groups, OR GM reports which groups they're still in so owner removes them.
GM only replies to STAFF (not non-staff, not ex-staff). DECISIONS (owner, session 26): (1) IDENTIFY: owner
just messages GM that they left. PLUS PROACTIVE — when a known staff member LEAVES an internal group, GM
DMs owner: "did X leave the company? they left [group(s)]". (2) GROUP REMOVAL: BOTH — auto-remove where
the bot has rights + report the rest. (3) ENGAGE-SCOPE: GM + all INTERNAL groups only (retail/B2B keep
serving customers, who aren't staff). (4) NO Telegram-level blocking (not needed). Detect group-leaves via
GM bot left_chat_member events (covers internal groups) + Telethon. Verify bot admin rights for auto-remove
at build. REGISTRY SEED: from existing STAFF_CALL_NAME/STAFF_ALIAS_MAP (~30 known) as 'active'; owner
prunes leavers via the ex-staff flow.
BUILT & LIVE (session 26): staff_registry seeded (36 people, 33 with telegram ids) + helpers. /exstaff
<name> OR owner plain-language DM ('X no longer works here') -> confirm card (shows which internal groups
they're in) -> mark ex_staff (history kept) + ban from internal groups WHERE BOT CAN + report rest. Multi-
match -> pick buttons. Proactive: known active staff leaving an internal group (left_chat_member) -> GM
DMs owner with the same confirm. ⚠️ AUTO-REMOVAL OFF: GM bot (@twb_gm_bot 8827684951) is only a MEMBER
(not admin) in all 5 internal groups, so it CANNOT kick — currently marks ex + REPORTS groups for manual
removal. TO ENABLE (owner chose listener route): CHECKED session 26 — listener account TheWineBakery24PP is also
NOT admin (admin=False, ban_users=False in Stock Checks/COMMS/REPORT; Supervisors/Management are basic-
group ids needing different lookup). So NEITHER account can kick yet. OWNER ACTION NEEDED: promote
TheWineBakery24PP to admin with 'Ban users' in the 5 internal groups. THEN build the removal QUEUE (GM bot
enqueues -> listener processes via Telethon kick -> reports). Until promoted, ex-staff stays in mark+report
mode (works). NOTE for build: Telethon entity for basic groups (Supervisors -4980513319, Management
-865916135) needs PeerChat/dialog resolution, not raw get_entity. 'No bot engages ex-staff' gate
(staff_get_by_uid/active_uids) ready; apply to future /stock + interactive flows.

**PAPERLESS /stock OVERHAUL (owner spec, session 26):** staff-only /stock command (GM ignores non/ex-staff)
→ category buttons → item buttons → enter counts. Can add new stock → owner gets a PRIVATE message of the
addition (to confirm unit+min). Later: award staff POINTS for doing checks (+ other checks). Counts flow
straight into stock_counts (no more paper / 'almost out' report). My ideas to make it easier: pre-fill last
counts (only change what moved); show UNIT IN BRACKETS per item (kills unit confusion); 'same as
yesterday' shortcut; only prompt items that move (weekly full audit); photo fallback (vision job reads the
sheet when rushed); add-new-item -> pending -> owner confirms; implausible-entry validation; remind the
usual checker. Replaces the photo-sheet vision flow over time (keep vision as fallback).

**STOCK UNIT MISMATCH lesson (session 26):** the sheet's MIN column mixes units vs how staff COUNT
(min 'per egg/per kg/per piece' but they count racks/blocks/packs). So the spec min CANNOT be the order
trigger. Readjusted 7 items to count-unit (President butter 50pc->2 packs, plastics 10->1). Right long-term
fix: bot LEARNS each item's reorder level from the numbers staff write (calibrated by 'almost out'),
in their own count-unit; unit brackets on names lock it down. UNITS NOW CONFIRMED (session 26): Pilot
butter=kg (10 is genuinely LOW vs 25), Red Velvet=kg (low), Corn Powder=kg (low), Eggs=per egg, White/Red
Sauce=pots (1.5), Homemade Jam=jars. All 50 items now have unit + min in the staff counting unit.

---

## Private-DM Attendance Overhaul (AL + Lateness + Live-Location) — owner spec session 26
> ⏸️ PAUSED (session 27): owner is planning MORE for this — DO NOT build flows until owner returns.
> SAVED STATE: full design in docs/ATTENDANCE_SYSTEM_MAP.md + docs/ATTENDANCE_SYSTEM_DETAILED.md (every step/
> branch/edge/message). CSV importer DONE (import_staff_schedule_csv) — registry rebuilt from owner CSV: 35
> active (29 TWB/6 Delis), 5 seniors, 6 ex-staff, schedules+expertise+5 planned ALs loaded. NEXT when resumed:
> live-location check-in (which also BINDS each person's real uid on first DM — current telegram_ids are
> seed-guessed from display names, imperfect for repeated names like 'Pisey') -> lateness -> AL approval ->
> group redirect -> understand-without-reply + 👍. Coverage analysis built (gm_bot/attendance.py available_staff).
> REPLACES the group-based lateness ladder + leave-questioning (both SILENCED:
> config.GM_ATTENDANCE_GROUP_ACTIVE=False). All attendance now happens in PRIVATE DM with the GM.
> If anyone posts AL/lateness in a GROUP -> GM replies "Please tell {name} to message me directly."

**WHY (2 photos session 26):** group lateness/leave ladder didn't understand non-threaded replies ->
re-asked + nudged + threatened escalation repeatedly -> spammed Supervisors, looked broken. Root cause:
resolution required a Telegram threaded reply. Fix = understand plain messages everywhere + 👍 ack + go private.

**GLOBAL FIXES (apply to ALL cases, not just attendance):**
- UNDERSTAND-WITHOUT-REPLY: resolve open lateness/AL/clarifications from a plain message (no threaded
  reply needed) — Haiku extract + Sonnet judge while a case is open in that chat.
- 👍 ACK: when GM registers any business reply that is NOT a concern, react 👍 so staff know they were heard.
  If the reply IS a problem/concern -> NO 👍 (so staff don't think it's fine). 👍 never replaces the GM's
  actual reply/escalation — it's only an acknowledgement.

**AL flow (private):** staff DM GM the AL days/hours + reason (no reason -> GM asks). >=2 of the chosen
seniors must approve. GM DMs each senior privately: ✅approve/❌not-approve buttons + the request + an
AVAILABILITY PICTURE — per AL day/window, the staff working those hours that day (EXCLUDING anyone on
day-off OR on AL themselves that day — don't list people who aren't there). On 2 approvals: the senior
messages collapse and a fresh message to all seniors restates details tagging who approved/not. Approved ->
Supervisors group gets a plain notice of the AL days/times (NO availability, NO who-approved). Rejected ->
nothing to the group, seniors only.

**Lateness flow (private):** staff DM "late X min/hrs". GM assumes their NEXT shift unless the shift already
started (then: "ok, but please tell us well before your start time next time"). GM posts the lateness to
the SUPERVISORS group for that shift (so others know he won't be there a while; real time confirmed when he
checks in via location). If he said e.g. 10 min late -> at 10 min past his start: "Have you arrived yet?
Share location if you did." No approval. Frequency reminders; negative points LATER.

**Live-location attendance (WHOLE shift):** staff share LIVE location with GM privately as their time-
attendance. Geofence 200m from TWB (GPS buffer). NOT for Delis staff yet. If live location goes off ->
"Did you leave work early? If not, share location again." Allowance: 30 min total outside per shift (shop
errands/food) — once exceeded -> "What are you doing outside the shop?" (10min + 20min = ask). ALSO: any
staff who hasn't checked in by their start time -> GM reminds them to check in (in case they forgot).

**REGISTRY SOURCE LESSON (session 26):** staff_registry was wrongly seeded from CONVERSATION history
(ops_messages) -> dragged in ex-staff + a duplicate account (Sao Visal/Sao Visal cv). FIX: the owner's
filled CSV is the source of truth. Marked 6 ex-staff (Buy Vong Sakada, Morn Putheavy, Ret Det, Sot Somnang,
Von Vichhka, Sao Visal cv) -> 30 active. When the final CSV is imported, REBUILD registry from it (anyone
not in CSV -> ex_staff; new people -> add). Refreshed CSV: C:\Users\Papa\Downloads\staff_schedule_REFRESHED.csv
**Facts from CSV (session 26):** Seniors (Y): Chim Samphass, Met Solina, Tengmarim Chaktopor, Phal Rath,
Hong Vannary — BUT Met Solina resigns 5 Jun 2026 (pick a replacement senior). Tyty (Boss TT) = CO-OWNER,
exempt from all rules. DELIS staff (separate location/TEAM, excluded from GM for now, AL TBD): Chea Seavluy,
Cheata Sok (Delis supervisor), Khil Chantra, Sopheak Nalmonyboth, Chheng Minea, Ouk Sokchea. New TWB staff
not in any group yet: Yorng Lyhouy, Chuch Pisey. Many TWB shifts are OVERNIGHT (9pm-6am etc.) — attendance
overlaps() handles overnight. Day-offs still to fill. DELIS = different team; if ever allowed to DM the GM,
treat as a separate team (its own seniors/availability pool), don't mix with TWB.

**Foundation BUILT (session 26):** gm_bot/attendance.py (pure: haversine, in_work_zone 200m, to_min,
overlaps incl overnight, available_staff [excludes day-off + AL], lateness_kind, outside_exceeded) — 9
tests. Schema: staff_registry +work_start/work_end/day_off/al_left/org/is_senior; al_requests, al_approvals,
lateness_records, attendance_sessions (init_attendance_db, applied to prod).
**NEEDS owner before flows can run:** fill C:\Users\Papa\Documents\staff_schedule_template.csv (work times,
day off, current AL left, TWB/Delis, SENIOR Y/N; suspected dual account flagged: Sao Visal / Sao Visal cv).
**TODO next:** CSV importer -> staff_registry schedules; then the private DM flows (AL intake+approval,
lateness intake, live-location handler + reminders, group redirect), understand-without-reply + 👍 ack.
AL accrual +1.5/mo arrears starts from the seeded al_left. Negative points later.

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

## GM Backlog & Roadmap (session 26 — owner asked for the full list)
> The remaining GM "shop-brain" work, grouped. "Logic/Haiku/Sonnet/Opus" = which tier does each.
> KEY THEME (owner): build the GM's KNOWLEDGE via Claude-on-subscription (me, terminal) reading the
> groups and distilling structured rows — NOT per-message bot API. Live bot stays cheap; depth comes from me.

### A. Finance brain (TWB REPORT)
- **Sales-anomaly framework — DONE (session 26), silent until data.** gm_bot/sales.py learns a normal BAND
  per day-type (weekday + payday month-phase + Cambodia holiday/festival class) and flags a final report's
  sales only when below the band with enough same-type history (+ likely-reason context, trend-vs-blip).
  Embodies the owner's 7 ideas. _maybe_flag_sales_anomaly DMs owner. ACTIVATES once the years of Facebook
  Messenger daily reports are imported (owner exporting to email; ~5 days live data only so far).
- **Overexpense carryover model** (pending decision #1, owner thinking) — current: cash-out>cash-in deficit
  carried to next day off the $600 float. Owner wants cleaner model. I propose options when owner's ready.
- **Daily/weekly finance digest** (wanted, not built) — Opus-me or scheduled: sales, expenses, cumulative
  Over/Lost trend, anomalies. Pairs with the attendance digest already live.

### B. Attendance brain (Supervisors/Management) — lateness ladder DONE
- **Leave QUESTIONING — DONE & LIVE (session 26):** detect_leave_request (Haiku) on Supervisors/Mgmt;
  logs every leave to gm_leave_events (accumulates now); missing info ('off' w/o 'AL', or no date) opens a
  'leave_clarify' clarification on the EXISTING ladder (ask→nudge→escalate to owner). _leave_questions pure.
- **AL engine (math) — PENDING, gated on owner seeding balances + schedules.** LOGIC for the math + the
  Haiku detection above. Accrual +1.5/mo ARREARS (mid-month start confirmed). Deduct on confirmed leave.
  /al [name] balance cmd; monthly auto-accrual job; low-balance + frequent-short-notice flags.
- **AL AMENDMENTS/inconsistency (owner raised session 26):** staff often change their AL dates or are
  inconsistent. Design: each leave request is a logged event; the AL ledger uses the LATEST confirmed
  request per person for a pending period and SUPERSEDES the prior (same 'latest wins' pattern as finance
  reports) — release old dates, book new, never double-count, and only DEDUCT once actually taken. When a
  change is unclear/conflicting, GM confirms the final dates via the clarification ladder before adjusting.
  TODO when engine built: add amends_previous detection + supersede link on gm_leave_events.
- **Working-hours-per-staff** (attendance memory "pending") — so GM can judge if a late/absence notice came
  BEFORE shift start (else ask for screenshot). Needs the per-staff shift times once names are mapped.

### C. Stock/ops brain (Stock Checks) — semantic concern detection DONE
- **Stock minimums** — stock_minimums table + /minimums cmd; owner gives each item's minimum → low-stock
  alerts fire when reported below min / not restocked.
- **MINIMUMS ALREADY EXIST on the stock sheet (session 26):** Claude read a sample of Stock Checks photos
  on Max (free). The daily stock-count SHEET (e.g. msg stk_225) has a "Min.Stock (in each 1)" column +
  "Order this" column + daily count columns. So minimums are authoritative, not approximated. Transcribed
  ~48 items (Tomato Ketchup 2 tubs, Almond Ground 2 packs, Eggs 500pc, etc.). OWNER TO CONFIRM blurry ones:
  Black sesame, Vegetable oil, Pilot butter, Molasses; and set mins for handwritten add-ons (Soft Roll
  Plastic, Chocolatin Plastic, Red Velvet, Corn Powder). Insight: chronic 'almost out' items hover right
  at their min (Almond Ground min 2, sheet shows 3,3,3) → raise mins or tighten reordering.

**DAILY STOCK ORDER (7am) — owner spec session 26, foundation built, vision job PENDING:**
- Goal: 7am message to Stock Checks group: "Check if we need to order:\n- Qty Item\n- Qty Item...".
- BOT READS THE STOCK SHEET (owner chose this over the text report): daily ~$0.01 vision read (Sonnet) of
  the latest stock-sheet photo → current count per item → compare to min → below-min items + order qty.
  (A scheduled job can't use Claude-on-Max, so this one feature does use a small daily API call; owner OK.)
- ORDER QTY = bot's OWN determination from USAGE HISTORY (depletion rate), NOT the sheet's 'Order this'
  (many items don't state it). Bot maintains/raises its order-qty as usage grows over time; can suggest
  updating the sheet's 'Order this'. DECLINING usage (item used less than before) → inform owner (off-menu?).
- PERSISTENCE: re-list each 7am until the item clears. NO NEW SHEET: reuse last; 2 days in a row no sheet
  → escalate to the group ("why hasn't the stock check been done?"). Roll out owner-preview first, then live.
- Order-qty formula + clearing rules: owner deferred ("learn more, ask later") — first-pass default built,
  tune on real output.
- BUILT (session 26): gm_bot/stock.py PURE brain (is_low, suggest_order_qty [min+buffer, or usage*lead],
  build_order_list, format_order_message, no_sheet_decision, usage_trend) — 10 tests. stock_items +
  stock_counts tables (init_stock_db).
- SEEDED (session 26): stock_items has 50 items, 47 with owner-confirmed minimums (seed_stock_items_default,
  idempotent DO NOTHING — re-run safe, never clobbers edits). Owner confirmed the blurry ones: Black sesame
  4kg, Vegetable oil 1 tin, Pilot butter 25kg, Molasses 2 bottles, Soft Roll Plastic 10 packs, Chocolatin
  Plastic 10 packs, Red Velvet 8kg, Corn Powder 5kg. STILL need min from owner: White Sauce, Red Sauce,
  Homemade Jam. Each item has aliases for matching the messy daily reports.
- TODO next: ai_client.read_stock_sheet (Sonnet vision) + photo-classify to find the sheet + daily 7am job
  (owner-preview first) + count time-series → usage learning + decline alert. Order-qty formula tune later.

### D. Cross-group KNOWLEDGE (built by Claude-on-subscription, NOT bot API) — the "through you" theme
- **Knowledge Brief** — rolling living summary of ALL groups (3,619 chats, prioritized by importance):
  cheap classify → targeted extract → me folding distilled rows in incrementally. WOC tables would feed it
  (WOC shelved). Never re-read raw archive via API.
- **Staff roster/profiles** — one record per person: real name + call-name + aliases + role + attendance
  record + error/recognition history. Backbone for tagging, lateness, AL, scorecards. (Partial: alias +
  call-name maps exist.)
- **Decisions/policy ledger** (from Management) — distill decisions/announcements so the GM KNOWS settled
  policy (extends the approved-proposals playbook).
- **COMMS & Transfers reconciliation** — money/stock transfers between locations: track + reconcile.
- **Supplier knowledge** — prices over time, issues, who's reliable (ties to the price-list fetcher).
- **Recurring-issue tracker** — equipment faults, repeated complaints, themes across groups.

### E. My added ideas
- **"Ask the GM"** — owner asks free-text ("how often was X late last month?", "what did we decide about
  Y?", "best customers?") answered from the structured knowledge by me/Sonnet. Turns the brain into a tool.
- **Morning owner briefing** — daily digest: yesterday's sales, any Lost, attendance, open clarifications,
  new concerns. One message to start the day.
- **Cross-signal correlation** — combine signals (waste up + sales down + a late key staff) into one flag
  instead of separate pings.
- **Proactive supplier price-change alerts** — price fetcher → compare to last → flag increases to owner.
- **Recognition/morale trend** — extend the points leaderboard into a morale/retention signal.

---

## Current Status
> Update this section at the end of every Claude Code session.

**Last updated:** 2026-06-06 (session 28 — attendance v2 design COMPLETE + registry fully bound + roll-call handler built & deployed)

**▶ RESUME HERE (session 28 end): ATTENDANCE BUILD IN PROGRESS.**
- **DESIGN 100% CLOSED — docs/ATTENDANCE_SYSTEM_DETAILED.md is the build spec.** Owner answered every 🔒
  over an 8-round brainstorm: button-driven private DM (any text → main menu, one button/row, ←Back first,
  long labels NEVER side-by-side); check-in at shift start via live location (200m, no continuous tracking,
  voluntary always-on secretly stored in location_pings); Late ladder (time buttons → reason ON ARRIVAL w/
  quick-reason buttons → Supervisors notice name+time only) + payback = need-targeted slots (7-day window,
  need-ranked, tie→closest date, before/after own shift + 1 day-off option in their usual hours, partials,
  14-day deadline → AL → salary, no payback-of-payback, no +10 during slots); AL days 7–90 (today+6 =
  Emergency only), balance shown in menu header, cancel until AL TIME starts; Emergency AL 1×/30d from last
  APPROVED (2nd = bonus-not-earned warning, 3rd = hard block incl. "counts as absence (1 day's pay)" line),
  mid-shift variant From-now/I'll-be-back with 1-senior-to-leave; Give OT = SENIOR grants 30min–6h →
  OWNER approves → time bank (cap 14h, no money, no expiry — daily self-deleting reminder) → staff books
  buyback at business-best slots, no approval; day-off swap (same week, 2 seniors + partner, partner
  FIRST); no-show = 1 day's pay (never mention the law) + next bonus not earned, cut carries to next
  month's #1 pay if current already paid; slips named by MONTH OF WORK (May#1=paid Jun 1, May#2=Jun 15,
  prorated from join date), owner reviews ONE paged editable table message → Approve & send all; bonus
  language = earned/not-earned ONLY, surprise reveal on #2 payday, approved legal disclaimer auto-appended;
  points CATALOGUED PENDING owner review (raw events stored now, +10 early/−1/−2 per min etc.); ripple
  check + coverage heatmap + /whois + /payroll + time-ledger digest line + EN/KH strings as DB table;
  👍 ALWAYS for owner messages + explicit action confirmations, staff 👍 never on problems; ALL seniors
  get approval requests even on AL/off-hours. ZERO-API: all flows buttons+logic, Haiku only for group
  redirect + understand-without-reply.
- **REGISTRY FULLY BOUND (session 28):** every active staff has a uid. CSV v3 imported (34 upd, day-offs,
  AL balances, expertise) + 4 planned ALs as approved al_requests (Chun Jun5-7, Kiry Jun4, Soleng Jun4,
  Visal Jun9/10/12). Salaries+bonuses+first/second pays imported (33). New registry cols: salary_usd,
  bonus_usd, phone, first_pay_usd, second_pay_usd (migration APPLIED to prod via init_attendance_db).
  Phones: 9 auto via listener + Khon Visalpisey CONFIRMED=768420022 (+phone), Chuch Pisey=6818934685,
  Sao Visal=5023909267 (proved 'Sao Visal cv' was a DUP of him — uid stripped from dup), Tyty=1067974900,
  Thorn Kimheng=6872279388 (@Kingmeow23). Dual-uid left: Rom Sopheaktra, Sen Vathanakthyda (first DM
  settles). Ex-staffed this week: Met Solina (resigned Jun 5), Lim Soleng (Jun 5), Yorng Lyhouy (owner:
  gone). 'Cheata Sok' renamed → Sok Cheata (KHMER NAMING: left=surname, right=given; call name = right
  name or its tail). Rule: store numeric uid always; accept @username/phone as input only.
- **ROLL-CALL HANDLER BUILT (gm_bot/rollcall.py) — deployed this session:** staff DM /start or hello →
  known active uid = bilingual greet by call name ONCE (gm_state rollcall_greeted), multi-uid settles to
  the writing account; unknown uid + name match (difflib/substring, Khmer name order, zero-AI) → owner
  confirm card [✅ Bind] (callback bind:) , silence to sender; stranger → silence + one-time owner note.
  staff_bind_uid() in database.py. _private_text_router replaces _owner_private_departure registration
  (owner → departure detect, others → roll-call). 12 tests test_rollcall.py. OWNER IS TELLING ALL STAFF
  TO MESSAGE THE GM NOW (roll-call = binding + Start-press collection).
- **NEXT BUILD (in order):** main-menu button shell → check-in job (+check-out, shift-continuity) → Late
  ladder + payback slots → AL/Emergency flows → day-off swap → Give OT/time bank → slips/payroll →
  role-play test with owner (attendance_test_mode: everything to owner only, he plays every role, tweaks
  wording+Khmer) → go-live WITHOUT live-location until owner explains + ALL staff pressed Start.
- **Button stacking fixes shipped:** gm _exstaff_kb + b2b Confirm-Recurring ×2 + Bank-account-number.
- **Still pending from session 27:** 143-item stock order CSV import (owner's staff filling); AppSheet
  decision (own-Google-accounts vs shared-link). Suite green: 280.

**Previous status (session 26):**

**Session 26 also shipped (finance + digest):**
- Lost>$2 group-ask: gm_bot/bot._maybe_ask_lost + finance.lost_exceeds + config.GM_LOST_FLAG_THRESHOLD (2.0). Opens 'cash_lost' clarification; judge prompt updated for cash_lost.
- Finance AI-fallback + alias learning: finance.looks_like_report_attempt + parse_report_text(extra_aliases=) threading; ai_client.extract_daily_report_ai (Sonnet, GM_FINANCE_FALLBACK_MODEL) runs ONLY when the regex parser under-reads a report-shaped message; recompute() math stays deterministic (AI only reads). New labels learned into gm_finance_aliases (init_gm_finance_aliases_db, gm_add/get_finance_alias) and fed back into the free parser. _store_daily_report_if_any is now async.
- Weekly attendance/AL digest: ai_client.generate_attendance_digest (Opus, GM_ATTENDANCE_DIGEST_MODEL) + _weekly_attendance_digest_job (run_daily 01:30 UTC, fires Mondays PP only) + gm_get_lateness_cases_since / gm_get_concerns_since. DMs owner; skips when no data. (AL section will populate once the AL engine + balances exist.)
- Tests: test_finance.py now 26 (added lost threshold + report-attempt heuristic + alias learning).
- TEST SUITE FIXED (session 26): added repo-root conftest.py that imports the real config.py before collection, so test_intake.py's `sys.modules.setdefault("config", stub)` no longer poisons later GM test modules. `python -m pytest tests/` now runs the WHOLE suite green (232 passed). Run the full suite normally again.
**Phase:** Retail bot complete. B2B bot Phases 1+2 complete. GM Manager bot live. Ops listener live. Hiring system: intake + quiz + Haiku intake intelligence + Opus assessment plumbing built. Chaos tests: B2B 42/42, Hire 57/57. Assessment decision tests: 17/17.

**(session 27 note, still pending):** owner's staff are filling the
full 143-item stock order CSV (C:\Users\Papa\Documents\stock_order_template.csv — 3 sheets: Sheet1 dry/baking
50, Sheet2 Meats 26 + Cheese 18, Sheet3 frozen/condiments/spices/pasta-delis/packaging 49). When owner sends
it: IMPORT into stock_items — create the ~93 NEW items + set each item's order_qty_override (fixed "how many
to order", replaces the bot computing it → no more 748-eggs) + supplier + confirm units/mins (esp. Meats/
Cheese which had blank units/mins). Watch for [X]=discontinued and [Delis] flags. Then the 7am order list
reads "Order N {unit} {item} — from {supplier}".
STRATEGIC (see "STRATEGIC — POS convergence"): stock staff-entry will start on AppSheet (throwaway bridge),
OUR Postgres stays source of truth; cross-ref the POS repo later. To START AppSheet build, owner must pick:
own-Google-accounts vs shared-link + by-area counter assignments.
PAUSED: Private-DM Attendance overhaul (owner planning more — full design in docs/ATTENDANCE_SYSTEM_*.md;
CSV importer DONE, registry rebuilt 35 active). SHELVED: Delivery System (WOC). Parked: AL engine, Lost-ask
sales-drop %, Knowledge Brief, stock /stock Telegram flow (owner-test mode).
GM shop-brain broadly LIVE: semantic concerns, policy replies+72h repeat, Lost>$2 ask, finance AI-fallback,
weekly digest, REPORT dedup, staff registry + ex-staff offboarding (auto-remove OFF — bot not group admin;
owner to promote TheWineBakery24PP if wanted), stock minimums seeded + vision-read job + 7am order (owner-
preview), global staff tagging. Whole pytest suite green (268).

**Semantic concern detection + policy replies — built & live (session 25):**
- shared/ai_client.py: detect_concern_semantic (Haiku, GM_CONCERN_MODEL) — meaning-based waste/mistake/low_stock judge. Replaces the 2-keyword scan. Catches zero-keyword reports ("tray slipped, 6 cakes fell"); ignores negations ("no waste today"). Fails flagged (_error) so caller can fall back.
- gm_bot/analyzer.py: _detect_text_concerns renamed _keyword_text_concerns (kept as FREE fallback). New _worth_checking pre-gate + _semantic_text_concerns (per-msg AI error -> keyword fallback) + detect_text_concerns dispatcher. analyze_live_message now async. run_analysis awaits it. config.GM_SEMANTIC_CONCERNS (default True) + ANTHROPIC_API_KEY gate semantic vs keyword.
- gm_compose_reply WIRED to approved policies: live concern -> gm_get_approved_policy_for_type(type) [SQL, no AI] -> gm_compose_reply (Haiku) drafts a fresh reply -> _policy_reply_plan routes it. Owner-gated by gm_state 'policy_replies_to_staff' (mirrors report_corrections_to_staff): not 'true' = private preview to owner; 'true' = posts in-group as reply. SET TO 'true' (live) session 25.
- Matching v1: correction + recipients='group' + concern_type match (or 'mixed'), newest approved wins. Skips individual/recognition proposals. NOTE: 0 approved group-correction policies exist today, so nothing fires until owner approves a proposal via /proposals — going live is dormant-safe.
- 72h REPEAT-NOTIFY (session 25, replaces the cooldown idea): no suppression. If the same policy/type fires again in the same group within config.GM_POLICY_REPEAT_HOURS (72), GM still replies in-group as usual AND pings the owner privately ("correction not landing") + forwards the triggering message. Tracked via gm_state key 'policy_last_reply:<chat>:<type>' (ISO ts), stamped only on a real in-group post. Pure helpers _repeat_within / _humanize_gap / _repeat_alert_text in bot.py.
- Tests: tests/test_semantic_concerns.py (12, injected fake detector) + tests/test_policy_reply.py (11: 4 routing + 7 repeat-notify). Full GM suite 49/49.

**Staff alias map — checked (session 25):** Scanned Stock Checks 2026-05-27 roll-call ("my name is X, call me Y"). config.STAFF_ALIAS_MAP already complete for the prior unknowns: Cat=Mon Chenda, Nakk=Doeun Rothanak, NY=Yi Sony, O=Korn Chantrea, Seth 🫵=Phan Piseth, Boss TT=Tyty, por=Por. STILL UNRESOLVED (did not self-ID in roll-call — ASK OWNER): **Pew, Me Me, Chan Oun, Roth** ("Roth" is ambiguous — ~70 B2B senders contain it).

**Owner "remind me later" queue (resurface each session until done):**
- Finance #1 overexpense carryover model (owner to think of an approach)
- Finance #3 BUILD: wire the Lost>$2 group-ask into the finance flow
- Stock minimums intake (#6 — table + /minimums, then owner gives each item's minimum)
- Provide real names for: Pew, Me Me, Chan Oun, Roth
- Facebook Messenger export (Sara Bologna account)
- Bakong/KHQR registration (needs passport on other PC)
- Hire bot: tap the pending owner Approve/Reject button, then run /create Test Candidate end-to-end
- Review the 383 concern cards in GM chat (/review for missed)
- Hiring: owner will send more questionnaire papers to analyze (targeted replies, salaries) → judge+educate via ChatGPT

**Telethon listener restored (session 24):**
- twbshop-listener was DOWN (crash-looping) since the session-22 secrets.py reformatting wiped TELETHON_API_ID/API_HASH/PHONE. Those creds were only ever on the server, never pushed to the repo → not git-recoverable. (Same corruption that killed GM_BOT_TOKEN.)
- Recovered api_id/api_hash from my.telegram.org (app "TWB Listener", id=30110706). Restored to secrets.py LOCAL + SERVER + REPO. Phone +85510655010 also stored everywhere.
- ops_intelligence/listener.py fixed: connect() + is_user_authorized() first, phone login only as fallback — so a valid session reconnects with NO re-login (start(phone="") used to raise before checking the session).
- Listener account = TheWineBakery24PP (id=1271537077) — the shop account that posts in groups. Session file ops_listener.session intact (created May 28, valid).
- ops_messages now holds 567,707 messages / 3,619 chats / 2020-2026 (330,933 text + 210,310 photos). This is the full 6-year business archive — STORED but not yet DIGESTED into a knowledge brief (that is the GM "shop-brain" build, still pending).

**SECRETS DURABILITY RULE (learned the hard way, session 22→24):**
- EVERY secret must live in the twbshop-secrets REPO, never only on the server. Server-only secrets get silently wiped by any secrets.py reformat/bootstrap and are unrecoverable.
- After adding/restoring any secret: push secrets.py to the repo via `gh api --method PUT /repos/aaaeeeaaarrr/twbshop-secrets/contents/secrets.py`.
- secrets.py is multi-line Python ALWAYS (one-line corruption = SyntaxError). Verify with `python -c "import secrets"` after any edit.
- The dangerous secret for the listener is the SESSION FILE (ops_listener.session = auth_key), NOT api_id/api_hash. Guard the session file. Consider 2FA on the account.

**GM finance parser — wired + storing (session 24):**
- gm_bot/finance.py: deterministic parser. parse_report_text + is_daily_report + recompute (drawer = float + cash in - cash out; Over/Lost = count - expected; catches staff math slips) + business_day_for (06:00 boundary) + classify_report (final=dawn <06:00, mid=daytime) + parse_full. No AI, no DB.
- shared/database.py: gm_daily_reports table + init_gm_finance_db + save_daily_report (idempotent on chat+message_id) + get_daily_reports_for_day. init called from run_gm_bot.py.
- gm_bot/bot.py: REPORT text that is_daily_report -> _store_daily_report_if_any (parse+recompute+store, NO messaging — owner-gated). MISROUTED ROUTING REMOVED per owner (no more wrong-group DMs; pure ingest). Receipt clarity check on REPORT photos unchanged.
- tests/test_finance.py: 14 tests pass (real reports 27/28/30, math-error catch, day-boundary, 4:55 final, caps/comma/spacing variations).
- STILL TO DO per owner's design: AI fallback when free-parse fails + learn new aliases; knowledge-brief (built by Opus-me on subscription, not bot API); semantic concern detection (replace 2-keyword); stock minimums intake; new /commands. Dedup (#5) before aggregation. See REPORT Finance Tracking section.

**Clarification escalation ladder — built + staff-facing ON (session 24):**
- gm_bot/clarify.py: pure logic — is_checking_phrase + decide_ladder_action (nudge 10min open / 30min checking / escalate at 2h) + nudge_text (hardens after 3) + escalation_text. 9 tests.
- gm_clarifications table + init_gm_clarifications_db + create/find/nudge/checking/answer/escalate helpers.
- bot.py: when GM posts a staff-facing math correction it opens a clarification (question_msg_id = the correction msg). _clarification_ladder_job (every 120s) nudges in-group on schedule, escalates to owner at 2h. _resolve_clarification_response records staff reply as the answer (their reason), or backs off to 30min on a "we're checking" phrase.
- report_corrections_to_staff flipped to 'true' — corrections now go in-group, tagging the report.
- 26 tests pass (17 finance + 9 clarify).
- RECEIPTS now folded into the ladder (topic='receipt_clarity'): unclear receipt opens a clarification; a later clear receipt or a text reply resolves it; same nudge/escalate cadence.
- "ANSWER DOESN'T ADD UP" judge wired: ai_client.judge_clarification_answer (Sonnet, claude-sonnet-4-6, configurable). On every staff answer the GM asks Sonnet if it genuinely resolves the question; if not -> escalate to owner with the answer + reason. Fails open (no escalation) on AI error. Sonnet chosen over Opus: bounded short Q+A judgment, runs live/API-metered, cheap+fast; Opus reserved for the brief + cross-week reasoning.

**GM misrouted message detection (session 23):**
- `_notify_misrouted()`: DMs owner + forwards the message whenever something lands in the wrong group
- `_check_misrouted_photo()`: for photos in non-REPORT groups — runs `assess_receipt_photo()` (Haiku, non-blocking via `asyncio.create_task`) — notifies owner if `is_receipt=True`
- `_check_report_receipt()`: now notifies owner when a non-receipt photo arrives in REPORT (previously silent)
- REPORT group text/doc/video: notifies owner with content type + preview, then stops (was previously falling through to Stock Checks concern scanner — bug fixed)
- GM_BOT_TOKEN was missing from secrets.py (lost during session 22 reformatting) — restored to local secrets.py, pushed to twbshop-secrets repo, added to server. GM bot active.

**Correction + offer flow wired (session 22):**
- correction:* callbacks registered in hire_bot/bot.py → delegates to correction_flow.handle_correction_callback
- DB fallbacks added to correction_flow: targeted_message_id and critical_hold loaded from DB on restart
- _store_correction_response idempotent: SELECT before INSERT, one response per attempt
- offer_flow refactored: send_offer_message (no DB) + record_offer_accepted (INSERT only on applicant accept)
- owner_approval_kb(attempt_id) replaces static OWNER_APPROVE_KB — attempt_id encoded in callback_data
- offer:owner_approve:{id} / offer:owner_reject:{id} registered in bot.py (owner private chat)
- offer:accept / offer:question registered (applicant side)
- E-T2 partial check before offer send — pauses and asks owner for last working day
- Path A open-check → correction_understood → auto-sends owner approval button (request_owner_approval)
- handle_open_check_answer returns classification dict for Path A detection
- 6 new tests in tests/test_correction_offer_flow.py — 87/87 pass
- secrets.py reformatted (was one-liner, local corruption)
**Assessment plumbing built (session 21):**
- hiring_ai_assessments, hiring_targeted_messages, hiring_correction_responses, hiring_offers tables
- assessment_package.py: evidence builder + Sonnet rule detectors (critical signals, partial answers, consistency checks)
- assessment_runner.py: run_final_hiring_assessment() — configurable model, JSON validator requiring evidence_refs
- assessment_notify.py: English-only owner notification, idempotent
- correction_flow.py: agreement buttons, open understanding check, Opus classification, resistance handling
- offer_flow.py: all gates checked, hiring_offers row only after owner approval
- assessment_pipeline.py: wired into _end_screen, fails silently (quiz never blocked)
- Khmer validator: 19/19 tests — catches COENG splits, anusvara/vowel splits, multi-space, box/dash artifacts, Latin adjacency

**Khmer status — BLOCKED permanently until manual solution:**
- khmer_auto_send = false
- khmer_status = pending_manual_approval
- All Khmer stored as NULL until manually reviewed and approved
- Khmer validation pipeline itself is unreliable (test strings being corrupted in transit)
- Do not attempt Opus Khmer generation via this pipeline — handle Khmer translation manually

**Live test results (session 22):**
- Service: twbshop-hire.service active (running) on server
- Service file: /etc/systemd/system/twbshop-hire.service (systemctl enable if needed)
- Assessment pipeline: FIRED — hiring_ai_assessments id=1, recommendation=hire, valid=True
- Owner notification: SENT to Telegram (check phone)
- Targeted message: id=1, English stored, Khmer validation FAILED (expected — blocked by design)
- Path A (correction_understood + proceed_to_verbal_retest): PASS
- Path B (conditional_reporting + reject_unless_owner_override): PASS
- hiring_offers: None (correct — row only created when applicant taps accept)
- Bugs found and fixed: JSONB double-decode in assessment_package + bot.py; Opus max_tokens 4096→8192; jsonschema missing from requirements.txt

**Pending (before Opus assessment is truly live):**
- Opus system prompt calibration with approved examples (waiting on clean samples)
- systemctl enable twbshop-hire (service not auto-start on reboot yet)
**Last completed (session 20):**
- B2B chaos test: 38/38 pass. 5 bugs found and fixed:
  1. FIXED: bm_edit_order (SEE YOUR ORDERS) was deleting the live [Confirm][Edit][Cancel] message — _menu_msg not cleared in _do_confirm
  2. FIXED: bm_back didn't clear _recurring_pending/_days — state leaked into next session
  3. FIXED: b2b_cancel keep/cancel-all dialog was dead code (existing_bread/cake never set) — replaced with live DB query
  4. FIXED: handle_menu_callback didn't call _restore_cart — cart lost after bot restart
  5. Hire chaos test: 33/33 pass
- Multi-file CV storage built: hiring_intake_media table, "Done sending files" button flow, 10-file limit
  - Applicants can send 5+ CV photos/certificates before tapping Done
  - All files stored in hiring_intake_media (one row per file)
  - No AI analysis before TEST_UNLOCKED — store first, analyse later
  - Photos at any state (fulltime_gate, appt_set) also stored silently
  - Migration: migrations/2026_05_29_hiring_intake_media.sql (run on server)
- Added new chaos tests: restart/resume (R01-R03), cross-group isolation (X01-X03), Telegram failure (T01), S12 fix verification (T02), multi-file CV (M01-M08)
- Run tests: python3 run_test_b2b_chaos.py (38/38) && python3 run_test_hire_chaos.py (33/33)
**Last completed (session 19d):**
- GM Manager bot fully live: privacy mode disabled, re-added to Stock Checks group, correct chat_id=-1003952029131
- Stock Checks Nov1–May27 2026 imported: 5,276 messages under correct chat_id
- 411 concerns analyzed; historical ones re-sent via local script run_send_historical_photos.py
- 383 concerns sent with photos (364/383 had matched local photos, 95% rate)
- /review command added: resends sent-but-unreviewed concerns by staff with fresh buttons
- Fixed: double /check button session bug, cmd_staff double-send bug
- Button flow: /check → staff buttons → concerns flow; /review → same for already-sent ones
- Buttons: [✓ All good] closes concern; [🚨 Real issue] flags for tracking; [📚 Teach bot] suppresses future similar via gm_rules
- /proposals + /approved + /points commands added (Claude API clustering, approval flow, monthly leaderboard)
- Teach flow improved: shows original concern text, no 60-char limit
- Supervisors TWB history imported: 323 messages (Jun 2025 – May 2026)
- All group chat_ids confirmed: Stock Checks, Supervisors, Management, COMMS & Transfers
- DAILY_REPORT_CHAT_ID=-5136886404 (TWB REPORT group, replaces Facebook Messenger daily reports)
- Management group imported: 538 messages (May 2023–May 2026)
- Staff alias map: 25+ Telegram display name → real name mappings from May 2026 salary sheet
- Proposals redesigned: Opus model, soft skip (pool return), AI-powered refine, 24h auto-skip, model ranking
- [✏️ Refine] on /approved: stacked notes, conflict detection, [New/Old/Keep both] resolution buttons, refinement_history column
- Buonissimo supplier added to price fetcher (chat_id=-5218925376)
- PDF price list handling rewritten with PyMuPDF: text-layer PDFs sent as PDF; image-only PDFs rendered page-by-page as JPEG
- TWB REPORT receipt checking: GM bot now monitors every new photo in REPORT group and replies in-thread if unclear
- Reply uses Telethon (not Bot API) to avoid MTProto/Bot API message ID mismatch for regular groups
- AI clarity rules tightened: only flags unreadable total amount or items — ignores missing vendor, date, phone, blank columns
- Receipt clarification learning: past answered Q&As stored in receipt_clarifications DB, injected into AI prompt as few-shot examples
- Backfilled 5 expense format examples into DB (mixed delivery+gas sheet, Atlas Ice, daily staff food money, food ingredient expense list, B2B delivery charges)
- run_check_report_photos.py: one-time historical scan — all 9 existing REPORT photos now pass clean (zero unclear after learning)
- run_backfill_clarifications.py: one-time script to import staff replies to historical clarification questions into DB
- Proposal conflict resolution: added [✏️ Explain...] button — owner can type free-text instruction to Opus instead of choosing preset buttons
- Global CLAUDE.md push protocol updated: any push/commit wording triggers full protocol (CLAUDE.md update + commit all + push)
- Hiring scoring engine built, tested, and refined: hire_bot/scorer.py + followups.py + readtime.py
  - Phase 1: auto_grade() → score_summary + is_correct per row; 0 contradiction rows written in Phase 1
  - Phase 2: detect_semantic_contradictions() → polished liar detection (tick=CORRECT + responsibility ≤ 1)
    Wrong tick + bad written = consistent failure → NOT flagged. hiring_contradictions stays clean.
  - 6 CONTRADICTION_PAIRS finalized: A2-Q13/C-Q8, A4-Q34/C-Q12, A4-Q38/C-Q12, A5-Q42/C-Q11 (updated),
    A6-Q58/C-Q16, A6-Q51/D3; + 1 written-vs-written pair: C-Q3/C-Q8
  - Risk profile: category-gated overrides; A2-Q13 → honesty 'weak'; A4-Q38 → quiet 'weak';
    A2-Q20 → experience 'red_flag'; both schedule questions wrong → schedule 'red_flag'
  - 13 curated bilingual follow-ups, capped at 5, eligibility blockers first
  - Per-language read-time: EN button vs EN words only; KH button vs KH words only
  - 7 repeatable tests in tests/test_hire_scorer.py (6 Phase 1 + 1 Phase 2 pre-scored)
- Session state schema added: attempt_status (9 states), abandoned_at_question_id, resume_count on attempts;
  resume_count + reopened_by on hiring_sessions; migration in migrations/2026_05_28_session_state_schema.sql
- run_session_state_migration.py deleted (one-time script, already run on production)
- hire_bot/bot.py built: token verify → identity confirm → intro block → 111 questions
  (yes/no, single-choice, D1 ranking, free-text) → follow-ups → end screen → owner notify
  Only accepts answer for currently expected question; deletion best-effort; 10-min timeout job
  Staff /create [Name] → one-time deep link; /reopen [attempt_id] → second resume
- hire_bot/sessions.py: DB layer; SELECT FOR UPDATE on open; check-before-insert on record_answer
- hire_bot/questions.py: QUESTION_SEQUENCE (111 items); D1 uses sorted(correct_order) for scrambled buttons
- run_hire_bot.py: entry point; requires HIRE_BOT_TOKEN in secrets repo (not added yet)
- Schema additions: hiring_contradictions table, risk_profile+score_summary on quiz_attempts, quiet_time_behavior+schedule_story_match on trial_outcomes
- Quiz bank live + reproducible: 111 questions in DB + migrations/2026_05_28_load_final_v3_quiz_questions.sql seed
- migrations/2026_05_28_scoring_schema.sql preserved — idempotent, safe to re-run
- Server stash list cleared (3 stale stashes dropped — all work already in main)
- Quiz bank audit passed: 0 duplicates, 0 missing answers, 23 critical tags correct, 8 verbal retest flags correct, D1 order correct
- Legacy paper import system live: hiring_assessments table + schema migration (2026_05_28_hiring_assessments_schema.sql)
  - assessment_id on hiring_feedback_points + hiring_contradictions; attempt_id made nullable on contradictions
  - staff_level_expectation, confidence, interpretation columns added to hiring_feedback_points
  - severity + source_type CHECKs expanded
- Vannary imported: candidate_id=24, assessment_id=2, 14 findings (leadership_audit, senior_staff)
  - Most critical: A2-Q13 risk_critical PENDING VERBAL RETEST (not confirmed dishonesty; tick position ambiguous)
    Retest Q stored in interpretation: "if you make a mistake and nobody sees it, what do you do first, and why?"
    If correct in person → downgrade to gap_medium. If defends hiding → escalate.
  - Training method gap (D3): corrected to senior_expected_gap (worker-level answer, senior-level gap)
  - Strengths: quiet-time instinct, problem chain detection (D2), customer/product awareness
  - map_confidence() added: medium_high → medium for per-finding field (assessment level retains 4-value scale)
- hiring_assessment_evidence table added: audit trail of photos/scans per assessment
  - file_hash (SHA-256, auto-computed when file available) + storage_status (8 precise values, not vague 'local_only')
  - storage_status: local_to_owner_phone | local_to_pc | server | cloud | telegram_file | chatgpt_only | missing | deleted
  - hash_file() helper in import scripts: fills file_hash automatically when path is known, NULL otherwise
  - Placeholder rule: update row #1 to photo #1 when filing — never mix NULL file_name with real file_name rows
  - Vannary evidence_id=1: storage_status='chatgpt_only' (photos uploaded to ChatGPT, not saved elsewhere)
- Part E hiring-facts added + structural fixes (sessions 18 + 18b + 18c):
  - hire_bot/questions.py: PART_E_ALWAYS (7 questions: E-A1a, E-A1, E-A2, E-A3a, E-A3b, E-A4, E-A5)
    E-A1a: structured "Can you start within 3 days?" (Yes/No/Not sure) — E-T3 fires on B or C
    E-A3 split into E-A3a (studying? Yes/No) + E-A3b (working? Yes/No) — no more keyword guessing
    evaluate_e_triggers(_rows=None): _rows injection for unit tests; DB load when None
    Triggers evaluated after PART_E_ALWAYS[-1] (E-A5) — not hardcoded "E-A5" in bot.py
  - hire_bot/sessions.py: get_answered_part_e_ids(), store_part_e_triggers(), load_part_e_triggers()
  - hire_bot/bot.py: cb_answer validates Part E questions correctly (was silently rejecting E-A3a/E-T1)
    _advance_part_e: triggers computed after PART_E_ALWAYS[-1], stored in DB immediately
    _after_main_quiz: reads DB for Part E answers — handles bot restarts without relying on user_data
  - Part E answers stored in hiring_quiz_answers (same table, E-* question IDs as FK)
  - tests/test_part_e.py: 30 unit tests, all pass (no DB required via _rows injection)
    Covers E-T1/E-T2/E-T3 structured + keyword paths, all-triggers, no-triggers, sequence ordering,
    get_next_part_e_question, get_part_e_progress
  - migrations/2026_05_28_part_e_and_ops_assessment.sql: original (8 questions, CHECK expansions)
  - migrations/2026_05_28_part_e_v2.sql: v2 structural fixes
    - E-A3 deactivated; E-A3a, E-A3b, E-T3 inserted with ON CONFLICT DO UPDATE
    - answer_sensitivity column: normal/owner_only (E-T2 = owner_only for salary data)
    - part_e_triggered text[] on hiring_quiz_attempts for DB-persisted trigger state
    - hiring_assessment_message_refs table: links findings to specific ops_messages rows
  - migrations/2026_05_28_part_e_v3.sql: v3 fixes (NOT YET RUN ON SERVER)
    - E-A1a question inserted (display_order=0, before E-A1)
    - All original Part E seeds converted to ON CONFLICT DO UPDATE
    - hiring_assessment_message_refs.message_id → ops_message_row_id (rename)
    - telegram_message_id column added; backfilled from ops_messages.message_id
    - UNIQUE constraint → hamr_unique_per_finding (assessment_id, finding_id, chat_id, ops_message_row_id)
    - 4 previously skipped Seth message refs re-inserted (multi-finding support now works)
    - staff_identity_aliases table created with Seth's 5 aliases seeded
- Seth (Phan Piseth) attendance assessment imported (session 18):
  - run_import_seth_assessment.py: creates candidate + ops_messages/attendance_review assessment + 6 findings
  - candidate: existing_staff, alias=Seth, day-shift service
  - findings: repeated lateness, payback pattern x4, multi-supervisor reporting (5 supervisors), no-show May 27, rotating excuses, accountability gap
  - ENTITY NOTE: Phan Piseth (Seth) ≠ Piseth Vinal (Hikaru, night bakery) ≠ Mr Pisey (SAM kitchen) — 3 separate people, never merge
  - SALARY PRIVACY: regular new staff salary OK in management group; supervisor/senior/chef/above is owner-only, never in any group
**EVIDENCE STATUS:**
  - assessment_id=2 (Vannary): COMPLETE — 12 photos linked, renamed 01_page.jpg–12_page.jpg, SHA-256 hashed
    Path: C:\Users\Papa\Documents\Bluetooth\Staff Assessments\Vannary\2026-05-13 leadership audit\
    storage_status=local_to_pc. Move to cloud/server when convenient.
  - Every future import: provide zip/photos at import time and evidence rows are inserted automatically
**MANUAL TEST CHECKLIST (before heavy B2B rollout / public hiring ads):**
  B2B:
  - [ ] True restart test: build cart → `systemctl stop twbshop-b2b` → start → tap old Confirm/Edit/Cancel/See Orders from Telegram
  - [ ] Live two-group test: two real B2B groups, verify carts/orders/locations never cross
  - [ ] Check actor logging is appearing in logs: `journalctl -u twbshop-b2b | grep 'b2b_confirm\|b2b_edit\|b2b_cancel\|Location set'`
  Hiring:
  - [ ] Live Telegram test with 5+ photos/files (send each separately, tap Done, verify count in message)
  - [ ] Verify `SELECT * FROM hiring_intake_media WHERE intake_id=X` shows all rows after live test
  - [ ] Confirm no AI call before TEST_UNLOCKED: `grep -i 'anthropic\|claude' logs/hire_bot.log` should be empty during intake
  - [ ] Start hire bot: `systemctl start twbshop-hire`
  - [ ] /create Test Candidate → full quiz flow
**Next task (immediate):**
  1. Run manual test checklist above
  2. User reviews 383 concern cards in GM chat (tap buttons as they go; /review for anything missed)
  3. Staff real names mapping: provide real names for aliases (Cat, Nakk, NY, O, Pew, Me Me, Seth, Boss TT, Chan Oun, Roth, por Khmer Bruce PP)
  4. Supplier price extraction [IN PROGRESS] — run `python run_extract_prices.py` on server
  5. Customer reactivation: extract names+phones from WOC DELIVERY PICTURES photos
  6. B2B bot rollout: add bot to all 24+ B2B customer groups
**Next task (hiring system):**
  1. Add HIRE_BOT_TOKEN to secrets repo, then test /create → deep link → candidate flow end-to-end
     Use this test path: /create Test Candidate → intro → 111 Qs → E-A1a=B (triggers E-T3) + E-A3a=A (triggers E-T1) + E-A3b=A (triggers E-T2) → all 3 triggers fire → E-Final → end screen → owner notify
  2. Wire up Phase 2 async scoring: after complete_session(), kick off draft_rubric_scores + detect_semantic_contradictions + build_risk_profile (background job or webhook)
  3. Intake funnel (hire_bot/intake.py) BUILT — all migrations run on server, 39 unit tests pass
     "cook have?" fix: hire_bot/bot.py handle_text now starts intake on ANY first message (no session),
       not just keyword matches. Bot is ad-linked — all first contacts are applicants.
     Edge case fixes (session 19d):
       - Photo/doc as first message: _handle_language_check detects has_media → skips to cv_pending
         _handle_document_or_photo: no-session → start_intake then handle_message (photo processed in 1 flow)
       - Blocked session + new text: start_intake handles cooldown; expired → reset to language_check
       - test_unlocked + new text: replies "quiz ready, use invite link" — does NOT reset session
     9/9 integration test scenarios pass: run_test_intake.py on server
     Next: add HIRE_BOT_TOKEN → start bot → run live Telegram test with real phone
     DESIGN NOTE: hiring_intake_sessions has flat UNIQUE (telegram_chat_id) — upsert overwrites old row
       on re-apply, no audit history. Future fix: partial unique index (active attempts only) or
       separate applicant_person → intake_attempts hierarchy. Not urgent before first real applicant.
  4. Insert Norin's 24-point bilingual feedback into hiring_feedback_points
  5. Link the 47 draft feedback_points to quiz question IDs (update source_ref, evidence_status from draft_unlinked to linked)
  6. Feed more questionnaire photos to ChatGPT → paste structured block here → import via same pipeline
  7. After 2–3 more person-specific import scripts: build generic structured-block importer
     (reads one standard block → inserts candidate + assessment + evidence rows + findings in one pass)
  8. Seth: formal accountability conversation, then update assessment findings with outcome
**Next task (new systems):** ChatGPT export ZIP pending (hiring bot questionnaire). Facebook Messenger export pending (Sara Bologna account).
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

## Operations Intelligence System — Planned (Phase 3)

A new system to be built alongside the existing bots. Three layers:

### Layer 1 — Data Collection (build first)
- **Telethon user-account listener** runs on the server as the owner's personal Telegram account (or a dedicated staff account added to all groups). Reads full message history + streams all new messages silently into a new `messages` DB table: sender, timestamp, group_id, text, media metadata.
- **One-time historical import script** reads Telegram JSON exports (exported manually from each group via the app) into the same table. Covers all history before the listener joined.
- **Photo analysis included from day 1** — every image sent in any group gets passed to AI vision.
- Both the listener and the existing bots share the same PostgreSQL database.

### Layer 2 — AI Analysis (all 4 tiers active from day 1, owner monitors costs and tones down)
| Tier | Model | Approx cost | Job |
|------|-------|-------------|-----|
| Free | None | $0 | Keyword summaries, counts, rule-based daily reports |
| Budget | Claude Haiku | ~$0.25/M tokens in | Daily digest — who said what, complaints flagged, order mentions, photo descriptions |
| Mid | Claude Sonnet | ~$3/M tokens in | Weekly deep analysis — staff behavior patterns, tone, operational issues |
| Premium | Claude Opus | ~$15/M tokens in | Special reports — long-context reasoning across weeks of data, hiring evaluation |

Scheduled jobs send analysis results to owner's private Telegram.

### Layer 3 — Hiring / Interview Bot (build after Layer 1+2)
**Access control — token-based, invite-only:**
- Candidates first contact a separate Telegram account (human contact, not the bot) to apply
- When candidate arrives in person, owner/staff runs `/approve @username` → bot generates a one-time deep link (e.g. `t.me/yourhirebot?start=abc123`)
- Only that token works — random people get silence from the bot
- Token is single-use and expires after a timeout (e.g. 30 min if not started)

**Interview session flow:**
- Candidate taps link → interview starts immediately in private chat with the bot
- Each question sent → candidate replies → bot deletes BOTH the question and the answer from the chat immediately after recording the answer → next question appears. Chat window stays visually empty throughout.
- If candidate goes inactive (no reply for 10 min) → session expires → token burned → owner notified: "Candidate @x abandoned at question N"
- Completed or abandoned: session locked, that token never works again, no way to restart

**Evaluation:**
- AI (Sonnet or Opus) scores answers against the rubric from the questionnaire system already designed with ChatGPT
- Owner receives a scored report in private Telegram

**To provide before building:**
1. ChatGPT export ZIP: ChatGPT → avatar → Settings → Data controls → Export data → download ZIP → upload here. Claude will read `conversations.json` and extract the hiring/interview system design.
2. The questionnaire document.

### Planned Repo Structure Addition
```
ops_intelligence/
├── listener.py         ← Telethon user-account message collector
├── importer.py         ← one-time Telegram JSON export loader
├── analysis.py         ← scheduled AI analysis jobs (all 4 tiers)
└── hire_bot/
    ├── bot.py          ← interview bot handler registration
    ├── sessions.py     ← token generation, session state, expiry
    └── evaluator.py    ← AI scoring against questionnaire rubric
run_listener.py         ← entry point: python run_listener.py (systemd: twbshop-listener)
run_hire_bot.py         ← entry point: python run_hire_bot.py (systemd: twbshop-hire)
```

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
