# Unified schedule-event resolution + reverse-on-supersede + notify-all (design)

> **Status: DESIGN (owner-driven, 2026-06-13). Not built.** Behind `attendance_live=OFF`. Governed by
> `docs/STATE_INTEGRITY_LAWS.md` (esp. S1 reversible, S3 atomic, S5 multi-writer). Companion to
> `docs/AL_DEDUCTION_REDESIGN.md` (the AL piece, already built). This generalises that into one model
> for the whole "what is this person doing on day D" surface.

## Why (the problems this fixes)
Today, two plans for one day = a **blocked conflict** (F14), sometimes needing an override. That's rigid
against the **messy human element**: someone is booked for a change, then they (or their child) get sick;
a swap is agreed, then the person can't make it. The owner's model: **don't block — let the newest
decision win, quietly stand the old one down, reverse whatever balance it moved, and TELL everyone
involved, so a supervisor can layer another change to re-cover.** No dead-ends, no override, no spiderweb.

It also fixes things already in the backlog: AL-on-a-redefined-day (no override needed), and it replaces
the never-built "senior cancel an approved redefine" with a general supersede.

## The core model (five rules)
1. **Append-only events, resolve-on-read.** Every schedule decision (AL · sick · senior redefine ·
   day-off swap · payback/OT-rest slot · normal schedule) is a row with a **status** (proposed ·
   approved · **superseded** · cancelled · done). Nothing is deleted. The **active** plan for a day is
   *computed* = the one live (non-superseded, non-cancelled) decision that wins by the precedence below.
2. **ONE resolver, used by EVERY reader.** Attendance prompts, the lateness verdict, the no-show sweep,
   settle, and `/audit` all call the SAME `resolve_day(staff, date)`. Never two code paths deciding
   "is she working?" differently (today `compute_day_events`, `_settle_redefined_shift`, the no-show
   sweep, and `_sc_running` each resolve a bit differently — that drift is the seed of spiderwebs).
3. **New supersedes old → reverse the old one's balance, atomically.** When a newer decision wins a day
   the older one held, the old row → `superseded` AND its balance effect is reversed in the SAME
   transaction (S1): AL → refund the frozen day + reverse its points; redefine → nothing if unsettled
   (OT only banks at checkout, and a superseded redefine never settles); swap → reverse its dated
   overrides; special-leave → refund the frozen amount. **If any path forgets to reverse, the original
   silent-drift bug returns — so this is the load-bearing discipline, not a nicety.**
4. **Notify ALL involved (owner's rule).** Every supersession sends "**X (details) replaced Y (details)**"
   to: the **Supervisors group**, the **staff** whose day changed, and the **senior** who made/owns the
   superseded decision (and, for a swap, the **partner**). So nobody is surprised and a wrong supersession
   is caught by a human immediately.
5. **The past is locked.** Only **future / not-yet-settled** days are supersedable. Once a day passes and
   AL/OT settles, it's history (`done`) — never rewritten. ("Temp/mutable layer" = everything not yet
   settled; settled = locked. No separate temp TABLE — a separate table is its own spiderweb; it's the
   same rows with a status + a resolver.)

## The events, what they mean, and what balance each moves
| Event | "away" or "working" | Balance it moves | Inverse (on supersede/cancel) |
|---|---|---|---|
| Normal weekly schedule | working (not on day-off) | none | — |
| Approved AL (`al_requests`) | away | −AL days (frozen map) + short-notice points | refund frozen day + reverse points ✓ built |
| Sick (`sick_cases`) | away | (own rules — papers/cover; may free AL) | reverse whatever it moved |
| Special leave (marriage/death/birth) | away | −AL (frozen `deducted_amount`) | `special_leave_refund` ✓ built |
| Senior redefine (`shift_changes`, `senior_id` set) | working (retimed/moved) | OT at checkout only | unsettled → nothing; supersede row ✓ built |
| Payback / OT-rest slot (`shift_changes`, `senior_id` NULL) | working (extra) | settles debt / spends OT bank at checkout | paired w/ booking — release booking too |
| Day-off swap (`dayoff_overrides`, two parties) | flips off↔work for two people | none direct (coverage) | reverse both parties' overrides + re-cover (human) |

## Precedence — the deep corner (NOT pure chronology)
"Newest wins" is right for the common case but **dangerous if applied blindly to balance/leave**, because
some supersessions are sensitive. Two classes of event:
- **AWAY events** (AL, sick, special-leave, swap-off, day-off): "I'm not in."
- **WORKING events** (normal, redefine, swap-work, payback/OT slot): "I'm in, at these times."

