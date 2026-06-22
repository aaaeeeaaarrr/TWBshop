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
| Channels: web / app adapter | 🟡 SPINE READY | the spine + a web-shaped adapter are demonstrated in test; a runnable web server is the remaining productization |

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
