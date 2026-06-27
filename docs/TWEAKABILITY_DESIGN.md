# Dashboard Tweakability — OPEN for the world, LEAN by default (the differentiator)

> Owner direction (2026-06-27): the cut-over settings are client tweaks. Don't think only TWB — think what
> ANY business worldwide would want to tweak in every threshold / ladder / rule, and make the dashboard OPEN
> enough that a client feels real control (even a "stupid" tweak) — **WITHOUT** a long messy abundance of
> knobs. **Simplicity + leanness is WHY we beat the rest.** This doc is the model that holds both at once.

## The core principle (how OPEN and LEAN coexist)
**Breadth lives in curated PRESETS + progressive disclosure + search — never in a flat wall of knobs.**
Everyone else (SAP, Salesforce, ServiceNow, even Deputy/Gusto) drowns the admin in settings trees. We invert it:
the *power* is all there, but the *default surface* is tiny. The client meets ~3 decisions, not 300 — yet
nothing is locked away.

## The 4 layers of control (depth is OPT-IN)
- **L0 — It just works.** Sensible defaults per industry/country template. The client never *has* to open a knob.
- **L1 — Vibe presets (1 tap, ~80% of real needs).** Per area/ladder, a few named presets that set a CLUSTER of
  knobs at once: lateness `Strict · Balanced · Relaxed`; approvals `Tight · Normal · Loose`; OT `Generous · Capped`.
  The client picks a *feeling*; we move the underlying values. Real control, ~1 decision. **This is the lean win.**
- **L2 — "Customize" (the granular knobs, hidden behind an expander).** Plain-language, intent-grouped: "≤ N min
  late is free," not `verdict.grace_min`. Power-users get every value. Hidden by default → never overwhelming.
- **L3 — "Ask / search to change."** A box: *"make lateness stricter"* → jumps to (or applies) the knob. With L3,
  breadth becomes FINDABLE instead of hunted — so we can have hundreds of knobs and the client never feels them.
  (We already have "Ask your business"; this is "Ask to change.")

## What businesses WORLDWIDE want to tweak (the universal surfaces — every "place/ladder")
- **Thresholds & grace** — lateness grace, OT cap, notice periods, deadlines, rounding. (Tolerance differs everywhere.)
- **Ladders & escalation** — who's told, after how long, how many steps, nudge→escalate→owner timing.
- **Approvals** — how many approvers, which roles, human-vs-bot, can-a-senior-self-approve.
- **Penalties & rewards** — points/penalty values, bonus sizes — the carrot/stick balance (very culture-dependent).
- **Schedule & labour rules** — overnight, split shifts, rest gaps, max weekly hours, consecutive-day caps.
  ⚠ **Labour LAW varies by country** — this is a huge global surface (EU working-time, US overtime, KH norms…).
- **Money** — currency, rounding, pay cycle, tax/VAT, allowances, OT multiplier.
- **Language & locale** — the UI *and* the staff-facing messages (KH/EN today → many languages).
- **Terminology** — what they CALL things: "AL" vs "PTO" vs "annual leave" vs "vacation" vs "holiday".

## How the breadth stays LEAN (the mechanisms)
1. **Country + Industry + Vibe PRESETS carry the breadth.** We curate "Cambodia / US / EU labour defaults",
   "bakery / café / retail", "strict / relaxed". The client picks in the onboarding questionnaire (already built) →
   the locale-correct defaults load. The *world's* variety lives in OUR preset library, not dumped on the client.
2. **Intent-grouping, plain language, in-context.** Knobs sit inside the card they belong to, phrased as outcomes.
3. **Allow-but-guard the "stupid" tweak.** The client CAN set grace=60min (control = they feel trusted); a gentle
   "heads up, that's unusual" nudge, but we never BLOCK it — and **validate-on-write + fail-safe-on-read** mean a
   silly value can never break live (the reliability discipline already in `docs/CUTOVER_COVERAGE.md`).
4. **Rename to their words.** A "terminology" layer lets a client relabel AL→PTO etc. — feels bespoke, costs nothing.

## Why this is the moat
Competitors equate "powerful" with "lots of visible settings" → overwhelming, needs a consultant. We make
powerful *feel* simple: 3 onboarding answers + a vibe per area = a fully-configured global business; the depth is
one "Customize" or one search away, never in your face. **Lean is not fewer features — it's fewer decisions per
outcome.** That's the edge.

## Next build (first concrete slice)
Make the already-migrated attendance knobs (grace · early-bonus · papers · short-notice · OT cap) the proof:
intent-group them ("Lateness & grace", "Overtime", "Leave & notice"), add a **vibe preset** per group (sets the
cluster), keep the granular values behind "Customize", and wire "ask to change". Then replicate the pattern per
domain + build the country/industry preset library.
