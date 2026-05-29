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

## Current Status
> Update this section at the end of every Claude Code session.

**Last updated:** 2026-05-30 (session 21 — Opus assessment plumbing)
**Phase:** Retail bot complete. B2B bot Phases 1+2 complete. GM Manager bot live. Hiring system: intake + quiz + Haiku intake intelligence + Opus assessment plumbing built. Chaos tests: B2B 42/42, Hire 57/57. Assessment decision tests: 17/17.

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

**Pending (before Opus assessment is truly live):**
- Opus system prompt calibration with approved examples (waiting on clean samples)
- Wire correction_flow handlers into hire_bot/bot.py (callback handler for correction: prefix)
- Wire offer approval into hire_bot/bot.py (owner callback for offer:owner_approve)
- Start hire bot service: systemctl start twbshop-hire
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
