# Shift Model — design rethink (overnight / cross-day root cause)

> **Owner prompt (2026-06-22):** stop patching overnight bugs one by one. Maybe tagging a shift by
> *calendar date* is the wrong de-facto identity — keep the date for DATA, but find a model that's
> **simpler, faultless, and portable to any business.** Options + pros/cons below, then a recommendation.
> Status: **DESIGN DRAFT for discussion — nothing built.**

## The root cause (one sentence)
The calendar **date** is overloaded: it's a human label AND the shift's identity AND the basis for time
logic ("is it now / has it passed / what day / what to display"). An **overnight shift dated D actually
runs D 21:00 → D+1 06:00**, so any code that reasons about the shift from the bare date is wrong after
midnight. Every night-shift bug this month is the same cause:
- the −15 didn't fire (resolve_day called the running sick day "not working"),
- "6am under 20/06" (really next morning),
- the 2am "never settled" false alarm (date < today trips at midnight while the shift is still worked).

## The principle that fixes the whole class
**A shift is a span of time: a start instant and an end instant. Reason ONLY on those. The calendar date
is a label for humans/reports — never the basis for is-now / has-passed / display.** This is how robust
calendar systems work (an iCal event = start/end instants + a display timezone). Intervals don't care
about midnight, so the entire cross-day bug class disappears. It is also **universal** — works for any
business and any pattern (day, night, split, on-call, rotating, 24h ops), which is the portability test.

## Options

### Option 1 — Band-aid: keep date-as-ID + an overnight-aware helper, route checks through it
*(what was proposed before the owner pushed back)*
- **Pros:** tiny; no migration; ship today.
- **Cons:** "fixes on top of fixes." The date is STILL the identity and STILL compared; it's faultless
  only if every caller remembers the helper — a new check or a new dev reintroduces the bug. Faultless
  by *discipline*, not by *construction*. Does not generalize cleanly. → **rejected by owner, rightly.**

### Option 2 — Business-day cutoff (e.g. the operating day runs 03:00→03:00)
- **Pros:** one rule; keeps date-keying; common in 24h retail/F&B for sales reporting.
- **Cons:** still calendar-date logic, just shifted; **business-specific** (assumes a clean daily cutoff —
  fails the portability test); doesn't answer "is now inside the shift" or odd patterns (a shift longer
  than the cutoff window, two shifts in a day). A half-measure — relabels the boundary, keeps the coupling.

### Option 3 — Interval model, COMPUTED (recommended first step)
One canonical function returns each shift's real **(start_dt, end_dt)** (overnight-aware, honoring
overrides — the system already half-does this in `resolve_day` / `_shift_date_now`). ALL logic uses those
instants; the date stays as a **display/grouping label only**; a **guard test bans raw calendar-date
comparisons** (`when_date < today`, etc.) in the attendance/audit/settle modules → faultless *by
construction*, not by memory.
- **Pros:** faultless for overnight (intervals ignore midnight); **universal/portable**; **NO schema
  migration** (windows are computed from the existing schedule + overrides); enforceable (the guard
  prevents regressions); the simplest path to the clean model; a clean **stepping-stone** to Option 4.
- **Cons:** a real (one-time) refactor of the time-logic call-sites; the shift is still *derived*, not a
  stored row, so events still reference the date (no FK-to-shift integrity); a PAST shift's window is
  **recomputed from the current schedule**, so it isn't frozen-in-time (fine for is-now/has-passed; see
  the honest caveat below for payroll history).