Rules that keep it humane AND safe:
- **A newer AWAY event supersedes an older WORKING plan** freely (life happened — they're sick / took
  leave). Reverse the working plan's balance (usually none pre-settle), notify all, surface the coverage
  gap. *This is the swap-then-sick case — it just works.*
- **A newer WORKING event over an older AWAY event (e.g., a senior redefine onto an approved-AL day) is
  SENSITIVE — it revokes someone's leave.** It is allowed ONLY as a **deliberate, explicitly-confirmed**
  act by the senior ("this cancels {name}'s approved AL on {date} — confirm?"), then it refunds the AL,
  supersedes it, and notifies all. Never silent, never automatic. (Today's resolver does this SILENTLY —
  a redefine overrides AL with no refund, no notice. That's the bug this rule kills.)
- **Among AWAY events**, the most recent stands; reverse the prior one's balance (e.g., AL then sick on the
  same day → AL refunds, sick stands — if policy says sick shouldn't cost AL).
- **Among WORKING events**, latest-wins within the SAME feature (senior redefine supersedes senior
  redefine — built); a payback/OT-rest slot (paired) is **not** auto-superseded by a senior redefine —
  the senior is warned it collides with a booked slot (S5 symmetric-picker gap, parked).
- Resolver returns ONE active decision; `/audit` asserts exactly one live decision per staff-date.

## Notify-all (owner's explicit requirement) — concrete
On any supersession, build ONE bilingual line **"🔁 {new, with date+times+who} replaces {old, with
date+times+who}"** and send to: Supervisors group · the affected staff · the senior who owns the
superseded decision · (swap) the partner. Reuse `_att_send` (group + per-uid). Fire-and-forget (best
effort), never blocks the state change. Logged for `/audit`.

