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

## Open design questions to refine next (step by step)
1. **Recurrence:** store each `shift` instance up front (generate from a schedule), or compute upcoming
   instances on the fly + materialize on first touch? (iCal RRULE-style vs eager rows.)
2. **Balances:** pure event-projection (replay) vs entity + event-trail (maintain a balance row, verify
   against events)? (Recommend the latter for simplicity + the per-event verifier.)
3. **`business_day` rule:** date-of-start everywhere, or a per-tenant cutoff (e.g. 03:00) for reporting?
4. **Identity for staff across channels:** a person may have a Telegram id AND a web login — one `staff_id`,
   many channel identities.
5. **Shadow comparator scope:** which outputs do we compare new-vs-live first (the check-in verdict +
   lateness minutes are the obvious first asserts)?