### Option 4 — Shift as a first-class ENTITY (stored interval + foreign keys)
A `shifts` table: `shift_id` (PK), `staff_id`, `start_dt`, `end_dt`, `business_day` (label), `status`.
Attendance / payback / OT / points reference `shift_id`. The date becomes a plain label column.
- **Pros:** the fully correct, mature model (how Deputy / When-I-Work / Homebase model it); faultless +
  universal + **relationally clean** (every event hangs off the shift, FK integrity); the window is
  **frozen** (a later schedule change can't rewrite history → correct payroll history); unlocks future
  features (splits, multi-shift days, swaps, integrations) and is the most portable end-state.
- **Cons:** the **biggest** change — schema + data migration of the **LIVE HIGH-RISK attendance core**;
  real migration risk; more upfront work; arguably more than the shop needs today (YAGNI) until patterns
  get complex.

## Honest caveat (Option 3 vs 4 — the one real difference)
Both make is-now / has-passed / display **faultless**. The ONLY thing Option 4 adds is **historical
freeze + FK integrity**: a stored shift remembers exactly what its window WAS, even if the staff's hours
change later; a computed window (Option 3) recomputes from current hours. For *this* shop's actual bugs
(all operational: is-it-now, has-it-passed, display) Option 3 fully suffices. Option 4 matters only if
payroll history must stay exact across schedule changes, or patterns get complex.

## Recommendation
1. **Adopt the principle** (date = label; reason on intervals) as a standing rule.
2. **Do Option 3 now:** one `shift_window(staff, anchor) -> (start_dt, end_dt, label)` source of truth +
   route every is-now / has-passed / display through it + a guard test banning raw date-comparison in
   these modules. Simplest thing that is *truly* faultless + portable, with **no risky migration**.
3. **Keep Option 4 as the documented north star.** Option 3 is a clean stepping-stone — once everything
   already reasons on intervals, adding the stored `shifts` entity later is mechanical, not a rewrite.

## Then "no.3" (the per-event verifier) — re-framed
Build the **model first, verifier second.** A per-event "verify every generated thing at write-time"
layer on top of the *current* date-confused model would inherit the confusion (it'd need its own
overnight special-cases). On the interval model it's clean: at each write, re-read + assert against the
shift's real window. So the order is **(model) → then the per-event verifier rides on it.** Doing the
verifier first = more fixes-on-fixes.

---

# OWNER UPDATE (2026-06-22): this is a PRODUCT — reframe + safe migration + a missed option

The owner's real goal: a **portable, scalable attendance SERVICE sellable to other businesses**, possibly
**multi-tenant** and **POS / external-system integrated**. That changes the calculus. Three honest
admissions: (a) **greenfield, Option 4 is the obvious choice** — the only reason to hesitate is the risk of
changing a *live* system that mostly works; (b) my first pass **did not explicitly stress-test the model
against every change type** (swap / reschedule / extend / cross-midnight / partial / full-day); (c) I
**missed an option** that's the gold standard for a sellable, integrated product: **event-sourcing**.

## Stress test — does the interval/entity model handle EVERY change? (yes — and they argue FOR it)
Each "change" is just an operation that **creates or edits a shift instance's (start_dt, end_dt)** — the
date never enters the logic:
- **Day-off swap (A takes B's day):** two instances get reassigned/created with their real windows. ✓
- **Senior moves a shift to another day (back & forth):** the instance's start/end move; identity is the
  shift_id, not the date, so "moving it" can't confuse anything. ✓ (this is exactly where date-keying
  tangles today)
- **Same-day time change / cross-midnight change:** different start/end instants. Native. ✓
- **A few hours / full day / extended times / OT / payback slot:** all just intervals of some length glued
  to an instance. Native. ✓
- **Split shift / two shifts in a day / on-call / 24h ops / rotating (other businesses):** multiple
  instances per person per day — the date-as-ID model *can't even represent* this; intervals/entities do
  it for free. ✓
**Conclusion:** the change-types don't just "work" under intervals — they're the reason the date-as-ID
model keeps breaking. They strengthen the case for a stored entity.

## The missed option

### Option 5 — Event-sourced timeline (gold standard for a sellable, integrated product)
Model the world as an **append-only log of events** (`shift_scheduled`, `shift_moved`, `shift_extended`,
`checked_in`, `checked_out`, `swap_approved`, `payback_credited`, …). Current state (a shift, a balance) is
a **projection** built by replaying events. The `shifts`/`balances` tables become read-models.
- **Pros:** the most faultless + **fully auditable by construction** (you can reconstruct the exact state
  at ANY past instant — perfect for payroll disputes); **integration-native** (a POS / payroll / BI system
  subscribes to the event stream — this is how products expose data); a true **immutable history** (no
  "wrong-at-birth" / no retro-rewrite); pairs perfectly with the per-event verifier (the events ARE the
  verification trail).
- **Cons:** the biggest **paradigm** shift (everyone must think in events + projections); more upfront
  scaffolding; easy to over-engineer for a single shop. Best adopted as **"entity model + an event log for
  the things that matter"** (a pragmatic hybrid) rather than pure event-sourcing everywhere.

## Product pillars (must be designed in from day one if it's to be sellable)
- **Multi-tenancy:** an `org_id` on every row + strict per-tenant scoping (one bug here = a cross-customer
  data leak — the highest-stakes thing in a SaaS). Decide row-level (shared DB) vs schema/DB-per-tenant.
- **Stable IDs + an API/event surface:** integrations (POS, payroll) need durable `shift_id` / `staff_id`
  and a way to read/subscribe — only the stored-entity (Option 4) or event model (5) provides this.
- **Config-per-business:** shift patterns, day boundaries, leave rules, points rules, currencies, timezone
  per tenant — none hard-coded (today many rules are TWB-specific constants).
- **Timezone-correct everywhere:** store UTC instants, render in the tenant's TZ (we already lean on PP_TZ;
  a product needs per-tenant TZ).

