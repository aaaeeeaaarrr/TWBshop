# Autonomous run — 2026-06-23 (owner away; review afterward)

Owner: "proceed with everything step by step, go through all open loops, find ways around manual yes/no,
I'll review later." This is the running log of what I did, so you can review it all at once.

## Bright lines I will NOT cross autonomously (left for you)
- **No live cut-over** — flipping any attendance vertical SHADOW→LIVE (so live reads config) is THE
  high-risk moment; it needs days of shadow agreement + your go.
- **No B2B re-enable** — I'll FIX the F2/F3/F4 money bugs (B2B is stopped), but re-enabling stays yours.
- **No company-name decision** — I'll propose a shortlist for you to pick.
- **No owner-only edits** — global `~/.claude`, the guard hooks.
- **No Telegram test-walks** — I can't tap Telegram; instead I ensure automated coverage so the walk is a
  belt-and-suspenders confirm, not a requirement.

## Safety posture
Everything below is shadow-only / inert / read-only / additive / reversible. Wizard work stays
localhost + read-views + SHADOW-only writes (PRODUCT SECURITY law). Deploys: tag + quiet window + verify;
bots restarted only if their code changed (the wizard service never touches them).

## Log (newest first)

### 1 ✅ Shadow residual — the open check-in mismatches (root-caused + cleared)
The 3 open LIVE check-in mismatches (ids 133/134/135 · staff 11/31/42 · Jun-21) were all WITHIN the 5-min
grace/early window (early 2, early 1, late 4) yet recorded as early/late — i.e. logged by the PRE
verdict-parity core (no grace yet). Today's deployed core (grace 5 / early 5) classifies all three as
`on_time` = agrees with live, and today's 19 check-ins all agree. Root cause = pre-port artifacts, NOT a
bug. Reconciled (reversible; shadow metadata only — touches nothing live). Result: digest "No open LIVE
mismatches 🎉"; the **check-in vertical now reads READY** (0 open · full coverage · 27 samples).
**FOR YOU:** check-in is the first vertical the shadow calls cut-over-ready — I did NOT flip it (your call
+ ideally a few more days of agreement).

### 2 ✅ Wizard admin — cut-over readiness dashboard (answers "where are we")
Added a 🚦 Cut-over status panel to the admin view (`wizard/app.py::render_cutover`): per vertical, how many
real events the shadow has compared, the agree-rate, and READY/gathering — plus how many config knobs are
wired LIVE vs still SHADOW. Read-only (reads `shadow_comparisons` via `build_digest`). So you open `/` and
see exactly how close each vertical is to safe cut-over. (Customer view unaffected — no internals leak.)

_(more appended as each item completes)_
