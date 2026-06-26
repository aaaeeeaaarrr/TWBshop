# Pending Work — master backlog (keep ALL; nothing lost)

> Owner (2026-06-26): "we have so many other pending works, can you please not lose any of them? Let's keep all
> to work on." This is the single consolidated home for everything OPEN. Detail lives in the linked docs;
> this is the index so nothing slips. Tick items here as they ship. (Also see `docs/ROADMAP.md`,
> `docs/ACTIONS_LEDGER.md`, `docs/POSBUSINESS_HARVEST_PLAN.md`, `docs/BONUSES_AND_FINDINGS.md`.)

## 🔬 Due-diligence audit (session 55, ultracode 44-agent) — confirmed findings to action
> Full report: workflow `wf_7bb0f25d-3e6` + the session-55 block in `docs/BONUSES_AND_FINDINGS.md`.
> Live core = sound; suite really green (1081p/2s). Priority order below.

**🔴 Owner-gated (need YOU):**
- [x] ✅ **GM bot token ROTATED** (owner, s55) — working-tree literal scrubbed + secret_guard regex flagged.
- [ ] **ROTATE the GM bot token via BotFather** *(done — kept for history)* → update secrets.py → redeploy twbshop-gm. The live token was
      in git history (`tests/test_log_redact.py` == `secrets.py`); working-tree literal already scrubbed, but
      ONLY rotation closes the breach. **#1 priority.**
- [ ] Quiet-window deploys (each prepared + proven on staging by me; the deploy is yours): own-sick race fix
      (gm) · hire-token fix (hire) · init_core_db ordering + run_gm_bot try/except (gm boot).
- [ ] B2B F2/F3/F4 fix session (with you, on the real ledger, at re-enable) — fix B2B_LANDMINE_FIX_PLAN's stale
      `message_id`→`group_message_id` note first.
- [ ] secret_guard.py:33 regex misses the bot-prefixed token form — the fix needs a `.claude/hooks/` edit
      (guard-blocks me); you apply it (drop `\b` / add `(?:bot)?` + a regression case).

**🟢 Autonomous / inert (I do on staging, never deployed):**
- [x] Scrub the live-token literal from tests/test_log_redact.py (synthetic same-shape token). *(s55)*
- [x] init_core_db: ALTER core_sales moved after its CREATE + run_gm_bot init wrapped try/except. *(s55, deploy gated)*
- [x] **2a hardening (s55):** audit.write same-txn (caller cursor) ✓ · core_audit BIGSERIAL seq + UNIQUE(org_id,
      previous_hash) + branch detection ✓ · ledger.py advisory-lock + FOR UPDATE + LEAST(cap) + log applied-delta ✓ ·
      leave_ledger no-row sign fix + cancel symmetry ✓ *(CHECK>=0 deliberately declined, see findings)*.
- [x] **2b refunds/voids (s55):** `pos.void_sale` one-txn (mark voided + re-increment stock + 'refund' drawer
      event + same-txn audit; single-void; revenue excludes voided). *(abnormal cash_event detector → forensics.)*
- [x] **Phase 3 / S2-S4 close (s55):** client_key idempotency + partial UNIQUE + ON CONFLICT on record_sale/
      receive_purchase/add_expense/record_count · GREATEST(0,…) + CHECK(on_hand>=0) · UNIQUE(org,period) +
      UNIQUE(run,staff) + claim-first run_payroll.
- [x] **Forensics + voids/refunds + cash-drawer + domain-audit (s55):** actor on cash_event/close_shift/void ·
      `investigate.voids_refunds_log` + `cash_drawer_report` both surfaced on /investigate · stock/pos/expenses/
      payroll mutations now write to the tamper-evident audit chain (verify_chain stays PASS).
- [x] **adapters/web.py hardening (s55):** reject client-supplied org_id (403) · serve() defaults 127.0.0.1 · 1MB
      body cap · import-guard test (no run_*.py may wire it without W3 auth).
