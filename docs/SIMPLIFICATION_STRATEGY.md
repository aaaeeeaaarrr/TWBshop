# Simplification strategy — "map, don't remodel" (2026-06-19, owner + Claude)

> Captured so a fresh session (esp. on another machine) doesn't re-litigate this. Decision stands
> until the owner changes it.

## The question
Owner asked: read the whole system, re-imagine it clean (no redundancy/noise), then **replace** the
code with simpler files — to escape past bugs. How dangerous?

## Verdict: the REWRITE-and-replace is VERY dangerous — don't do it.
- It **maximizes the exact thing you want to avoid**: the "noise" you'd delete is mostly *scars* —
  overnight date-binding, idempotent claim-before-bank, go-live grace, F14 locks, resolver precedence.
  Delete them and you re-live every solved bug, on real staff pay.
- It's **live, with real money/people**; a cutover risks attendance/leave/pay + trust.
- **769 tests encode the spec**; a rewrite invalidates them.
- It's a **moving target** (accountant/stock still building) and **open-ended** effort (months).
- Honest axis check — the clean approach is **NOT better in every way**: safer than a rewrite (yes),
  more understandable (yes, via the map), but not faster and not auto-"better structure". The single
  most valuable property — *it works, proven, live* — you ALREADY have; no remodel improves it, the
  best it can do is not break it.

## What we DO instead (the safe benefit, minus the danger)
1. **Map, don't remodel.** `MAP.md` gives the understanding/trust you actually want (the real problem
   was *not seeing/trusting* the system, not bad code) — at zero risk.
2. **Delete only provably-dead code** (no callers, tests green). Safe noise removal.
3. **Refactor only what actively hurts** — behavior-preserving, one module, tests green, shipped+verified.
   Never big-bang. Characterization-test a module BEFORE refactoring so "simpler" can't mean "different".
4. **Otherwise leave working code alone and keep shipping.** The urge to remodel for cleanliness is
   itself often the noise. "Do less, understand more."

## Bonus ideas (when wanted)
- **Lessons & Guards index** — every past bug → the test/law that now prevents it, in one list, so a
  recurrence is visibly impossible (the trust you're chasing).
- **"Does it earn its keep?" audit** — list each subsystem; the win is often *retiring* a feature
  (less code, same behavior) — far safer than rewriting one.
- **Pilot refactor** — take the one messiest module, do a clean behavior-preserving pass, feel the
  cost, THEN decide if it's worth continuing.

## The MAP mechanism (built this session)
- `MAP.md` (index only — never prose) + `CLAUDE.md` top-pointer ("open MAP.md for any task") +
  `tests/test_map_integrity.py` (fails the build on a dead pointer or an unmapped package).
- **Mechanical ceiling:** ~100% on "no dead pointers + no missing subsystem"; NOT 100% on "complete +
  accurate" (a new file inside an existing area, or a stale gotcha, stays human discipline).
- **Rule:** any file move/rename/new subsystem updates `MAP.md` in the SAME commit. With the map in
  place, `CLAUDE.md` can be trimmed further (detail lives behind the map), but only carefully.

## Honest caveat that drove all this
Cross-session memory is unreliable (it failed on 2026-06-19 — claimed gaps that were already solved
and documented). So lessons must live in **docs + tests** (artifacts that travel), not in "Claude will
remember". The map + the don't-assert-without-checking rule are the fix.
