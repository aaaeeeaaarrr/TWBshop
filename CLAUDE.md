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
difflib) — AI is used only for photo analysis and staff message monitoring.
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

## Current Status
> Update this section at the end of every Claude Code session.

**Last updated:** 2026-05-27 (session 14)
**Phase:** Retail bot complete. B2B bot Phases 1 + 2 complete. Ops Intelligence Layer 1 complete. GM Manager bot live and in active use.
**Last completed:**
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
**Next task (immediate):**
  1. User reviews 383 concern cards in GM chat (tap buttons as they go; /review for anything missed)
  2. Staff real names mapping: provide real names for aliases (Cat, Nakk, NY, O, Pew, Me Me, Seth, Boss TT, Chan Oun, Roth, por Khmer Bruce PP)
  3. Supplier price extraction [IN PROGRESS] — run `python run_extract_prices.py` on server
  4. Customer reactivation: extract names+phones from WOC DELIVERY PICTURES photos
  5. B2B bot rollout: add bot to all 24+ B2B customer groups
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
