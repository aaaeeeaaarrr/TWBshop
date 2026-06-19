# MAP — task → where to look (the router)

> **Open this FIRST for any task.** Find your area → read the listed files + the *Read-first* law/doc →
> `grep docs/HISTORY.md` for the area before changing anything → heed the ⚠ gotcha. This is the index
> that keeps a cold session from guessing (the failure on 2026-06-19: claiming gaps without checking).
>
> **RULE (mechanical):** any file move / rename / new file / new subsystem updates this map IN THE SAME
> COMMIT. `tests/test_map_integrity.py` fails the build if: a path here doesn't exist · a `file::symbol`
> anchor's symbol is gone (logic moved) · a code package is unmapped · a package `.py` is neither indexed
> here nor in **MAP-IGNORE** (bottom). What it still CAN'T check (human): a gotcha whose file+symbol exist
> but whose *behaviour* silently changed. So gotchas POINT to the law/test that owns the truth — never
> assert a fact the map can't verify. Index only; never let this grow into prose.

---

## Attendance — check-in / check-out / no-show  ·  ⚠ LIVE (real staff, payroll-adjacent)
- **Files:** `gm_bot/bot.py` (scheduler, location handler, jobs) · `gm_bot/attendance_ui.py::resolve_day` (the ONE day-resolver) · `gm_bot/checkin.py::can_auto_checkout` · `gm_bot/attendance.py` · `gm_bot/flow.py` (flow-state engine under every ladder)
- **Read-first:** `docs/ATTENDANCE_SYSTEM_DETAILED.md` · `docs/ATTENDANCE_SYSTEM_MAP.md` · `docs/ATTENDANCE_TEST_MODE.md` · `docs/STATEFUL_MENU_PATTERNS.md`
- **History:** grep `docs/HISTORY.md` sessions 31–42.
- **⚠ Gotchas:** overnight shifts bind to the SHIFT-START date, not the calendar day · go-live grace · everything is `is_test`-scoped · LIVE since 2026-06-16 → read-only on prod first, prove on staging, deploy by TAG in a quiet window.