- [x] **Shadow honesty — parity-lock test (s55):** core.attendance.verdict == gm_bot.checkin.verdict locked
      across the full minute grid (`tests/test_verdict_parity.py`) so the platform verdict can't silently drift.
      ⏸ Still deferred (low value, cut-over HELD): labeling informational settle rows (gm-deploy-gated) + modeling
      the payback-slot ext-worked path (= harvest #5).
- [x] **Test hardening (s55):** the 3 money guards self-provision a dedicated ex_staff test staffer — can't silently skip.
- [x] **Map/docs (s55):** auto-discover PKG_DIRS + _PACKAGES from the filesystem (one source of truth) → MAP_INDEX
      now 190 entries incl. core/wizard/adapters/telegram_bot; MAP.md gained adapters/ + telegram_bot/ pointers.

## 🔨 In flight / next up
- [ ] **"Ask your business" assistant** — computer-tier NL router over our real reports/insights (no API cost) +
      ai-tier escalation behind the AI-power toggle. *(Building now — Fin-inspired, lean.)* → ledger.
- [ ] **Phone-answer random attentiveness check** (GM bot) — DESIGNED, not built. Random-time ping the on-duty
      staff → tap to confirm → escalate → alert+log a miss; behind test-mode first. **Owner gate:** should a
      repeated miss ever AUTO-penalize (points), or always just alert+log? (default = alert+log).

## 🎴 Dashboard / wizard — parked for owner review (sensible defaults are live)
- [ ] Wire TWB's REAL live data into the dashboard (after setup is complete enough) → real shop, not migration.
- [ ] Shave card copy + the ~20 cascade lines (all my drafts).
- [ ] Tune the dials — value-weights (ranking) · colour thresholds · which frontier cards to flip on.
- [ ] Packaging per client-type (which cards per plan/segment).
- [ ] Decide which planned/idea preview-toggles to make FUNCTIONAL next.

## 🧰 POSBusiness harvest — remaining phases (→ `docs/POSBUSINESS_HARVEST_PLAN.md`)
- [x] Phase 1+1b — tamper-evident audit hash-chain + external anchor (SHIPPED, tag `54q`).
- [x] Phase 2a — POS till / cash-drawer money model (SHIPPED, tag `54r`).
- [ ] **Phase 2b** — refunds / voids (full cash refund per order + single-refund DB constraint; void unpaid;
      fold the cash refund into the till's expected_cash + the audit chain). HIGH-RISK money, own session.
- [ ] **Phase 3** — offline-first idempotency (idempotency key + safe retry, no double-charge).
- [ ] **Phase 4** — PayWay / KHQR payments. **Owner gate:** real sandbox/prod credentials (secrets only).
- [ ] **Phase 5** — ESC/POS printing (hardware-bound).
- [ ] **2a hardening** — float→**Decimal** when 2b adds tax/discounts · **atomic-audit** (write the audit in the
      SAME txn as the money op).
- [ ] **Anchor OPS activation** — set `ANCHOR_DIR` off the DB host + `ANCHOR_HMAC_KEY` (secrets) + schedule
      `scripts/anchor_audit.py` nightly + copy the anchor file offsite.

## 🤖 Fin-inspired borrows (→ ledger; do leaner than Fin)
- [ ] "Ask your business" (in flight, above).
- [~] **Automations — recipes tier BUILT (s55)** — `core/automations.py` + `/automations`: 8 one-tap plain-words
      recipes (condition → action) riding our existing detectors (insights.attention_feed + investigate),
      config-driven (`automations.recipes`), with a "would fire now" preview. ⏳ Next: the custom builder (the
      advanced door) + live SEND wiring (adapter/gm — it currently PREVIEWS what would fire, doesn't yet dispatch).
- [ ] An **"optimize" view** + an outcome metric — "X% of approvals / checks / reorders handled automatically."

## 🔎 Investigation ideas still open
- [x] **Cash-drawer over/short report (s55)** — `investigate.cash_drawer_report` + a section on /investigate.
- [x] **Voids / refunds log (s55)** — `investigate.voids_refunds_log` (built on 2b void/refund + actor tracking).

## 🔐 Owner-gated decisions / activations (need YOU)
- [ ] Validate the Telegram onboarding on a real BotFather bot (token → `run_onboard_demo.py`).
- [ ] Check-in cut-over — READY, but HELD in shadow by your call.
- [ ] B2B re-enable — only after the F2/F3/F4 money fixes (`docs/B2B_LANDMINE_FIX_PLAN.md`); B2B stays disabled.
- [ ] Company name decision (`docs/COMPANY_NAME_IDEAS.md`).
- [ ] Public-exposure hardening (W3): `ORG_SECRET_KEY` + CSRF + login rate-limit + HTTPS before anything is public.

## 📚 Standing open loops (older threads — detail in ROADMAP / HISTORY)
- [ ] Accountant bot — P2 HIGH-RISK money matcher + the staging walk + Bakong.
- [ ] Stock lane — create the AppSheet app → the GM↔stock cutover (remove `gm_bot/stock.py`).
- [ ] Marketing automation (Telegram channel → FB/IG → TikTok) — parked (`docs/ROADMAP.md` §F).
- [ ] AI order-taker (AI-assist behind a human, no auto-userbot) — parked.
- [ ] WOC customer-number extraction (123k-photo archive; ~$250 Haiku) — parked, ⚠ privacy/legal flag on outreach.
