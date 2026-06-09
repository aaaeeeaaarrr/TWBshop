# Bakery Automation System — Project Rules & Status

---

## Real-Path Precision Standard — UNIVERSAL, ENFORCED (full local copy — self-contained)
REAL_PATH_PRECISION_STANDARD_VERSION: 2026-06-09-A

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

**Last updated:** 2026-06-09 (session 30 — LIVE staff entry wired for the attendance flows (gated,
inert until attendance_live); precision-standard v2026-06-09-A; Visal AL 10th→11th fix; root-caused
the "won't restore" bug = ad-hoc ssh scripts skipped commit)

**Session 30 (Jun 9) — LIVE STAFF ENTRY for attendance (gated OFF):**
- **What:** a real ACTIVE TWB staffer can now open their OWN attendance menu (Check-in / Late / About
  Work / About Me → AL, Special Leave, day-off swap, OT, My schedule) and fire the REAL submit_* as
  themselves. Same menus/callbacks/submit_* as the owner /test shell — NO behavior fork (Rule 1).
- **Entry:** non-owner /start or private text → if `attendance_live` AND active TWB staff →
  `attendance_ui.open_live_menu` (persona LOCKED to self; "🎭 Switch persona" hidden; pick/persona
  callbacks refused). Else → roll-call (unchanged). Check-in & late→payback-on-arrival stay on the
  already-live location path (`_handle_staff_location`).
- **Reason capture:** flow_state (DB, restart-safe) per the doc — `flow_save(uid,"att_pending",…)`;
  the staffer's next text completes the flow. Owner test path still uses user_data (unchanged).
- **Unified dispatcher:** `_att_test_dispatch` → `_att_dispatch(update, ctx, pend, *, live)`. live=True
  acts as self, requester_uid=self, routes to real recipients; live=False = owner test (routed to
  owner, is_test). **LIVE late = declare-only** (heads-up); the payback debt+picker appear on arrival
  via live location. TEST collapses declare+arrival (so the owner can test booking) — per the doc note.
- **Gating/safety:** everything behind `_attendance_live()` (still OFF) — module messages no one but
  the owner until go-live. Module docstring safety-contract updated to the live+test contract.
- **Verified:** suite 379 green (+10 new in tests/test_attendance_live_entry.py — persona self-lock,
  menu hides switch, armed gating, flow_state routing, LIVE late declare-only vs TEST collapse,
  unknown-uid rejected). py_compile OK. Real-staff DELIVERY provable only at go-live (single account +
  gate OFF) — the documented plan (owner role-play test in test mode covers the message shapes).
- Khmer WIRED into all 11 live reason/'go' prompts (bilingual EN·KH), mirroring the file's already-
  approved terms (បងៗ / ច្បាប់រៀបការ / មរណភាពគ្រួសារ / ប្រពន្ធសម្រាលកូន / ប្តូរថ្ងៃឈប់ / ទីតាំងផ្ទាល់);
  Latin kept for go/AL/OT/numbers. Real callback path proves the %-formatted ones (late/marriage/famf/
  ot) format without error. Owner should still eyeball via ChatGPT before go-live (my drafts, not yet
  owner-reviewed). The dispatcher confirmations were already bilingual.

**Session 30 (Jun 9) — tap-to-confirm + bilingual Back:**
- No-reason flows (own-sick, family-sick, family-death ×2, wife-birth) now show a **"✅ I confirm ·
  ខ្ញុំបញ្ជាក់"** button (`att:go`) instead of asking to type 'go'. New `_confirm_prompt` + bot
  `_att_go_callback` (owner→user_data pending, live→flow_state) fires the real submit_* via
  `_att_dispatch(reason="(confirmed)")`. `_att_dispatch` made callback-safe (no `message.text`).
- **Back button bilingual:** `_back_row` → "← Back · ត្រឡប់ក្រោយ" (applies everywhere).
- Suite 396 green (+ att:go-confirms, back-row-bilingual).

**Session 30 (Jun 9) — AL date-picker polish + day-off-aware count/span:**
- Selected dates now show **✅** (green-tick emoji) not the `✓` unicode; al_screen header trimmed to
  "You have X AL days left" (Eng+Kh) — dropped the "Choose dates (tap to ✓…)" line.
