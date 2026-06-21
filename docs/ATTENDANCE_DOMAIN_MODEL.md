# Attendance Domain Model — MVP design (FIRST CUT, refine step by step)

> The platform's first module, built on the principles in `PLATFORM_VISION.md` + `SHIFT_MODEL_DESIGN.md`:
> **multi-tenant, channel-agnostic, entity + event, date = label only.** This is the "no.1" the owner
> green-lit. FIRST DRAFT for refinement — not final, nothing built.

## The one rule everything obeys
A **shift is a time interval** with a stable ID. All logic reasons on `start_dt` / `end_dt` (absolute,
UTC). The calendar date is a **derived label** (`business_day`) for humans/reports/grouping — never the
identity, never the basis for is-now / has-passed. This is what makes overnight, splits, swaps,
reschedules, and any business "just work."

## Core entity: `shift` (one scheduled work interval for one person)
| field | meaning |
|---|---|
| `shift_id` (PK) | stable identity — everything references THIS, never the date |
| `org_id` | tenant (multi-tenancy; every row scoped) |
| `staff_id` | who |
| `start_dt`, `end_dt` | the real interval (UTC instants) — the source of ALL time logic |
| `business_day` | DERIVED label for grouping/reports (per-tenant rule: usually date-of-start) |
| `status` | scheduled · active · closed · cancelled |
| `origin` | how it came to be: regular-schedule · swap · senior-redefine · payback-slot · OT |
| `parent_shift_id` | for a redefine/extension/split: links to what it changed (audit) |
| `created_at`, `updated_at` | |