## The boundary the machine must NOT cross (keeps it simple, no spiderweb)
A **swap is a two-person agreement.** If one party drops out (sick), the machine: excuses them, reverses
THEIR balance, reverses the dated overrides that are now meaningless, and **alerts supervisors that
coverage broke** — it does **NOT** try to auto-rearrange the partner or auto-find new cover. A human
"does another swap to fix the previous swap" (owner's words). Machine owns **balances + truth + telling
people**; humans own **coverage**. Auto-rearranging coverage is precisely where a spiderweb would grow.

## Every corner (incl. ones we hadn't named) — and the answer
- **Swap → then sick:** sick (away, newer) supersedes their swap-work; overrides reversed; supervisors
  told; partner told; a human re-swaps. ✓
- **AL approved → then sick same day:** sick supersedes AL; AL refunds (don't double-charge leave); sick
  recorded per its rules; all told. ✓
- **Senior redefine onto an AL day:** allowed only as a confirmed revoke → refund AL + notify. ✓ (replaces
  the silent override bug).
- **Both swap partners get sick:** two independent supersessions; each reversed + announced; two coverage
  gaps surfaced; humans handle. No interaction between them = no spiderweb. ✓
- **Chain (change → change → change):** latest active wins; each step reverses the prior's balance; the
  append-only log is the trail, the resolver is the truth. ✓
- **Race (two supervisors at once):** the per-staff `pg_advisory_xact_lock(911,staff_id)` already
  serialises; exactly one supersession wins, the other re-resolves. ✓ (built for F14, reused here.)
- **Past/settled day:** locked — supersede refused (`< today` / `status='done'`). ✓
- **Payback/OT-rest slot in the way:** paired with a booking — never auto-superseded; senior warned
  (parked symmetric-picker fix). The booking's release must pair with any deliberate cancel.
- **Sick currently doesn't touch the resolver** (compute_day_events ignores `sick_cases`) — the unified
  resolver MUST make a sick day an AWAY event so the no-show sweep + prompts honour it. (Confirm the
  current sick→excuse path; today it may rely on the sick flow creating something else, or be a gap.)

## How this avoids NEW bugs (the discipline that makes "simpler" still safe)
1. **One resolver** — kill the drift between compute_day_events / settle / no-show / verdict.
2. **Every supersede reverses balance in the SAME txn** (S1) — or silent drift returns. Each event type's
   inverse is unit-proven on staging before wiring.
3. **Atomic + idempotent** (S2/S3) — the advisory lock + CAS already in place; a double-tap supersedes once.
4. **Reverse reads the FROZEN record** (S1) — never recompute (float drift). Built for AL.
5. **`/audit` asserts the invariant** — exactly one live decision per staff-date; every superseded row's
   balance reversed; no orphaned paired booking. Catches any missed inverse.
6. **F14 stays as the backstop** during rollout — we evolve block→supersede only where the inverse is
   proven, never rip the guard out first.

## Current state → what's needed
- **Built:** AL deduct/refund (frozen, atomic) · redefine latest-wins + senior supersession · special-leave
  refund · the advisory-lock serialiser · `v_one_active_redefine`.
- **To build (phased, on staging, each proven + notify-all + audit):**
  1. `resolve_day(staff, date)` — ONE function returning the single active decision (away/working +
     times + which row), folding AL · sick · special · redefine · swap · normal with the precedence
     above. Repoint compute_day_events / no-show / settle / verdict to it.
  2. Make **sick** an away-event the resolver honours (+ its balance inverse).
  3. **Supersede engine:** `supersede_day(staff, date, new_event)` — in one txn: mark the loser
     superseded, reverse its balance (dispatch per type), emit the notify-all. The sensitive
     working-over-away case routes through a senior confirm first.
  4. **Notify-all** wiring (Supervisors + staff + senior + partner).
  5. Retire the silent redefine-overrides-AL path; the confirmed-revoke replaces it.
  6. Swap-side: reverse both parties' overrides on supersede + coverage-gap alert.

## WIDER SWEEP — where this SAME class of issue lives across the system (owner directive)
Tracking every place the same root patterns can bite, so the phases + the eventual law/audit pass cover
them all — from the original AL-deduction bug through everything fixed to the end of this model:
- **Multi-reader drift (many readers resolving the shared schedule differently).** `shift_change_active`
  is still read DIRECTLY (not via `resolve_day`) in: `_sc_running` (mid-shift extension), the `/test`
  simulate-checkout, and the payback-booking clash check (`bot.py:2786`). Each can disagree with the
  resolver (e.g., not honour leave). → repoint to `resolve_day` (Phase 2+ continuation).
- **`is_test` bleed on a balance/schedule read.** Fixed: `compute_day_events` (now scoped). STILL open:
  `dayoff_override_for` has no `is_test` filter; do a systematic grep of every read on a
  balance/schedule path for the predicate (the AL overhaul fixed `staff_absent_dates`/`al_leave_days_set`).
- **A balance/state moved but not REVERSED on supersede/undo (S1).** Fixed: AL refund, special-leave
  refund, points-on-AL-cancel, OT bank/payback pairs. STILL open: the silent redefine-over-AL (Phase 5),
  the day-off-swap undo (Phase 6), and any future "new cancels old" path (must dispatch a reversal).
- **Implicit precedence between features** (the redefine>AL silent override). Fixed in `resolve_day`.
  Watch for the same wherever two features write one slot (S5).
- **The human element (not technical):** a swap partner dropping out → coverage gap (Phase 6 alert,
  human re-covers); a senior revoking someone's approved leave → must be a CONFIRMED, announced act
  (Phase 3), never silent; a person booked for a change then sick → newest-away supersedes (Phase 3).
- **Other shared resources to re-check with the same lens:** the OT bank (settle add vs buyback spend —
  clean pair today), payback debt (lateness add vs settle credit), `attendance_sessions` (manual vs
  auto-checkout vs crash-redelivery — guarded by the atomic claim). Confirm each stays single-resolver +
  reversible as the model lands.

## Laws + /audit to update (AFTER it's built + proven more accurate than before)
- **S5 → extend** with: "one resolver for the resource; a supersession REVERSES the loser's balance in the
  same txn AND announces to every party (no silent revoke of a balance/leave)." (The notify-all + reverse
  becomes a named sub-rule.)
- **Menu Law 3 (supersession honesty)** already says "tell the user the old thing was replaced" — this is
  its data+multi-party generalisation; cross-link.
- **/audit:** `v_one_active_redefine` → generalise to `v_one_active_decision` (one live decision per
  staff-date across ALL event types); add `v_supersede_reversed` (every `superseded` row that moved a
  balance has a matching reversal); keep the booking↔redefine pairing law.
- Update `docs/STATE_INTEGRITY_LAWS.md`, CLAUDE.md Rule 6, and the memory pointers once proven.
