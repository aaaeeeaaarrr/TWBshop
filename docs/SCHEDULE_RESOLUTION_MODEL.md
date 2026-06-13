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
  - **Phase 1a DONE** — `resolve_day()` (the one resolver, precedence, is_test-scoped) + `_day_context` batch.
  - **Phase 1b DONE** — `compute_day_events` repointed → the two bugs vanished (redefine no longer
    overrides AL; sick honoured; is_test bleed closed). no-show rides compute_day_events → also fixed.
  - **Phase 2 DONE** — lateness verdict repointed; settle gained a `resolve_day` leave-guard.
  - **Phase 3a DONE** — additive `supersede_day(staff, date, today_iso)`: reverses approved AL (per-day,
    proven inverse) + stands down SENIOR redefines (spares payback/OT-rest slots), idempotent, returns
    descriptors for notify-all. NOT yet wired into any creation path.
- **PHASE 3b — WIRE `supersede_day` into every creation path (the re-sweep map; do each with proof):**
  - **AL approval** (`_al_finalize`): an approved AL is AWAY-over-working → stand down a senior redefine
    that day (replaces F14's block for this direction). away-over-working = automatic + announced.
    **DONE (Phase 3b-i).** Done IN-TXN inside `al_approve_and_deduct` (same advisory lock + claim, so a
    crash can't deduct-without-superseding), not via the standalone `supersede_day` — a senior redefine
    pre-settle moves no balance, so the inverse is a pure status flip and belongs in the atomic approve.
    A payback/OT-rest slot (senior_id NULL) and a swap-work override on the day STILL block (their
    inverses aren't auto-safe yet); a settled 'done' redefine blocks (locked history). Request-side
    (`al_date_conflict`) relaxed to match (senior redefine no longer blocks a submit). Notify-all seed
    `_announce_supersessions` tells the owning senior + Supervisors group ("🔁 X took AL …"). Proven on
    staging: `test_al_approval_supersedes_senior_redefine`, `..._request_side_allows_senior_redefine…`,
    `..._concurrent_vs_senior_redefine_al_always_wins` (race, ×8), `..._blocks_when_payback_slot_shares…`.
  - **Sick creation** (the sick flow): make sick an AWAY event (resolver already honours `sick_cases`) +
    `supersede_day` the sick day(s) to stand down a working event; reverse balances; announce.
  - **Special-leave creation** (marriage/death/birth): `supersede_day` across the span (extend the engine
    to special-leave reversal — currently AL+senior-redefine only).
  - **Redefine approval** (`shift_change_approve_claim`): the SENSITIVE working-over-AWAY case — route
    through a **senior confirm** ("this cancels {name}'s approved leave that day — confirm?") that then
    `supersede_day`s the AL (refund) before approving. Replaces today's F14 block + the silent override.
  - **Swap approval** (`swap_approve_claim`): Phase 6 — reverse both parties' overrides on supersede +
    coverage-gap alert; extend `supersede_day` to the swap/booking-release case.
- **Phase 4 — notify-all:** on every supersession emit "🔁 X (details) replaced Y (details)" to
  Supervisors + the staff + the senior who owned the superseded decision (+ swap partner).
- **Phase 5** — retire the silent redefine-overrides-AL path (subsumed by the confirmed-revoke above).
- **Phase 6** — swap-side reversal + coverage-gap alert.

## WIDER SWEEP — where this SAME class of issue lives across the system (owner directive)
Tracking every place the same root patterns can bite, so the phases + the eventual law/audit pass cover
them all — from the original AL-deduction bug through everything fixed to the end of this model:
- **Multi-reader drift (many readers resolving the shared schedule differently).** `shift_change_active`
  is still read DIRECTLY (not via `resolve_day`) in: `_sc_running` (mid-shift extension), the `/test`
  simulate-checkout, and the payback-booking clash check (`bot.py:2786`). Each can disagree with the
  resolver (e.g., not honour leave). → repoint to `resolve_day` (Phase 2+ continuation).
- **`is_test` bleed on a balance/schedule read.** Fixed: `compute_day_events` (now scoped via
  `_day_context`). `dayoff_override_for` (unscoped) is now **CLOSED** — its only caller `works_on` was
  removed, so it's dead; the schedule path reads overrides with `is_test` directly. (Still worth a
  one-time grep of any other balance read for the predicate; the AL overhaul fixed the AL-path reads.)
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
