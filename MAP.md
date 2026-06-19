# MAP — task → where to look (the router)

> **Open this FIRST for any task.** Find your area → read the listed files + the *Read-first* law/doc →
> `grep docs/HISTORY.md` for the area before changing anything → heed the ⚠ gotcha. This is the index
> that keeps a cold session from guessing (the failure on 2026-06-19: claiming gaps without checking).
>
> **RULE (mechanical):** any file move / rename / new subsystem updates this map IN THE SAME COMMIT.
> `tests/test_map_integrity.py` fails the build if a path here doesn't exist, or a code package is
> unmapped — so a lying map can't ship. (It can't check that *new files inside an area* were added, or
> that a gotcha is still accurate — that stays human. Index only; never let this grow into prose.)

---

## Attendance — check-in / check-out / no-show  ·  ⚠ LIVE (real staff, payroll-adjacent)
- **Files:** `gm_bot/bot.py` (scheduler, location handler, jobs) · `gm_bot/attendance_ui.py` (menus + `resolve_day`) · `gm_bot/checkin.py` (verdict, auto-checkout) · `gm_bot/attendance.py`
- **Read-first:** `docs/ATTENDANCE_SYSTEM_DETAILED.md` · `docs/ATTENDANCE_SYSTEM_MAP.md` · `docs/ATTENDANCE_TEST_MODE.md` · `docs/STATEFUL_MENU_PATTERNS.md`
- **History:** grep `docs/HISTORY.md` sessions 31–42.
- **⚠ Gotchas:** overnight shifts bind to the SHIFT-START date (not calendar day) · go-live grace · everything is `is_test`-scoped · LIVE since 2026-06-16 — read-only on prod first, prove on staging, deploy by TAG in a quiet window.

## AL · OT · payback · sick · swap · special-leave · points  ·  ⚠ LIVE, MONEY/BALANCE
- **Files:** `gm_bot/al.py` · `gm_bot/ot.py` · `gm_bot/payback.py` · `gm_bot/sick.py` · `gm_bot/swap.py` · `gm_bot/special.py` · `gm_bot/points.py` · `gm_bot/late.py` · `gm_bot/lateness.py` · `resolve_day` in `gm_bot/attendance_ui.py` · `shared/database.py` (al_*, payback_*, ot_*)
- **Read-first (TRIPWIRE):** `docs/STATE_INTEGRITY_LAWS.md` (S1–S5) BEFORE any balance/state change · `docs/SCHEDULE_RESOLUTION_MODEL.md` · `docs/AL_DEDUCTION_REDESIGN.md`
- **History:** grep `docs/HISTORY.md` sessions 31–42; open data ops in `docs/ACTIONS_LEDGER.md`.
- **⚠ Gotchas:** deduct-at-approval + refund-on-cancel · F14 same-date claims serialized by a pg advisory lock · settle banks via an atomic claim (no double-bank) · ONE resolver (`resolve_day`) decides a day.

## Audit · watchdog · session-closer · resilience
- **Files:** `gm_bot/audit.py` (`run_audit` + validators) · `gm_bot/bot.py` (`_auto_audit_job`, `_live_watchdog_job`, `_session_closer_job`, `_watchdog_delta`) · `run_collection_watchdog.py`
- **Read-first:** `docs/RESILIENCE.md` (every down-safeguard + known gaps + fire drill)
- **⚠ Gotchas:** self-heal first (systemd `Restart=always`), alarm only on PERSISTENT failure · live watchdog vs test watchdog — exactly one runs · `/audit` is the cross-row backstop the watchdog can't replace.

## Accountant (expense / receipts / payments)  ·  staging only, INERT (no live service)
- **Files:** `accountant/bot.py` · `accountant/capture.py` · `accountant/db.py` · `run_accountant.py` · `scripts/run_accountant_local.py`
- **Read-first:** `docs/REPORT_SYSTEM_DESIGN.md`
- **⚠ Gotchas:** P2 money matcher is HIGH-RISK, per-step owner approval, no live money · uses `shared/ai_client.py::extract_receipt` (Sonnet) · Expense group `-5417163768`, TEST supplier `-5406470751`.

