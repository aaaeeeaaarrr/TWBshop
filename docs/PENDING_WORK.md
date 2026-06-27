# Pending Work — master backlog (keep ALL; nothing lost)

> Owner (2026-06-26): "we have so many other pending works, can you please not lose any of them? Let's keep all
> to work on." This is the single consolidated home for everything OPEN. Detail lives in the linked docs;
> this is the index so nothing slips. Tick items here as they ship. (Also see `docs/ROADMAP.md`,
> `docs/ACTIONS_LEDGER.md`, `docs/POSBUSINESS_HARVEST_PLAN.md`, `docs/BONUSES_AND_FINDINGS.md`.)

## ▶▶ SESSION-55 WRAP — the LIVE pending map (one scan; nothing lost)
> A huge multi-thread session (audit → hardening → token incident → swap rule → questionnaire → automations →
> comms). This block is the single "what's left." Detail is in the sections below + the linked docs. (2026-06-26.)

### ✅ Shipped + LIVE this session (deployed + verified)
- **Audit hardening** — audit chain same-txn/seq/un-forkable · ledger over-bank+phantom · leave_ledger sign ·
  domain idempotency · STOCK-NEG · PAYROLL-IDEMP · web-adapter · map auto-discover · money-guard self-provision.
- **Live-fix deploys** (gm/hire) — own-sick double-book race · init-order + gm-boot-isolation · hire-token.
- **GM-token incident** — server token fixed, gm restored (→ `docs/ACTIONS_LEDGER.md`).
- **Swap rule** → overlap-based + config-driven (fixed Norin↔Chomreun). (gm.)
- **Onboarding questionnaire** (packaging per client-type) · **Automations recipes** · **cash-drawer/voids +
  verdict parity-lock + domain→audit-chain**. (wizard.)

### 🅿️ Built this session, PARKED — needs you to finish/deploy
- **Comms escalation** — the DETERMINISTIC brain (`gm_bot/comms.py`) + the data-capture fix (ops_messages now
  stores `reply_to_msg_id` + `mentioned_ids`; the listener captures them) are BUILT + tested. **Remaining (all
  parked):** (1) **listener deploy** so the structured data starts flowing · (2) the **gm job** (fetch recent
  monitored-group msgs → resolve reply_to → `comms.find_unanswered(staff tg ids)` → `comms.stage_for` + a
  `comms_actions` idempotent table → gated nudge DM / escalate-to-Supervisors) · (3) **gm deploy** · (4) your
  **test-mode walk + wording (Khmer) review** · (5) flip the gate `gm_state comms_escalation_live`.
  **Scope:** group MESSAGES = deterministic; 1-to-1 Telegram CALLS = invisible to the listener (not a party);
  cellular calls = need a phone app.

### 🔴 Owner-gated — decisions / credentials (can't do without you)
- B2B F2/F3/F4 fix-session (real ledger, at re-enable) · `secret_guard.py:33` bot-prefix regex (in .claude/hooks,
  guard-blocks me) · validate onboarding on a real BotFather bot · check-in cut-over (HELD in shadow) · company
  name · W3 hardening (`ORG_SECRET_KEY` + CSRF + rate-limit + HTTPS) · Harvest Phase 4 (PayWay creds) / 5 (ESC/POS
  hardware) / Anchor-OPS (`ANCHOR_DIR`+`ANCHOR_HMAC_KEY` in secrets) · refresh the server GitHub PAT (so `--sync` works).

### 🎨 Owner-shaped — give me a steer + I build (designed, ready)
- **Automations**: ✅ COMPLETE end-to-end — recipes · live dispatch · scheduled runner · custom builder (compose
  your own {trigger+who+message}). Nothing left but optional polish.
- **Comms**: the gm-job wiring above (decide window / ladder / groups / repeat-flag) + optionally pair with the
  **proactive attentiveness ping** (a deterministic responsiveness alternative; gate: auto-penalize vs alert+log).
