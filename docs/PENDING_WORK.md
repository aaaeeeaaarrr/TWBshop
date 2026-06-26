# Pending Work — master backlog (keep ALL; nothing lost)

> Owner (2026-06-26): "we have so many other pending works, can you please not lose any of them? Let's keep all
> to work on." This is the single consolidated home for everything OPEN. Detail lives in the linked docs;
> this is the index so nothing slips. Tick items here as they ship. (Also see `docs/ROADMAP.md`,
> `docs/ACTIONS_LEDGER.md`, `docs/POSBUSINESS_HARVEST_PLAN.md`, `docs/BONUSES_AND_FINDINGS.md`.)

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
- [ ] Automations — plain-words **trigger → condition → action** ("if a baker is sick, alert the senior"),
      riding our existing event hooks (the leaner "Procedures").
- [ ] An **"optimize" view** + an outcome metric — "X% of approvals / checks / reorders handled automatically."

## 🔎 Investigation ideas still open
- [ ] **Cash-drawer over/short report** — now buildable (the till tracks variance per shift).
- [ ] Voids / refunds log — unlocks after harvest 2b (needs the refund/void events).

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