## Stock (catalog / counts / reorder)  ·  staging only, INERT
- **Files:** `stock/catalog.py` · `stock/catalog_data.py` · `stock/db.py` · `stock/order_brain.py` · `stock/sync.py` · `gm_bot/stock_gateway.py` (GM seam) · `shared/stock_shared.py` (shared tables) · `run_stock.py`
- **Read-first:** `docs/STOCK_APPSHEET_SETUP.md`
- **⚠ Gotchas:** `gm_bot/stock.py` is a soon-to-be-removed duplicate of `stock/order_brain.py` (drift-guarded) · gateway hidden until `STOCK_APPSHEET_URL` set · builds on shared `acc_items`/`stock_movements`.

## B2B wholesale bot  ·  LIVE (customer-facing)
- **Files:** `b2b_bot/bot.py` · `b2b_bot/orders.py` · `b2b_bot/order_parsing.py` · `b2b_bot/menu_handlers.py` · `b2b_bot/recurring.py` · `b2b_bot/billing.py` · `b2b_bot/summaries.py` · `b2b_bot/customers.py` · `run_b2b_bot.py`
- **Read-first:** `docs/B2B.md`
- **⚠ Gotchas:** PP-clock dates via `shared/clock.py` · b2b service is intentionally stopped at times — check before assuming live.

## Retail bot  ·  LIVE (customer-facing)
- **Files:** `run_bot.py` (entry — original retail bot)
- **⚠ Gotcha:** oldest subsystem; grep before editing. (Map entry thin — enrich when next worked on.)

## Hiring intake + quiz + assessment bot
- **Files:** `hire_bot/bot.py` · `hire_bot/intake.py` · `hire_bot/sessions.py` · `hire_bot/questions.py` · `hire_bot/scorer.py` · `hire_bot/assessment_runner.py` · `hire_bot/correction_flow.py` · `hire_bot/offer_flow.py` · `run_hire_bot.py`
- **History:** grep `docs/HISTORY.md` sessions 18–22.
- **⚠ Gotcha:** AI-call budget rules (max 2 Haiku/applicant pre-test) — see CLAUDE.md Arch Rule 1.

## Listener / ops-intelligence (the read-only eyes)
- **Files:** `ops_intelligence/listener.py` · `ops_intelligence/importer.py` · `ops_intelligence/analyze_chats.py` · `ops_intelligence/price_list_fetcher.py` · `run_listener.py`
- **⚠ Gotchas:** Telethon session file is auth — NEVER run two clients on one session · session backed up to the secrets repo (not in `bootstrap.py --sync`).

## Shared infrastructure
- **Files:** `shared/database.py` (ALL DB + the fail-closed `TWBSHOP_ENV` switch) · `shared/ai_client.py` (the ONLY place the anthropic SDK is used) · `shared/error_handler.py` · `shared/runtime_guard.py` · `shared/clock.py`
- **Read-first:** CLAUDE.md Arch Rules 1–6.
- **⚠ Gotchas:** every AI call goes through `shared/ai_client.py` · `TWBSHOP_ENV` unset RAISES (no silent prod) · balance writes flip status FIRST.

## Deploy / ops
- **Files:** `scripts/verify_live.py` (HEAD==origin + active + marker) · `scripts/checkpoint.ps1` (the `push` engine) · `pull.ps1`
- **Read-first:** CLAUDE.md "Deploy Discipline" + "push/pull words".
- **⚠ Gotchas:** deploy-from-TAG (server runs a tag, not main tip) · restart only the changed service · verify independently after.

## Multi-lane (hub + lane worktrees)
- **Files:** `parallel_lanes.json` (file→lane ownership) · `scripts/lane_guard.py` · `scripts/make_lane.ps1` · `scripts/checkpoint.ps1` · `scripts/integration_audit.py` · `scripts/monitor_bot.py`
- **Read-first:** `docs/MULTI_LANE_PLAYBOOK.md` · `docs/PARALLEL_LANES.md`
- **⚠ Gotcha:** lanes never edit `CLAUDE.md`/Current Status (hub owns it) → use `CLAUDE.local.md`.

## Governance / standards / what-was-decided
- **Files:** `CLAUDE.md` (the Standard + Arch Rules + Current Status) · `docs/BEDROCK.md` · `docs/STATE_INTEGRITY_LAWS.md` · `docs/STATEFUL_MENU_PATTERNS.md` · `docs/GOVERNANCE_INVENTORY.md` · `docs/ACTIONS_LEDGER.md` (open data ops) · `docs/HISTORY.md` (the full archive — grep it)
- **⚠ Gotcha:** before claiming anything is missing/broken/a-gap, grep `docs/HISTORY.md` + the area's doc and cite it, or say "let me check" and check. An unverified gap-claim is a violation, same as a false "done."