Notes:
- An **overnight** shift is simply `end_dt` on the next calendar day — no special case anywhere.
- A **split shift / two shifts in a day** = two `shift` rows. (The old date-as-ID model couldn't do this.)
- **Frozen history:** once worked, a shift's interval is what it WAS — a later schedule change creates a
  new/edited shift, it never silently rewrites a past row (correct payroll history).

## The event log (append-only, the audit + integration backbone)
Every change is an **event**, never an in-place mystery mutation. Read-models (current schedule, balances)
are built/verified from events. One table:
`event_id · org_id · at · actor · type · shift_id? · staff_id · payload(JSON)`

Event types (MVP set):
- **Schedule:** `shift_scheduled`, `shift_moved` (new start/end), `shift_extended` / `shift_shortened`,
  `shift_cancelled`, `shift_split`, `swap_applied` (A↔B).
- **Attendance:** `checked_in` (at, location), `checked_out` (at), `marked_late` (minutes, informed?),
  `marked_early`, `marked_absent` / `no_show`.
- **Leave:** `leave_taken` (kind: AL/sick-own/sick-family/special; window; reason), `leave_cancelled`.
- **Balances (money/state):** `payback_owed`, `payback_credited`, `ot_banked`, `points_awarded`.
Each balance event is the SINGLE source of a balance change → the per-event verifier just re-reads + asserts.

## How every change-type the owner listed maps (no date logic anywhere)
| Real-world change | Becomes |
|---|---|
| Senior moves a shift to another day (back & forth, same-time or cross-midnight) | `shift_moved` (new start/end) on the SAME `shift_id` |
| Extend / shorten / a few hours / full day | `shift_extended` / `shift_shortened` (new end_dt) |
| Day-off swap (A takes B's day) | `swap_applied` → shifts reassigned/created with their real intervals |
| OT / payback slot | a shift with `origin=ot`/`payback-slot` (its own interval) + a balance event on settle |
| Sick / AL | `leave_taken` that supersedes the overlapping shift(s) by interval, not by date |
| Two businesses, any pattern (rotating, on-call, 24h) | just more `shift` rows with different intervals |

## Multi-tenant + config (so it's a product, not TWB-only)
- `org_id` on every row + every query scoped to the tenant (the #1 SaaS safety rule).
- Per-tenant **config** drives behavior: timezone, locale, geofence, the schedule/shift patterns, leave &
  points rules, currency, enabled channels + tokens, the `business_day` cutoff rule. None hard-coded.
- TWB's current rules become TWB's tenant config (reuse the RULES; drop the hard-coding).

## Channel-agnostic boundary (proof the model is delivery-independent)
The core exposes **commands** + emits **results/events**; channels are adapters.
- Commands (examples): `CheckIn(org, staff, when, location)`, `RequestLeave(...)`, `BookPayback(...)`,
  `MoveShift(...)`. Pure domain — no Telegram/web/app types.
- A **Telegram adapter** (reuse TWB's surface) turns a tap/message into a command + renders the result.
  A **web adapter** later does the same from a page. The core never knows which.

## The thinnest first increment (build #1, shadow-run vs live TWB)
**check-in / check-out** through the whole new stack: `shift` entity + `checked_in`/`checked_out` events +
`CheckIn`/`CheckOut` commands + Telegram adapter + TWB tenant config + a **shadow comparator** (every real
TWB check-in also runs the new core; assert new == live; zero exposure). Prove it → port lateness → AL →
sick → OT → payback → points onto the same shape → add web adapter → onboarding wizard → package → sell.

## Locked decisions (owner, 2026-06-22 — working basis, refine details)
1. **Recurrence:** a schedule TEMPLATE materializes `shift` rows a rolling ~30 days ahead (stable IDs to
   reference), not pure compute-on-the-fly. A daily job extends the horizon + applies template changes to
   not-yet-started shifts only.
2. **Balances (debt / OT bank / points):** keep a balance ROW per staff + verify it against the event
   trail (not full replay). The per-event verifier asserts row == sum(events).
3. **`business_day`:** date-of-start by default; per-tenant cutoff configurable later. Label only.
4. **Staff identity:** one `staff_id` + a `channel_identities` table (telegram_id, web_login, … all map to
   the one person).
5. **Shadow comparator (first asserts):** the check-in VERDICT + lateness MINUTES, then credit amounts.

## ⚠ TOTAL-MIND interaction & edge-case map (owner: "don't trade old bugs for new ones")
Switching identity from *date* to *shift_id* ripples everywhere that used the date. Each interaction below:
how the new model handles it **+ the NEW risk it introduces that we must design against.**

- **Identity ripple (the big one).** Today `attendance_sessions`, `payback_bookings`, `shift_changes`,
  `sick_cases`, points all key on (staff, DATE). New: they reference `shift_id` (for per-shift things) or
  stay per-STAFF (balances). **Rule:** *per-shift* facts (check-in, lateness, a payback-slot, OT on a
  shift) → `shift_id`; *per-staff* balances (debt, OT bank, points) → `staff_id` (a shift event credits
  them). **New risk:** a wrong shift↔event mapping at migration/shadow time → assert it in the comparator.

- **Far-date move / overlap.** `shift_moved` keeps `shift_id`, changes the interval — far dates are just
  different instants. **New risk the model now EXPOSES (and must guard):** a move can make two of a
  person's shifts **overlap** (the old date-model couldn't even represent two shifts/day, so it never
  checked). **New invariant:** *no two active shifts for one staff overlap* (unless an intentional split
  with a gap) → reject/flag the move. Also: only a **scheduled/future** shift may be moved — never a
  worked one (a worked interval is frozen history).

- **Payback ladder + deadline + over-book.** The ladder counts working days → now = **upcoming shift
  instances** (entities), and a payback slot **is** a shift (`origin=payback-slot`). **New risk = the SAME
  class as the bug we just fixed:** a stale plan. **Rule:** the ladder, the deadline count, and the
  `book_room` over-book guard must ALWAYS re-derive from the CURRENT shifts/events, never a cached plan —
  and if a counted shift is later moved/cancelled, an event re-triggers the re-derive. (The entity model
  makes "what's my real remaining + my real upcoming slots" a clean query instead of date math.)

- **Leave (AL / sick / special).** `leave_taken` supersedes the shift(s) it **overlaps by interval**
  (handles half-day / partial = shorten or split the shift). **New risk:** leave overlapping a shift that
  ALSO has a payback/OT origin, or a leave whose window crosses midnight → resolve by interval-overlap,
  not by date-equality (one resolver, like today's `resolve_day` but interval-based).

- **Swap (A↔B day-off).** `swap_applied` reassigns/creates shift instances with their real intervals.
  **New risk:** a swap that creates an overlap (see invariant above) or leaves an orphan (B's cancelled
  shift still referenced) → both sides emitted as one atomic event-pair; the overlap invariant catches the rest.

- **Balances on cancel/reverse.** A points/credit event for attendance that ALREADY happened **stands**
  even if a later part changes; cancelling a **future scheduled** shift just cancels (nothing to reverse).
  **Rule:** events for things that occurred are immutable; reversals are explicit compensating events
  (`payback_credit_reversed`), never silent edits — so the balance row always == sum(events).

- **The shadow comparator is itself overnight-sensitive (irony to guard).** It maps an old (staff, DATE)
  row to a new `shift` entity by INTERVAL. **New risk:** mis-aligning an overnight old-row to the wrong
  new-shift → the comparator must map by the interval the work fell in (reuse the overnight-aware binding),
  and a mapping failure must surface as a comparator error, not a silent "match."

- **Cutover migration (date-keyed → shift_id).** In-flight shift (someone mid-overnight) → maps to the
  active shift entity; open debt/OT/points (per-staff) → carry over unchanged; booked future payback slots
  → become shift entities. **New risk:** an in-flight or booked row that doesn't map cleanly → migration
  must be a dry-run-first, reconciled, reversible step (same rigor as a balance migration).

### New invariants the model must enforce (so new bugs can't hide)
1. **No overlapping active shifts** for one staff (the move/swap guard).
2. **Worked intervals are frozen** — never moved/edited; changes create new shifts or compensating events.
3. **Always re-derive** ladder / deadline / over-book from current state — never a cached plan.
4. **Balance row == sum(its events)** — enforced by the per-event verifier (the "check everything" layer).
5. **Comparator maps by interval + fails loud** on any unmapped old/new row.

## Open (finer detail, refine as we build)
- exact event payload schemas; the `channel_identities` shape; the per-tenant config schema; how the
  schedule template expresses patterns (rotations, splits); reversal-event catalogue.
