# MAP — task → where to look (Layer 1: the curated router)

> **Open this FIRST for any task.** Find your area → the *entry* files + the *Read-first* law/doc →
> `grep docs/HISTORY.md` for the area → heed the ⚠ gotcha. This is curated WISDOM, kept slim.
>
> **Need a file that isn't here, or "where's function X"? → `MAP_INDEX.md` (Layer 2).** That's the
> AUTO-generated complete inventory (every file → docstring + symbols); it can't omit a new file.
> So Layer 1 only lists *entry points* — completeness lives in Layer 2, by construction.
>
> **RULES (mechanical):** any file move/rename/new file → run `python scripts/gen_map_index.py` and
> commit `MAP_INDEX.md` (the build fails if it's stale — `tests/test_map_index_fresh.py`). Any Layer-1
> `path` or `file::symbol` here must resolve (`tests/test_map_integrity.py`). **Gotchas POINT to the
> law/test that owns the truth — never assert a fact the map can't verify.** Index only; never prose.
> Before claiming anything is missing/broken/a-gap: check the records this points to and cite them.

---

## Attendance — check-in / check-out / no-show  ·  ⚠ LIVE (real staff, payroll-adjacent)
- **Entry:** `gm_bot/bot.py` (scheduler + location handler + jobs) · `gm_bot/attendance_ui.py::resolve_day` (the ONE day-resolver) · `gm_bot/checkin.py::can_auto_checkout`
- **Read-first:** `docs/ATTENDANCE_SYSTEM_DETAILED.md` · `docs/STATEFUL_MENU_PATTERNS.md` · grep `docs/HISTORY.md` sessions 31–42
- **⚠ Gotchas:** overnight shifts bind to the SHIFT-START date, not the calendar day · go-live grace · everything `is_test`-scoped · LIVE since 2026-06-16 → read-only on prod first, prove on staging, deploy by TAG in a quiet window.

## AL · OT · payback · sick · swap · special-leave · points · pay  ·  ⚠ LIVE, MONEY/BALANCE
- **Entry:** `gm_bot/payback.py` · `gm_bot/ot.py` · `gm_bot/al.py` · `gm_bot/attendance_ui.py::resolve_day` · `shared/database.py` (al_*, payback_*, ot_*) — siblings (sick/swap/special/points/late/pay) in `MAP_INDEX.md`
- **Read-first (TRIPWIRE):** `docs/STATE_INTEGRITY_LAWS.md` (S1–S5) BEFORE any balance/state change · `docs/SCHEDULE_RESOLUTION_MODEL.md` · `docs/AL_DEDUCTION_REDESIGN.md` · `docs/ACTIONS_LEDGER.md` (open data ops)
- **⚠ Gotchas (read the law, don't trust this line):** deduct-at-approval + refund-on-cancel · F14 same-date claims under a pg advisory lock · settle banks via an atomic claim — all per `docs/STATE_INTEGRITY_LAWS.md`.

## Audit · watchdog · session-closer · resilience
- **Entry:** `gm_bot/audit.py::run_audit` · `gm_bot/bot.py::_live_watchdog_job` · `gm_bot/bot.py::_session_closer_job` · `run_collection_watchdog.py`
- **Read-first:** `docs/RESILIENCE.md` (every down-safeguard + known gaps + fire drill)
- **⚠ Gotchas:** self-heal first (systemd `Restart=always`), alarm only on PERSISTENT failure · `/audit` is the cross-row backstop the watchdog can't replace · closer shuts dangling sessions at the resolved shift end.

## REPORT finance (daily cash/sales reconciliation)  ·  LIVE (GM bot)
- **Entry:** `gm_bot/finance.py` (parse + recompute) · `gm_bot/reconcile.py` (cash/POS cross-check) · `gm_bot/sales.py`
- **⚠ Gotcha:** business day = 06:00→06:00 · a small "Over" is BY DESIGN (4000៛=$1 FX margin) — never flag it; flag "Lost".

## GM monitoring — concerns · clarify · tagging · roll-call
- **Entry:** `gm_bot/analyzer.py` (ops-message concern scanner) · `gm_bot/clarify.py` (clarification ladder) · `gm_bot/mentions.py` (staff @-tagging) · `gm_bot/rollcall.py`
- **⚠ Gotcha:** tag via the canonical `_staff_mention`; GM only ever engages STAFF, never ex-staff/strangers.

## Accountant (expense / receipts / payments)  ·  staging only, INERT (no live service)
- **Entry:** `accountant/bot.py` · `accountant/capture.py` · `accountant/db.py` · `shared/ai_client.py::extract_receipt` (Sonnet)
- **Read-first:** `docs/REPORT_SYSTEM_DESIGN.md`
- **⚠ Gotchas:** P2 money matcher is HIGH-RISK, per-step owner approval, no live money · Expense group `-5417163768`, TEST supplier `-5406470751`.

## Stock (catalog / counts / reorder)  ·  staging only, INERT
- **Entry:** `stock/order_brain.py` · `stock/sync.py` · `stock/catalog.py` · `gm_bot/stock_gateway.py` (GM seam) · `shared/stock_shared.py` (shared tables)
- **Read-first:** `docs/STOCK_APPSHEET_SETUP.md`
- **⚠ Gotchas:** `gm_bot/stock.py` is a soon-to-be-removed duplicate of `stock/order_brain.py` (drift-guarded by `tests/test_stock_brain_no_drift.py`) · gateway hidden until `STOCK_APPSHEET_URL` set.

## B2B wholesale bot  ·  LIVE (customer-facing)
- **Entry:** `b2b_bot/bot.py` · `b2b_bot/orders.py` · `b2b_bot/order_handlers.py` · `b2b_bot/order_parsing.py` — menu/cart/billing/commands in `MAP_INDEX.md`
- **Read-first:** `docs/B2B.md`
- **⚠ Gotchas:** PP-clock dates via `shared/clock.py` · b2b service is intentionally stopped at times — check before assuming live.

## Retail bot  ·  LIVE (customer-facing)
- **Entry:** `run_bot.py` (original retail bot)
- **⚠ Gotcha:** oldest subsystem; grep before editing. (Thin entry — enrich when next worked on.)

## Hiring intake + quiz + assessment bot
- **Entry:** `hire_bot/bot.py` · `hire_bot/intake.py` · `hire_bot/scorer.py` · `hire_bot/assessment_runner.py` — the rest in `MAP_INDEX.md`
- **Read-first:** grep `docs/HISTORY.md` sessions 18–22
- **⚠ Gotcha:** AI-call budget rules (max 2 Haiku/applicant pre-test) — see CLAUDE.md Arch Rule 1.

## Listener / ops-intelligence (the read-only eyes)
- **Entry:** `ops_intelligence/listener.py` · `ops_intelligence/importer.py` · `ops_intelligence/price_list_fetcher.py`
- **⚠ Gotchas:** Telethon session file is auth — NEVER run two clients on one session · session backed up to the secrets repo (not in `bootstrap.py --sync`).

## Shared infrastructure
- **Entry:** `shared/database.py` (ALL DB + the fail-closed `TWBSHOP_ENV` switch) · `shared/ai_client.py` (the ONLY anthropic SDK use) · `shared/error_handler.py` · `shared/runtime_guard.py` · `shared/clock.py`
- **Read-first:** CLAUDE.md Arch Rules 1–6
- **⚠ Gotchas:** every AI call goes through `shared/ai_client.py` · `TWBSHOP_ENV` unset RAISES (no silent prod) · balance writes flip status FIRST.

## Deploy / ops
- **Entry:** `scripts/verify_live.py` (HEAD==origin + active + marker) · `scripts/checkpoint.ps1` (the `push` engine) · `pull.ps1`
- **Read-first:** CLAUDE.md "Deploy Discipline" + "push/pull words"
- **⚠ Gotchas:** deploy-from-TAG (server runs a tag, not main tip) · restart only the changed service · verify independently after.

## Multi-lane (hub + lane worktrees)
- **Entry:** `parallel_lanes.json` (file→lane ownership) · `scripts/lane_guard.py` · `scripts/checkpoint.ps1` · `scripts/integration_audit.py`
- **Read-first:** `docs/MULTI_LANE_PLAYBOOK.md` · `docs/PARALLEL_LANES.md`
- **⚠ Gotcha:** lanes never edit `CLAUDE.md`/Current Status (hub owns it) → use `CLAUDE.local.md`.

## Governance / standards / what-was-decided
- **Entry:** `CLAUDE.md` (Standard + Arch Rules + Current Status) · `docs/BEDROCK.md` · `docs/STATE_INTEGRITY_LAWS.md` · `docs/STATEFUL_MENU_PATTERNS.md` · `docs/SIMPLIFICATION_STRATEGY.md` · `docs/ACTIONS_LEDGER.md` · `docs/HISTORY.md` (the full archive — grep it)
- **⚠ Gotcha:** before claiming anything is missing/broken/a-gap, grep `docs/HISTORY.md` + the area's doc and cite it, or say "let me check" and check. An unverified gap-claim is a violation, same as a false "done."