- **Dashboard tuning**: card copy · ~20 cascade lines · value-weights · colour thresholds · which cards per plan
  (questionnaire built) · which preview-toggles to make functional · wire TWB's REAL live data in.
- **Reliability — instant-live coverage** (owner due-diligence, s55): the config MECHANISM is instant-live (fresh
  reads · atomic writes · `set_config` now `FOR UPDATE`-locked, race FIXED); the GAP is only 2 live-gm paths read
  config (swap · AL re-ping · verdict grace/early · papers_grace · short_notice — ALL DEPLOYED-LIVE s55,
  behavior-verified on prod) — ALL 5 easy wins (grace · early · papers · short · ot_cap) now LIVE. The remaining
  hardcoded settings (MED-risk + ones needing a new config key) await later passes. Migration plan →
  **`docs/CUTOVER_COVERAGE.md`** (5 easiest behavior-preserving wins first: grace_min · early_bonus · papers_grace
  · short_notice · ot_cap; + GRACE_MIN dup in checkin.py & late.py to consolidate). Each HIGH-RISK (payroll-
  adjacent) → staging-prove default==current + quiet-window deploy. Owner-paced.
- **Dashboard tweakability rollout (s56→s57, open-yet-lean) — ✅ ROLLOUT COMPLETE:** model → `docs/TWEAKABILITY_DESIGN.md`.
  DONE+LIVE: **vibe presets** (`core/presets.py` + `/presets`, 5 live areas, captions) + **per-setting RESPONSIBILITY
  microcopy** (`core/policy.py` — a light-grey "your call, per your policy / local law" line; on /presets + the
  editor; a `/policy` terms page). **Decisions: country presets DROPPED (re-confirmed by owner 2026-06-27 + grep-verified
  there are none — businesses own their own laws); terminology PARKED.**
  **s57 (this resume) — DONE, wizard-only, suite green:** ① microcopy EXTENDED to **all 4 other domains** (stock · pos ·
  hr_payroll · accountant) **+ attendance gaps completed** → `SETTING_POLICY` now ~58 entries (only `verdict.rounding`
  deliberately omitted — one fixed option); 54 grey lines render on `/customer/config`; regression guard
  `tests/test_policy.py::test_other_domains_every_setting_has_a_responsibility_line` enforces "cover them all".
  ② **ASK-TO-CHANGE BUILT** (`core/ask_change.py` — a stateless NL parser "make lateness stricter" → a vibe-preset
  proposal; safe-by-construction: only ever maps to an existing preset, ambiguous→None; the wizard `/ask` shows a
  confirm card whose Apply POSTs to the **audited `/presets/apply`** — no new write primitive; 9 tests, a GET mutates
  nothing). ⏳ Optional follow-ons (owner-gated): smarter group-disambiguation when no area is named; cover the
  onboarding/connections plumbing settings too if wanted.

### 📚 Older standing threads (unchanged)
- Accountant P2 money matcher + Bakong · Stock lane AppSheet + GM↔stock cutover · marketing automation · AI
  order-taker · WOC extraction · shadow informational-labeling (low value, cut-over HELD).

---

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
- [x] **Automations — COMPLETE (s55): recipes · live dispatch · scheduled runner · custom builder** — `core/automations.py` + `/automations`: 8
      one-tap plain-words recipes (condition → action) riding our existing detectors, config-driven, with a
      "would fire now" preview AND live dispatch — `dispatch()` SENDS each firing recipe to its configured target
      via the tenant's bot, debounced (`automation_dispatches`); SAFE-by-default (blank target = no send); a
      "Send pending alerts now" button + a SCHEDULED runner (`run_automations.py` + the `twbshop-automations`
      service: every 15 min auto-sends opted-in tenants' firing recipes — DOUBLY safe: opt-in OFF by default AND
      only to set targets) + the CUSTOM BUILDER (compose your own named {trigger+who+message}; both doors compile
      to one engine). ✅ Done end-to-end.
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
