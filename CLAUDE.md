# Bakery Automation System — Project Rules & Status

---

## Session Start — Run These Checks Automatically

At the start of every session in this folder, immediately run ALL checks below
and report results before doing anything else. Run connectivity checks and
expiry checks in parallel for speed.

### Connectivity checks

| # | What | How to check | Good result |
|---|------|-------------|-------------|
| 1 | **SSH — server** `129.212.228.102` | `ssh -i ~/.ssh/twbshop_server -o StrictHostKeyChecking=no -o ConnectTimeout=6 root@129.212.228.102 "echo ok"` | `ok` |
| 2 | **GitHub** push access | `git ls-remote origin` | lists refs without error |
| 3 | **DigitalOcean API** | `curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $(python3 -c 'import sys; sys.path.insert(0,\".\"); import secrets; print(secrets.DO_API_TOKEN)')" https://api.digitalocean.com/v2/account` | `200` |
| 4 | **DigitalOcean — droplet** | `curl -s -H "Authorization: Bearer $(python3 -c 'import sys; sys.path.insert(0,\".\"); import secrets; print(secrets.DO_API_TOKEN)')" https://api.digitalocean.com/v2/droplets \| python3 -c "import sys,json; d=json.load(sys.stdin); print(d['droplets'][0]['status'])"` | `active` |
| 5 | **DigitalOcean — database** | `curl -s -H "Authorization: Bearer $(python3 -c 'import sys; sys.path.insert(0,\".\"); import secrets; print(secrets.DO_API_TOKEN)')" https://api.digitalocean.com/v2/databases \| python3 -c "import sys,json; d=json.load(sys.stdin); print(d['databases'][0]['status'])"` | `online` |
| 6 | **Anthropic API** | `curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: $(python3 -c 'import sys; sys.path.insert(0,\".\"); import secrets; print(secrets.ANTHROPIC_API_KEY)')" -H "anthropic-version: 2023-06-01" https://api.anthropic.com/v1/models` | `200` |
| 7 | **Telegram — retail bot** | `curl -s "https://api.telegram.org/bot$(python3 -c 'import sys; sys.path.insert(0,\".\"); import secrets; print(secrets.BOT_TOKEN)')/getMe" \| python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['username'] if d.get('ok') else 'FAIL')"` | bot username |
| 8 | **Telegram — B2B bot** | same but with `secrets.B2B_BOT_TOKEN` | bot username |

### Expiry dates — warn if ≤ 30 days away

| Service | Expiry | How to check days left |
|---------|--------|----------------------|
| DO API Token | never expires | — |
| Telegram bot tokens | never expire | — |
| Anthropic API key | no expiry (usage-based billing) | — |
| DO Droplet (`twbshop`) | monthly billing — no fixed expiry | check DO account is active |
| DO Database (`twbshop-db`) | monthly billing — no fixed expiry | check status = online |

### Report format

Print this table every session start:
```
── Connectivity ──────────────────────────
SSH server            ✓ connected
GitHub                ✓ reachable
DigitalOcean API      ✓ active
DO Droplet            ✓ active
DO Database           ✓ online
Anthropic API         ✓ ok
Telegram retail       ✓ @WineB_bot
Telegram B2B          ✓ @twb_b2b_bot

── Expiry ────────────────────────────────
DO API Token          ✓ no expiry
```
If anything is ✗ or ≤ 30 days from expiry, flag it clearly and say what to do.

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
For every future AI-powered feature, create the function stub now with a placeholder return.
Do not leave these out — they are the connection points for the API layer later.

Stubs to include from the start:
```python
def analyze_photo(image_bytes: bytes, photo_type: str) -> dict:
    # Placeholder: will connect to Claude API later
    # photo_type: "workstation" | "fridge" | "stock_sheet"
    return {"status": "pending", "notes": "manual review required"}

def check_staff_message(text: str, context: list) -> dict:
    # Placeholder: will connect to Claude API later
    return {"action": "none", "flag": False}
```

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
TWBshop/                        ← one GitHub repo for the whole business
├── CLAUDE.md                   ← project-wide rules and status
├── config.example.py           ← all settings for all systems (copy → config.py)
├── requirements.txt            ← combined dependencies
├── run_bot.py                  ← entry point: python run_bot.py
│
├── shared/                     ← imported by any system
│   ├── database.py             ← SQLite: all tables and queries
│   └── ai_client.py            ← Anthropic client (vision + text)
│
├── telegram_bot/               ← Telegram bakery bot (current system)
│   ├── bot.py                  ← handler registration and scheduled jobs
│   ├── orders.py               ← order intake, menu matching, confirmation flow
│   ├── menu.py                 ← menu items, aliases, synonym tables
│   ├── summaries.py            ← production totals and fulfillment lists
│   ├── photos.py               ← photo receiving, storage, AI analysis
│   ├── staff_monitor.py        ← staff message logging and AI monitoring
│   └── reminders.py            ← missing photo deadline checks
│
├── photos/                     ← shared photo storage (gitignored)
└── logs/                       ← shared logs (gitignored)
    └── unmatched.log           ← text patterns the bot couldn't match