## AL · OT · payback · sick · swap · special-leave · points · payroll  ·  ⚠ LIVE, MONEY/BALANCE
- **Files:** `gm_bot/al.py` · `gm_bot/ot.py` · `gm_bot/payback.py` · `gm_bot/sick.py` · `gm_bot/swap.py` · `gm_bot/special.py` · `gm_bot/points.py` · `gm_bot/late.py` · `gm_bot/lateness.py` · `gm_bot/payroll.py` · `gm_bot/attendance_ui.py::resolve_day` · `shared/database.py` (al_*, payback_*, ot_*)
- **Read-first (TRIPWIRE):** `docs/STATE_INTEGRITY_LAWS.md` (S1–S5) BEFORE any balance/state change · `docs/SCHEDULE_RESOLUTION_MODEL.md` · `docs/AL_DEDUCTION_REDESIGN.md`
- **History:** grep `docs/HISTORY.md` sessions 31–42; open data ops in `docs/ACTIONS_LEDGER.md`.
- **⚠ Gotchas (see the law, don't trust this line):** deduct-at-approval + refund-on-cancel · F14 same-date claims serialized by a pg advisory lock · settle banks via an atomic claim (no double-bank) — all per `docs/STATE_INTEGRITY_LAWS.md`.

## Audit · watchdog · session-closer · resilience
- **Files:** `gm_bot/audit.py::run_audit` (+ validators) · `gm_bot/bot.py::_auto_audit_job` · `gm_bot/bot.py::_live_watchdog_job` · `gm_bot/bot.py::_session_closer_job` · `gm_bot/bot.py::_watchdog_delta` · `run_collection_watchdog.py`
- **Read-first:** `docs/RESILIENCE.md` (every down-safeguard + known gaps + fire drill)
- **⚠ Gotchas:** self-heal first (systemd `Restart=always`), alarm only on PERSISTENT failure · live watchdog vs test watchdog — exactly one runs · `/audit` is the cross-row backstop the watchdog can't replace · session-closer closes dangling sessions at the resolved shift end.

## REPORT finance (daily cash/sales reconciliation)  ·  LIVE (GM bot)
- **Files:** `gm_bot/finance.py` (parser + recompute) · `gm_bot/reconcile.py` (cash/POS cross-check) · `gm_bot/sales.py` (sales-anomaly framework)
- **History:** grep `docs/HISTORY.md` "REPORT Finance".
- **⚠ Gotcha:** business day = 06:00→06:00 · a small "Over" is BY DESIGN (4000៛=$1 FX margin) — never flag it; flag "Lost".

## GM monitoring — clarify · coverage · tagging · roll-call
- **Files:** `gm_bot/clarify.py` (clarification ladder) · `gm_bot/coverage.py` · `gm_bot/mentions.py` (staff @-tagging) · `gm_bot/rollcall.py` (uid binding) · `gm_bot/analyzer.py` (ops-message concern scanner → gm_concerns) · `gm_bot/frequency.py` (call-out pattern detection)
- **⚠ Gotcha:** tag staff via the canonical `_staff_mention` (call-name + ping); GM only ever engages STAFF, never ex-staff/strangers.

## Accountant (expense / receipts / payments)  ·  staging only, INERT (no live service)
- **Files:** `accountant/bot.py` · `accountant/capture.py` · `accountant/db.py` · `run_accountant.py` · `scripts/run_accountant_local.py`
- **Read-first:** `docs/REPORT_SYSTEM_DESIGN.md`
- **⚠ Gotchas:** P2 money matcher is HIGH-RISK, per-step owner approval, no live money · uses `shared/ai_client.py::extract_receipt` (Sonnet) · Expense group `-5417163768`, TEST supplier `-5406470751`.

## Stock (catalog / counts / reorder)  ·  staging only, INERT
- **Files:** `stock/catalog.py` · `stock/catalog_data.py` · `stock/db.py` · `stock/order_brain.py` · `stock/sync.py` · `gm_bot/stock_gateway.py` (GM seam) · `gm_bot/stock_entry.py` (paperless /stock entry) · `shared/stock_shared.py` (shared tables) · `run_stock.py`
- **Read-first:** `docs/STOCK_APPSHEET_SETUP.md`
- **⚠ Gotchas:** `gm_bot/stock.py` is a soon-to-be-removed duplicate of `stock/order_brain.py` (drift-guarded by `tests/test_stock_brain_no_drift.py`) · gateway hidden until `STOCK_APPSHEET_URL` set · builds on shared `acc_items`/`stock_movements`.

## B2B wholesale bot  ·  LIVE (customer-facing)
- **Files:** `b2b_bot/bot.py` · `b2b_bot/orders.py` · `b2b_bot/order_parsing.py` · `b2b_bot/order_handlers.py` · `b2b_bot/menu_handlers.py` · `b2b_bot/menu_keyboards.py` (cart state + keyboards) · `b2b_bot/menu.py` + `b2b_bot/cake_menu.py` (menu DATA — edit for items/prices) · `b2b_bot/pricing.py` · `b2b_bot/recurring.py` · `b2b_bot/billing.py` · `b2b_bot/summaries.py` · `b2b_bot/customers.py` · `b2b_bot/staff_commands.py` (/markpaid, /balance, …) · `b2b_bot/dispatch_reminder.py` · `b2b_bot/delivery.py` · `run_b2b_bot.py`
- **Read-first:** `docs/B2B.md`
- **⚠ Gotchas:** PP-clock dates via `shared/clock.py` · b2b service is intentionally stopped at times — check before assuming live.

## Retail bot  ·  LIVE (customer-facing)
- **Files:** `run_bot.py` (entry — original retail bot)
- **⚠ Gotcha:** oldest subsystem; grep before editing. (Map entry thin — enrich when next worked on.)

## Hiring intake + quiz + assessment bot
- **Files:** `hire_bot/bot.py` · `hire_bot/intake.py` · `hire_bot/sessions.py` · `hire_bot/questions.py` · `hire_bot/scorer.py` · `hire_bot/followups.py` · `hire_bot/assessment_runner.py` · `hire_bot/assessment_package.py` (Sonnet evidence builder) · `hire_bot/assessment_pipeline.py` · `hire_bot/assessment_notify.py` · `hire_bot/correction_flow.py` · `hire_bot/offer_flow.py` · `hire_bot/khmer_validator.py` · `hire_bot/readtime.py` · `run_hire_bot.py`
- **History:** grep `docs/HISTORY.md` sessions 18–22.
- **⚠ Gotcha:** AI-call budget rules (max 2 Haiku/applicant pre-test) — see CLAUDE.md Arch Rule 1.

## Listener / ops-intelligence (the read-only eyes)
- **Files:** `ops_intelligence/listener.py` · `ops_intelligence/importer.py` · `ops_intelligence/analyze_chats.py` · `ops_intelligence/price_list_fetcher.py` · `ops_intelligence/price_extractor.py` (read supplier price PDFs/photos) · `ops_intelligence/price_report.py` · `run_listener.py`
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
- **Files:** `CLAUDE.md` (the Standard + Arch Rules + Current Status) · `docs/BEDROCK.md` · `docs/STATE_INTEGRITY_LAWS.md` · `docs/STATEFUL_MENU_PATTERNS.md` · `docs/GOVERNANCE_INVENTORY.md` · `docs/SIMPLIFICATION_STRATEGY.md` · `docs/ACTIONS_LEDGER.md` (open data ops) · `docs/HISTORY.md` (the full archive — grep it)
- **⚠ Gotcha:** before claiming anything is missing/broken/a-gap, grep `docs/HISTORY.md` + the area's doc and cite it, or say "let me check" and check. An unverified gap-claim is a violation, same as a false "done."

---

## MAP-IGNORE — package files intentionally NOT a routing target
> Every `__init__.py` is auto-ignored. Beyond that, a file goes here ONLY after being read and judged
> genuinely trivial (a tiny facade/helper reached transitively) — never as a lazy "make the test pass".
> If unsure, index it in an area above. (Verified by reading each one, 2026-06-19.)
- `b2b_bot/menu_flow.py` — 10-line back-compat facade that just re-exports from `b2b_bot/menu_keyboards.py` + `b2b_bot/menu_handlers.py`.