- **Day-off is never charged AL + from→to span:** `al.al_charged_days` / `al.al_span_label` /
  `al_day_count(day_off=…, non_working=…)`. Picking 3 days where one is the day off = **2 AL**; leave
  shows "Tue 23/06 → Thu 25/06", bridging the day off whether or not tapped. A genuine WORKING-day gap
  does NOT bridge.
- **Span bridges ANY absence, not just the weekly day-off** (owner): `non_working` set from new
  `database.staff_absent_dates(staff_id)` = approved AL + special-leave spans + swap day-off overrides.
  So a gap that's another AL/leave bridges into one from→to span (and isn't re-charged).
- **PUBLIC-HOLIDAY placeholder wired (empty):** `database.public_holidays()` reads gm_state
  ['public_holidays'] (JSON list, empty default) and is folded into `staff_absent_dates`. Add dates
  via **/holiday add YYYY-MM-DD** (owner/Tyty) — they then auto-bridge AL spans and cost NO AL / NO
  points, no code change. `set_public_holidays()` + `/holiday` (list/add/del) shipped. (Per-person
  paid-free grants could extend the same seam later.)
- Suite 394 green (+ al-day-off-excluded-and-span, updated summary test).

**Session 30 (Jun 9) — AL card redesign + edit-in-place on decision:**
- AL senior cards are now **English-only, BOLD space-separated dates** (`_al_summary`, HTML parse_mode);
  buttons English ("✅ Approve" / "❌ Not approve").
- **Decision edits the card in place** — `submit_al_request` stores each card's (chat_id, msg_id) in
  `bot_data["al_cards"][req_id]`; `_al_finalize` edits every card to "{request}…✅/❌ <verdict> by X and Y"
  and DROPS the old per-senior "Approved by X" new messages. Fallback recap if card refs lost (restart).
  Requester + Supervisors notices kept (bilingual; owner sees English via strip).
