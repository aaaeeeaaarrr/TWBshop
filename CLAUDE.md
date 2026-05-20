# Bakery Automation System — Project Rules & Status

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

### 1. Zero AI Runtime API Calls — Until Explicitly Told Otherwise
Do NOT import or use Anthropic, OpenAI, or any other LLM API for live bot interactions.
All natural language parsing must use rule-based matching: dictionaries, regex (`re`),
alias tables, and `difflib` fuzzy matching. When in doubt, ask the user to confirm
via Telegram buttons — never silently guess.

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
- **Database:** SQLite (local, simple, no server needed to start)
- **Fuzzy Matching:** `difflib` (standard library, no install needed)
- **Logging:** Python's built-in `logging` module — log ALL unmatched text patterns
  to a file so we can study them and improve matching rules over time

---

## Project File Structure (Target)
```
bakery-bot/
├── CLAUDE.md              ← This file
├── bot.py                 ← Telegram bot entry point and handler registration
├── orders.py              ← Order intake, menu matching, confirmation flow
├── database.py            ← SQLite setup, all read/write functions
├── summaries.py           ← Production totals and per-customer fulfillment lists
├── photos.py              ← Photo receiving, storage, and analyze_photo() stub
├── staff_monitor.py       ← Staff message logging and check_staff_message() stub
├── menu.py                ← Menu items, aliases, synonym tables
├── config.py              ← Bot token, group chat IDs, file paths (no secrets in code)
├── reminders.py           ← Deadline checks, missing photo alerts (scheduled jobs)
└── logs/
    └── unmatched.log      ← All text patterns the bot couldn't match
```

---

## Build Phases — Do These In Order

### Phase 1 — Foundation (Current Phase)
- [ ] Telegram bot connects and receives messages
- [ ] Bot can reply and send buttons
- [ ] SQLite database initialised with orders table
- [ ] Config file set up (token, chat IDs)
- [ ] Basic logging working

### Phase 2 — Customer Ordering
- [ ] Menu defined in menu.py with aliases
- [ ] Fuzzy text matching against menu items
- [ ] Confirmation flow with Telegram inline buttons (Confirm / Edit / Cancel)
- [ ] Confirmed orders saved to database
- [ ] Order rejection and retry handling

### Phase 3 — Production Summaries
- [ ] Aggregate confirmed orders into production totals
- [ ] Bot posts daily summary to bakery staff group
- [ ] Per-customer fulfillment list (name, items, pickup/delivery, time)

### Phase 4 — Photo Flow
- [ ] Staff can submit workstation cleaning photos
- [ ] Staff can submit fridge display photos
- [ ] Photos stored locally with timestamp and staff ID
- [ ] analyze_photo() stub in place — just stores photo, flags for manual review
- [ ] Missing photo deadline reminders (scheduled check)

### Phase 5 — Stock Sheets
- [ ] Staff can submit stock sheet photos
- [ ] Photos stored, analyze_photo() stub handles them
- [ ] Manual review fallback in place

### Phase 6 — API Layer (Add Later, One Feature at a Time)
- [ ] Stock sheet OCR via Claude API (first API feature)
- [ ] Workstation/fridge photo analysis via Claude API
- [ ] Staff message monitoring via Claude API (last — most complex)

---

## Key Decisions (Do Not Revisit Without Good Reason)
- **SQLite not PostgreSQL** — single server, simple bakery operation, no need for
  managed database at this stage. Can migrate later if needed.
- **Free-first architecture** — API features are additions, not the foundation.
  The bot must work fully without any API calls before any API calls are added.
- **No silent AI guessing** — every ambiguous input goes to a human confirmation step.
  The confirmation gate is not optional, it is the safety mechanism.
- **Telegram only** — no web dashboard, no separate app. Staff and customers
  already use Telegram. Keep the surface area small.

---

## Current Status
> Update this section at the end of every Claude Code session.

**Last updated:** [date]
**Phase:** 1 — Foundation
**Last completed:** Nothing yet — first session
**Next task:** Set up bot.py with Telegram connection and a basic echo reply
**Known issues:** None yet
**Notes:** —
