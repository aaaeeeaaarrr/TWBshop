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

## Connectivity Reference
*Broken something? Connectivity checks (SSH · GitHub · DO API/droplet/db · Anthropic · Telegram) → `docs/CONNECTIVITY.md`.*

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
*Need the file layout? → `docs/REPO_STRUCTURE.md` (or just read the filesystem).*

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

## GM Subsystems — status index
*One-line status; full detail → `docs/SUBSYSTEMS.md` (+ the per-topic docs named there).*
- **REPORT finance tracking (GM bot):** LIVE.
- **Supervisors/Management — lateness·AL·tagging:** mostly BUILT; group ladder SILENCED (moved to private-DM).
- **Delivery System (WOC):** SHELVED.
- **Staff Registry · Ex-staff offboarding · Paperless /stock:** BUILT (stock overhaul + 143-item CSV import PENDING).
- **Private-DM Attendance Overhaul:** IN BUILD, gated OFF (current focus) → `docs/ATTENDANCE_SYSTEM_DETAILED.md` + `..._MAP.md` + `..._TEST_MODE.md`.
- **STRATEGIC — POS convergence:** keep our Postgres source-of-truth; AppSheet is a throwaway stock front-end.
- **GM Backlog & Roadmap:** → `docs/ROADMAP.md` (reference, not an auto-run list).
- **Operations Intelligence System:** mostly BUILT (Phase 3 — listener + import + AI tiers + hire bot).

---

## Current Status
> Update this at the end of every session. The only source of truth for what's next. Old session logs (19–31) → docs/HISTORY.md.

**Last updated:** 2026-06-10 (session 31 — HIGH-RISK guard PROVEN LIVE + HARDENED + made UNIVERSAL +
named **Bedrock** (Standards+Guards+Ratchet) and converged via 3 advisor passes → `docs/BEDROCK.md`.
Architecture review CLOSED; 5 deltas queued. ⚠ The `#HIGHRISK-OK` marker is DEPRECATED — Claude can
type it = self-approval; catastrophic actions will switch to block-and-owner-runs-manually next session)

**Session 31 (Jun 10) — AL hours-display + reason-prompt becomes an "awaiting approval" card (owner):**
- **"Fractional deduction" wording removed** everywhere (the hours-AL detail + the ③ HOURS-AL help
  label). Hours-AL now shows the **actual AL amount** ("AL: Mon 23/06 · 9pm–12am = 0.3 AL") instead of
  the meaningless "Hours AL" — `fractional_al(f,t,shift_len) × charged-days`, day-offs excluded
  ("Day off = Free").
- **Reason prompt no longer sits stale.** When a flow captures its prompt (`_arm_pending` now stores
  the prompt message's coords for EVERY flow), typing the reason **edits that message in place** into a
  card: same info + `📝 <reason>` + `⏳ Awaiting approval · កំពុងរង់ចាំការអនុម័ត` (done in
  `_att_dispatch`'s `confirm`, gated on `pend['_summary']`). **Wired:** AL (days + hours), the new
  shift-redefine (`scp`), day-off swap. **Not wired (by design):** sick/marriage/death/birth (already
  tappable confirm CARDS, not stale prompts) and the dormant old Now/Later OT picker (slated for removal).
- Suite **420** green (+ `test_dispatch_al_edits_prompt_into_awaiting_card`; the 3 `_arm_pending`
  signature tests updated to pass an `update`). Owner verifies the live edit in `/test` post-deploy.

**⏳ IN PROGRESS (session 31) — OT / shift-redefine rebuild → full settled design in `docs/OT_DESIGN.md`.**
Owner redesigned OT into a UNIFIED **"redefine-a-shift"** model: a senior retimes / moves / extends a
working day's shift, the staff approves, and OT is EMERGENT = hours worked beyond the normal shift
length. Normal late/leave-early/no-show rules apply (no special OT −10 card). PB and OT are ONE currency
(an extension/earned-OT clears payback first, then banks; points stay separate; agreed OT shields the PB
ladder before deadline). Cancellation = re-edit or absence. Day-off payback (within regular shift hours,
natural cap). **DONE + tested:** spec + decision log; `gm_bot/ot.py` length-based OT +
`split_ot_pb`/`apply_ot_to_pb`/`settle_shift` + `end_option_tags` ladder; `payback.dayoff_*` primitive;
`shift_changes` table (additive) + lifecycle CRUD; **propose** (`submit_shift_change` + approval card) +
**approve/decline** (`_shift_change_callback`, registered `att:sc:`); **bank-at-checkout**
(`_settle_redefined_shift` in `_handle_staff_location` — settle + PB-net + 14h cap, is_test end-to-end
proven); **day-off payback slot WIRED** into `_payback_slot_keyboard`; **PICKER UI REBUILT + WIRED**
(`attendance_ui` `sc_*` screens under `att:scp:` — staff→work-day→[Change time | Change day→nearest 2
day-offs]→start ladder→end ladder w/ +PB/+OT tags→reason→`submit_shift_change`; entry "➕ Give OT / change
shift"; bot dispatch `flow=="shift"`; old Now/Later chain dormant). The new flow shows in `/test`.
**NEXT:** **attendance USES the redefined times** (`_checkin_scheduler_job` + verdict read
`shift_change_active` so check-in/out fire at the redefined start/end and lateness is vs the redefined
start); the **shield** (approved OT pauses the PB ladder); remove the dormant old OT picker; `/test`
harness polish (a simulate-checkout that shows the banking). Honest: picker tap-through is owner-verified
in `/test`, not unit-tested (gated UI). attendance_live=OFF, attendance_test_mode=OFF.

**▶ RESUME HERE (session 31 → next session): BEDROCK deltas, then prove, then attendance.**
Bedrock (Standards+Guards+Ratchet) is converged + documented → **`docs/BEDROCK.md`** (read it first).
Architecture review is CLOSED — no more abstract review; the next move is PROOF. Order (CORRECTED —
OS boundary moves LAST so guard edits don't need elevation mid-build):
  1. **Claude:** apply deltas 1/3/5 to the real files — the final guard write also REMOVES the
     `#HIGHRISK-OK` marker (catastrophic set → block-and-owner-runs-manually) · gate secrets at
     commit/push/upload not just write · give the Ratchet a removal trigger.
  2. **Fresh-session wiring test (only real proof):** bypass mode — a catastrophic action with NO
     override must die on exit 2; verify the owner-run path; grep for a DB write path that dodges the
     guard.
  3. **OWNER locks** the GLOBAL enforcing files (`~/.claude/hooks/*.py` + `~/.claude/settings.json`),
     elevated shell — owner→Administrators/SYSTEM, Papa→ReadAndExecute. FEASIBILITY VERIFIED session 31
     (Claude non-elevated + UAC prompts → real boundary; see docs/BEDROCK.md). Read the ACL back to prove.
  4. Then attendance: (a) **Bank-on-completion for OT** (the only fix for "leave early, keep OT pay");
     (b) **Go-live prep** (owner role-play → /testreset → /testmode off → greeting + 📋 Menu → flip
     attendance_live). **No universal tests gate** (project-opt-in, push/deploy-time only).
NOTE: PowerShell-tool coverage + global hooks are now ACTIVE this session (verified — a PS call to a
guard path hard-blocked). attendance_live=OFF, attendance_test_mode=OFF.

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
*Working on the B2B wholesale bot? Full design rules, repo structure, and build phases → `docs/B2B.md`.*
