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

**Last updated:** 2026-05-25
**Phase:** Retail bot complete. B2B bot Phases 1 + 2 complete. Infrastructure complete.
**Last completed:** Dispatch reminders to shop staff phone (DISPATCH_REMINDER_TELEGRAM_ID = 1271537077) — 1h before fulfillment, message with items+costs+buttons. Confirm button: "🚗 Already in delivery" / "✅ Ready for Pickup". Snooze buttons stacked vertically one per row: "Remind me in 30/20/10 min", auto-stripped as time runs out (≤45m: no 30m, ≤35m: no 20m, ≤25m: no 10m). Snooze deletes message + reschedules via DB. Confirm marks DELIVERED/READY FOR PICKUP (LATE prefix if after fulfillment time). 5min escalation to staff group if unconfirmed. 60s polling job, fully restart-safe — message deletion has no effect, all state in b2b_dispatch_reminders table. Also added pull.ps1 for full pull procedure (git + bootstrap sync + pip install).
**Next task:** None defined
**Known issues:** None
**Notes:**
- Retail bot: `python run_bot.py` — systemd: `twbshop-retail`
- B2B bot: `python run_b2b_bot.py` — systemd: `twbshop-b2b`
- Set ANTHROPIC_API_KEY in config.py to enable AI features (retail bot only for now)
- Business names live in `b2b_bot/customers.py` — add group chat ID + name, restart bot to register new customer

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