```

### Adding a new system
1. Create a new folder at the root (e.g. `web_dashboard/`)
2. Import shared code with `from shared.database import ...`
3. Add a launcher at root if needed (e.g. `run_dashboard.py`)
4. Add its dependencies to `requirements.txt`
5. Document its phases in this CLAUDE.md under a new section

---

## Build Phases — Do These In Order

### Phase 1 — Foundation (Current Phase)
- [x] Telegram bot connects and receives messages (bot.py)
- [x] Bot can reply and send buttons (orders.py — InlineKeyboardMarkup)
- [x] SQLite database initialised with orders table (database.py)
- [x] Config file set up (token, chat IDs) — config.example.py; copy to config.py
- [x] Basic logging working (all modules use logging)

### Phase 2 — Customer Ordering
- [x] Menu defined in menu.py with aliases (plurals, misspellings, short forms)
- [x] Fuzzy text matching against menu items (difflib, noise stripping, word-numbers)
- [x] Confirmation flow with Telegram inline buttons (Confirm / Edit / Cancel)
- [x] Confirmed orders saved to database
- [x] Order rejection shows full menu; /menu command added

### Phase 3 — Production Summaries
- [x] Aggregate confirmed orders into production totals
- [x] Bot posts daily summary to bakery staff group (scheduled via JobQueue, SUMMARY_HOUR/MINUTE in config)
- [x] Per-customer fulfillment list (name + items, sorted alphabetically, sent to staff group)
- [x] /summary staff command for manual trigger; STAFF_USER_IDS access control

### Phase 4 — Photo Flow
- [x] Staff can submit workstation cleaning photos
- [x] Staff can submit fridge display photos
- [x] Photos stored locally with timestamp and staff ID; recorded in photo_submissions table
- [x] analyze_photo() stub in place — stores photo, flags for manual review
- [x] Missing photo deadline reminders (scheduled check via JobQueue at REMINDER_HOUR:MINUTE)

### Phase 5 — Stock Sheets
- [x] Staff can submit stock sheet photos (added to type-button menu)
- [x] Photos stored, analyze_photo() stub handles them
- [x] Manual review fallback: staff group notified immediately on receipt; not in REQUIRED_PHOTO_TYPES (on-demand, not daily)

### Phase 6 — API Layer
- [x] Stock sheet OCR via Claude API — items extracted, formatted, posted to staff group
- [x] Workstation/fridge photo analysis — issues posted to staff group; pass logged silently
- [x] Staff message monitoring — flags posted to staff group with ALERT/URGENT prefix
- [x] Graceful fallback to manual-review mode when ANTHROPIC_API_KEY is not set

---

## New Machine Setup

Just say: **pull**

Claude Code clones the repo, syncs all secrets and SSH keys, and runs bootstrap automatically.
You will be asked for your GitHub PAT (`repo` scope) once — everything else is handled.

PAT creation: https://github.com/settings/tokens
Secrets live in: `github.com/aaaeeeaaarrr/twbshop-secrets` (private)
Claude Code permissions sync automatically via `.claude/settings.json` in this repo.

---

## Workflow Rules (Apply on Every Machine)
- **Always commit before pushing.** The user works across multiple machines. If you push without committing first, the other machine sees nothing when it pulls. When the user says "push", always: check for uncommitted changes → commit → pull --rebase → push.
- **Smart pull.** When the user says "pull", always: run `git pull --rebase`, then check if `secrets.py` exists. If it does not exist, automatically run `python bootstrap.py` without asking — the user should never have to type that themselves.

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

**Last updated:** 2026-05-23
**Phase:** Retail bot complete. B2B bot Phase 1 complete. Infrastructure complete.
**Last completed:** Full automation system — automatic signals (push→status, pip→requirements, orphan detection, schema migration flags, new token detection, server detection), global checklist in ~/.claude/CLAUDE.md, bootstrap downloads checklist to new machines
**Next task:** B2B Phase 2 — recurring weekly orders (standing orders with confirmation flow)
**Known issues:** None
**Notes:**
- Retail bot: `python run_bot.py`
- B2B bot: `python run_b2b_bot.py`
- Set ANTHROPIC_API_KEY in config.py to enable AI features (retail bot only for now)

---

## B2B Orders Bot — b2b_bot/

Handles wholesale orders from restaurant and bar customers via their own Telegram groups.

### B2B Design Rules
- Group chat = the customer. Anyone in the group can order.
- Re-order same day: bot asks "is this extra?", then re-confirms full merged order.
- Gram-required items: pulls from history first, falls back to standard grams (shown in confirmation).
- Attributes (e.g. sesame type): pulls from history first, falls back to menu standard.
- Delivery/pickup: stored per group. New group asked once on first order.
- 9pm Phnom Penh (UTC+7 = 14:00 UTC): nightly summary to B2B staff group.
- No AI in Phase 1 — rule-based matching only.

### B2B Repo Structure
```
b2b_bot/
├── bot.py         ← handler registration and 9pm scheduled job
├── menu.py        ← B2B menu items, grams, attributes, aliases (edit to add items)
├── customers.py   ← group chat ID → business name registry (edit to add customers)
├── orders.py      ← parsing, history resolution, confirmation flow
└── summaries.py   ← nightly production total + per-customer breakdown
run_b2b_bot.py     ← entry point: python run_b2b_bot.py
```

### B2B Build Phases
- [x] Phase 1 — Foundation + full order flow (menu, customers, history, confirmation, delivery, 9pm summary)
- [ ] Phase 2 — Recurring weekly orders (standing orders with 7am/1pm/6pm confirmations, 9pm cutoff)
  - DB table: b2b_recurring_orders (group_chat_id, items_json, day_of_week, status: active/paused/cancelled)
  - Saturday bot sends at 7am, reminds at 1pm if no reply, reminds again at 6pm, drops at 9pm if still no reply
  - Customer presses [Confirm] or [Skip this week] — silence = no order, nothing baked
  - Cancelled permanently: status = 'cancelled', record kept for history, bot never sends again
- [ ] Phase 3 — Claude API for smarter matching and future AI features