## How to change a LIVE system with near-zero risk (the owner's instinct — correct)
Three layers, strongest first:
1. **Shadow / parallel run (the de-risker):** build the new model and run it **alongside** the live one,
   computing its answers for the SAME real events **without acting on them**, and **continuously compare**
   old vs new. Agreement → confidence; every disagreement is a bug caught **before** it touches a human.
   After N weeks of clean agreement, promote the new model to authoritative. (This is how banks migrate
   ledgers — zero customer-visible risk during the proving period.)
2. **Feature-flag flip + instant revert:** one switch routes reads/writes to old or new; flip back on any
   problem (we already use `attendance_live` / `att_test` this way).
3. **The per-event verifier** rides on top once the new model is authoritative.
This lets us build the *right* (high-risk) model but **prove it in production with no exposure** before it
ever drives a real decision.

## Wording / generated-messages — yes, couple a clarity pass
A model change is the right moment to sweep **every generated human message** (FYIs, prompts, reminders,
the digest, the audit/watchdog lines) for clarity + correctness:
- The model makes displays **consistently** correct (always the real start/end + day) — the "6am under
  20/06" and "OT vs payback" confusions were symptoms of the same date-overload.
- Name things truthfully (a payback slot is not OT); show the real day for overnight; per-tenant language
  later (the bot is already bilingual EN/KH — a product needs per-tenant locale).
This is a **coupled workstream**, not an afterthought.

## REVISED recommendation (given the product goal)
- **Target = Option 4 (stored shift entity) + a lean event log for the money/schedule events (a 4+5
  hybrid)**, designed **multi-tenant + integration-ready from day one.** For a sellable, POS-connected
  service this is the foundation; Option 3 (computed) is NOT (no stable IDs, no tenancy, no frozen history).
- **De-risk with the shadow/parallel run + flag + instant revert** — this is what makes a live rewrite safe.
- **Option 3's discipline is still the on-ramp:** force all current code to reason on intervals first
  (cheap, no migration) so the shadow build has a clean target; but the END is 4+5, not 3.
- **Honest reversal:** my first "Option 3 now" was right for "just fix the shop." For "build a sellable
  service," the answer is **the proper model, proven via shadow-run.** The requirement changed, so the
  recommendation changed.
- **Scope reality:** this is a multi-week build, not a session. Sequence it: (1) lock the principle + the
  guard; (2) design the entity+event schema + tenancy; (3) shadow-run vs live; (4) flip with revert;
  (5) wording pass; (6) per-event verifier; (7) API/POS surface.
