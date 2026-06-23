# Shadow ↔ Live coverage — how much of the study is done

> Owner asked (2026-06-22): how much has the shadow study covered vs live, and what areas are still
> uncovered. Honest read below — updated as coverage grows. The cut-over (shadow→live) only happens after
> DAYS of real-data agreement on the covered areas AND closing enough of the gaps. **We are NOT at 90%.**

## Three states
- **PROVEN** — mirrored AND empirically agreeing with live on REAL data (the strongest).
- **PARITY** — the platform's logic is cross-checked equal to live's code (drift-guarded), but not yet
  confirmed on real data (sparse/no live data, or not wired to the live stream). Strong, not empirical.
- **GAP** — not yet ported/built in the platform.

## Coverage map
| Area | State | Evidence / why |
|---|---|---|
| Check-in verdict (late/early/grace/minute-of-day) | ✅ PROVEN | replay 98–100% over 135 real check-ins |
| Redefine-aware check-in (payback/OT moved start) | ✅ PROVEN | redefine days 16/16 on real data |
| Check-in points (early +10 · late split −1/−2) | 🟡 PARITY | `core.points` vs `gm_bot.points` full grid; rides the proven verdict |
| Checkout worked-min (edge-clamped) | 🟡 PARITY | `core.settle.worked_minutes`; no stored live "worked" to compare empirically |
| OT earned / bank / cap | 🟡 PARITY | `core.settle` vs `gm_bot.ot`; **no live data — `ot_bank` empty**, so empirically unprovable until OT actually happens |
| Payback split (OT clears debt first) | 🟡 PARITY | `core.settle`; sparse live credits |
| AL deduction (charged days · frozen S1 map · count) | 🟡 PARITY | `core.leave` vs `gm_bot.al` + S1 invariants |
| Short-notice points · fractional AL | 🟡 PARITY | `core.leave` parity |
| Schedule resolver (precedence) | 🟡 PARITY | `core.schedule.resolve_day` brain, parity vs live's precedence (full space) |
| Resolver SELF-DERIVE (core decides from its own state) | 🟢 BUILT | `core/derive.py` — resolves a day from `core_day_overrides` (no live feed → cut-over-ready); staging-proven incl. precedence. Remaining wiring: the live→core SYNC to populate the overrides during the shadow phase |
| OT/payback settle ORCHESTRATION (atomic claim · cap · refund · over-book guard) | 🟢 BUILT | `core/ledger.py` — settle-once claim + structural CHECK constraints (over-credit/over-bank impossible) + reversible (S1); proven on staging (no double-bank · cap · buyback refusal · clean reverse). Remaining: wire into the shadow at checkout + which-debt/redefine-window selection |
| AL deduct/refund ORCHESTRATION (atomic deduct-at-approval + symmetric refund) | 🟢 BUILT | `core/leave_ledger.py` — frozen-map deduct ↔ refund (S1), atomic claim each way; proven on staging (deduct-once · refund-once · exact reversal · refund reads the frozen total even after a schedule change) |
| Sick / no-show PENALTY computation | 🟡 PARITY | `core/points.py` — full catalogue (incl. `no_show` −2/min, `late_sick_inform` −15) drift-guarded == live + `points_for` derivation (Σ value×qty) + no_show/late_sick event constructors |
| Sick / no-show / special FLOW (reason · family · sweep · papers) | 🔴 GAP | per-CHANNEL adapter work (Telegram menus/jobs), not core math — belongs in the adapter layer, not the brain |
| Special leave | 🔴 GAP | live-only |
| Schedule changes (swap · redefine create · day-off move) | 🔴 GAP | architectural (`shift_moved` events) — #7 |
| Channel-agnostic spine | 🟢 BUILT | `core/channel.py` — neutral (command, params) dispatch; test proves two channel shapes → one brain + GUARDS that no core/* imports a channel SDK (principle #1 enforced) |
| Multi-tenant config (per-tenant knobs) | 🟢 BUILT | `core/tenant_config.py` — grace/thresholds/cap/channels/package on `orgs.config`, defaults = TWB; wired into the spine so the same code serves every tenant. (The onboarding wizard writes this.) |
| Channels: Telegram | ✅ PROVEN | the shadow hook runs on the live Telegram flow |
| Channels: web | 🟢 BUILT | `adapters/web.py` — HTTP request → neutral command → JSON, proven (same brain as Telegram/replay) + a thin stdlib `serve()`. A deployable second channel. |
| Channels: app / others | 🔵 TRIVIAL | any new channel = one small adapter to the spine (the hard part — the brain — is done) |
| Onboarding wizard (self-serve setup) | 🟢 ENGINE BUILT | `core/onboarding.py` — channel-agnostic step engine (steps=data, skip→default) + `apply()` → creates org + writes tenant config; starter steps included (owner refines the questions + package names/prices — a product decision) |

## Honest percentage
- **Dominant daily flow (check-in): ~proven.** Check-in is the single most frequent attendance event, and
  it agrees 98–100% on real data including redefines. The thing that happens most, every shift, is solid.
- **The everyday COMPUTATION math: ~mirrored.** Verdict (proven) + points + settle + leave math
  (parity-locked). The numbers the system computes are ~covered.
- **By behavior-area BREADTH: roughly 50%.** ~8 of ~16 areas are PROVEN or PARITY; the other half are GAPs —
  the **money-moving ORCHESTRATION** (the highest-stakes one), **sick / no-show / special-leave / swap**
  flows, the **self-derived resolver**, and **non-Telegram channels**.

**So: not 90%.** Call it ~**proven on the main flow, ~half the breadth.** The covered half is the
high-frequency path; the uncovered half is the money-moving mechanism + the rarer flows + other channels.

**UPDATE (after this build run):** the BUILT/PARITY breadth is now much higher — the whole brain
(verdict·points·settle·leave·resolver), BOTH money mechanisms (OT/payback + AL, atomic, staging-proven),
the channel spine, and multi-tenant config are all in. By behavior breadth that's ~**70%+ built**. But
the binding metric for cut-over is EMPIRICAL real-data agreement, and that is still **only PROVEN for
check-in** — the money paths are PARITY + atomic-proven on staging, not yet confirmed on live data
(which is sparse for OT/payback, so it accrues slowly — the "days of study"). The remaining GAPs are now
mostly: real-data confirmation (time) · the self-derive event-sync · sick/no-show/special FLOW · a
runnable web server + the onboarding wizard.

## What raises it next (in build order)
1. **#7 self-derive the resolver** (`shift_moved` events) → moves the resolver 🟠→ and unlocks schedule-changes.
2. **Settle/leave orchestration in core** (atomic-claim-at-write) → moves the money mechanism 🔴→🟡.
3. **Sick / no-show / special-leave** ports → close those GAPs (parity where data is sparse).
4. **Web adapter** → proves channel-agnosticism (the platform's whole premise).
Each raises this map; the cut-over waits on DAYS of real-data agreement across the PROVEN/PARITY set.

---

## ▶ Platform build state (refreshed 2026-06-23, session 53)
The table above is the ATTENDANCE shadow-study (the cut-over gate). Separately, session 53 built out the
sellable PLATFORM around that brain. State key: 🟢 BUILT (works, tested) · ✅ PROVEN (real or e2e flow) ·
🟡 BUILT-but-UNVALIDATED (mock-tested, no real run) · ⏸ GATED (needs an owner decision/action).

| Piece | State | Note |
|---|---|---|
| Config-driven engine (`core/tenant_config`) | 🟢 BUILT | the system IS its config; DEFAULTS = TWB; deep-merge; every `core` path reads it |
| Wizard — admin + customer editor (4-state badges, Apply/Cancel draft) | 🟢 BUILT | `wizard/app.py`; **127.0.0.1:8090 via SSH tunnel only**; Apply whitelists safe (non-LIVE) knobs |
| 5 domains configurable (attendance · accountant · stock · POS · HR) | 🟢 BUILT | attendance live-mirrored; the other 4 = INERT modelled config; 5 niche domains stay upsell |
| Onboarding — Telegram (guided bot · groups · discover-confirm · staff/expertise editors · templates · consent · bulk) | 🟡 UNVALIDATED e2e | mock-tested only — **NO real bot has run it** (the #1 thing to validate) |
| Channels — Telegram + Web | 🟢 BUILT | web check-in/out via a per-staff token link → `core` (not TWB live); + staff "recent check-ins"; same brain as Telegram/replay |
| Security — encrypted secret store · auth/logins | 🟢 BUILT (off by default) | Fernet when `ORG_SECRET_KEY` set; `WIZARD_AUTH=1` → login. Before public: set the key + CSRF + HTTPS + rate-limit |
| What-if preview · config audit log · export/import | 🟢 BUILT | read-only/safe; preview a change's effect · who-changed-what-when · clone a tenant's setup |
| Platform e2e flow | ✅ PROVEN (own flow) | one test: org→staff→config(audited)→web check-in→history→what-if→export connects |
| Live-bot menu bool-reset audit | ✅ CLEAR | read-only sweep — the bug class is ABSENT in retail/b2b/hire |
| Cut-over (shadow→live, per vertical) | ⏸ GATED | check-in is READY; owner keeps it in shadow for more real-data days |
| Real-bot validation · public hosting+W3 · name · B2B re-enable · `ORG_SECRET_KEY` | ⏸ GATED | owner decisions/actions (parked) |

**Honest platform read:** the platform is **broadly BUILT and self-consistent** (config engine · wizard ·
onboarding · 2 channels · 5 domains · security · audit · what-if · export-import), with TWB's live shop
**untouched** throughout (every deploy hit only `twbshop-wizard`). The gating constraints are no longer
*building* — they're **empirical validation** (a real bot has never run the Telegram onboarding; the
attendance money-paths await real-data days) and **owner decisions** (cut-over, hosting, name). Capture of
every win/gotcha → `docs/BONUSES_AND_FINDINGS.md`.