- `_att_send` now takes `parse_mode` and RETURNS the sent Message (so cards can be edited later).
- AUDIT (decision → new msg vs edit card): AL fixed. Already edit-in-place: OT yes/can't, OT reject,
  OT buyback, swap-partner, sick-papers, death-upgrade. STILL TO CONVERT (owner to decide): **swap
  SENIOR cards** (only the voter's card updates; others go stale) — best next candidate for the same
  edit-all-cards style; minor: OT owner-reject leaves the staff's pending card stale.
- Suite 391 green (+ _al_summary, _al_finalize-edits-in-place).

**Session 30 (Jun 9) — location-mix fix + swap/OT edit-in-place:**
- **LOCATION BUG (owner): DELIS staff leaked into TWB AL coverage.** `_al_availability_lines` built its
  roster from ALL active staff. Fixed → TWB only (excl Tyty). Audited every `staff_all` aggregation:
  also filtered `_seniors` (TWB only — defensive; no Delis senior today), the `/test` persona picker,
  and the dry-run sample. (The greeting/started report intentionally labels "(Delis)" — left as-is.)
  Org values are `TWB` / `DELIS`; the 4 seniors are all TWB; Tyty is TWB & not senior.
- **Swap senior cards now edit-in-place** (like AL): `_swap_partner_callback` stores card refs in
  `bot_data["swap_cards"]`; `_swap_apply` edits them all to "Day-off swap … ✅/❌ verdict" (no more
  stale non-voter cards).
- **OT owner-reject** now edits the staff's pending Yes/Can't card to "cancelled" (stored in
  `bot_data["ot_staff_card"]`) instead of leaving it stale + a new message; senior still memo'd.
- Suite 393 green (+ al-availability-excludes-Delis, swap-apply-edits-cards).

**Session 30 (Jun 9) — OT approval model = silence-is-approval (owner):**
- **OT no longer waits for owner approval.** Senior gives OT (Now or Later) → the STAFF is engaged
  IMMEDIATELY (Now = bank on the spot + buyback picker; Later = Yes/Can't ask) and the owner gets a
  **REJECT-ONLY** notice. Owner silence = approval; owner can veto until the OT START time
  (`_ot_started`); a Now grant that already banked is REVERSED on veto. Statuses: banked / staff_asked
  → booked / declined / rejected. Old pending_owner→approve gate removed.
- Files: `submit_ot_grant`, `_ot_owner_callback` (now veto-only + window check + bank reversal),
  `_ot_future_callback` (staff_asked→booked/declined), `_ot_started`, dispatcher OT confirm text.
- **OT confirmations show the real time window** (e.g. `4pm-5pm`), never "now" — `_ot_window()` (Now =
  shift-end→end; Later = date + window); used in the owner notice + the staff ask.
- **Staff consent FIRST for BOTH Now and Later:** submit_ot_grant now ASKS the staff Yes/Can't first
  (no auto-bank). NOW banks + offers buyback only in `_ot_future_callback` AFTER the staff accepts;
  LATER books. (Was: NOW auto-banked at grant without asking.)
- **Take-back ≠ payback:** earned-OT buyback slots are now at the shift EDGES (come in late / leave
  early) via new `payback.takeback_windows`, not the before/after-shift payback windows. Labeled
  🌅 in late / 🌙 leave early.
- **OWNER never gets Khmer — but ONLY in message BODIES, not the shell.** `attendance.strip_khmer()` is
  applied in `_att_send` when the recipient is the owner (test-routed previews + owner notices →
  English). The `/test` shell menus/screens STAY BILINGUAL so the owner previews exactly what staff see
  (owner corrected the scope, session 30 — do NOT strip the shell/menu). Live staff always bilingual.
- Suite 389 green (+ _ot_started, Later/Now ask-first, now-accept-banks, _ot_window, takeback_windows,
  strip_khmer).

**Session 30 (Jun 9) — /testseed + restart test-mode sync + /testmode diagnostic:**
- **/testseed [name]** (owner/Tyty): mirrors real approved ALs + open payback debts into is_test copies
  so TEST mode shows realistic data after a /testreset wipe (idempotent — clears prior test copies
  first; real rows never touched). `database.attendance_testseed()` + generic `_copy_test_rows` (schema-
  proof via information_schema). Ends the "re-seed Visal by hand each reset" loop.
- **Restart bug fixed:** `build_app` now restores `set_att_test(gm_get_state('attendance_test_mode'))`
  on boot — a restart no longer silently flips att_test_on() to False while the DB says test_mode=true
  (which made TEST mode show REAL rows instead of the is_test sandbox — likely source of earlier
  "ALs still gone in test" confusion).
- **/testmode no-confirmation: RESOLVED.** Temp debug log proved command reaches the handler (uid=owner,
  chat=private, args=['on']) and replies (sendMessage 200) after a clean restart. Earlier silence was a
  transient (process not processing updates during the overload/restart churn) — not reproduced, not a
  code bug. Debug line removed.
- **Give OT ⚡ Now picker fixed:** was listing the WHOLE roster; now only staff present right now —
  on shift OR finished < 1h ago (new `attendance_ui._present_now`, schedule-based, excludes day-off/AL-
  today). Empty → points to 📅 Later. Back from "to whom" now goes to the now/later screen.
- Suite 382 green (+ test_copy_test_rows, + test_present_now_for_ot, both DB-free).

**Session 30 (Jun 9) — precision standard + data fixes:**
- **Precision standard trimmed + sharpened (v2026-06-09-A):** 15 HARD RULES → 6 RULES (deduped, no
  teeth lost) in BOTH global ~/.claude/CLAUDE.md and project CLAUDE.md. New first-class **Rule 2 PROOF,
  NOT ECHO** — operation echo ≠ persisted state: PUSHED ≠ LIVE and WRITTEN ≠ SAVED (commit/close then
  re-read on a SEPARATE connection; RETURNING / return value / 2xx / enqueue-ack are not proof).
- **Visal AL corrected real+test:** req 17 was 9/10/12 but the 10th is his day off (Wed) → now 9/11/12
  approved (is_test=False); seeded matching test copy (req 20) + Por 240 test payback (debt 11).
- **Root cause of the "/testreset won't restore Visal's ALs" saga:** NOT a bot bug and NOT test
  isolation. My earlier inline `ssh … psycopg2.connect()` restore scripts never called commit
  (autocommit defaults off) → implicit ROLLBACK on process exit; RETURNING showed the in-txn value so
  it looked restored. The REPO write path (`shared/database.py::_db()` context manager) commits
  correctly — every bot/helper write is sound. Fix: ad-hoc DB scripts use _db() or autocommit + a
  fresh-connection readback (now Rule 2).

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
