# s58 Execution Run — turnkey checklist (do in a FRESH chat: "run the s58 execution list")

> Why fresh: these are LIVE PAYROLL-PATH edits. The C1 net makes them safe-by-construction, but edit
> quality degrades on a long session (s58 already leaked test DMs from fatigue). Fresh context = sharp.
> Everything below is net-ready; this is execution, not investigation. Do 1-by-1; gate + verify each.

## C2 — check-in verdict cut-over (the safe first flip; net-ready)
> **✅ STATUS 2026-06-29 — steps 1–4 DONE + VERIFIED LIVE** (tag `session-58-c2-checkin-net-20260629`=`340f017`;
> gm PID 1519626 NR=0, clean boot; `is_authoritative('twb','checkin')`=False = byte-identical no-op; suite
> 1223p/2s). Built `gm_bot/checkin_net.py::verdict_via_net` (routes the RAW verdict through the net; grace /
> points / payback stay live) + `init_flip_db` at startup + 7 tests; verified parity line-by-line == live for
> TWB 5/5. **✅ step 5 THE FLIP DONE 2026-06-29 ~12:06 PP (owner go)** — `set_authoritative('twb','checkin',True)`; independent re-read authoritative=True; no restart; gm active. **INSTANT REVERT: `core.flip.set_authoritative('twb','checkin',False)`.** Watch `core_flip_log` agreement over today's check-in waves.
**Edit:** `gm_bot/bot.py` live check-in, ~line 1907 where `state, mins = ci.verdict(now_min, ws, True, grace_min=_g, early_bonus_min=_e)`.
1. Compute core's verdict alongside live's (bridge signatures; `core.attendance.verdict(when_dt, start_dt, tz, grace, early)` — the shadow_hook already does this bridge, reuse it).
2. Route through the net: `state = flip.decide("twb", "checkin", core_state, state)[0]` (FLAG OFF → returns live `state` → byte-identical; a botched core_state is ignored while off).
3. Staging-prove: flag-off ⇒ identical to today; flag-on ⇒ core==live (parity-lock) ⇒ no divergence. Full suite.
4. Deploy FLAG-OFF (quiet window) → **verify ZERO behavior change** (it's a no-op).
5. **Flip:** `core.flip.set_authoritative("twb","checkin",True,"cut-over")` → watch the flip-divergence Sentinel detector + the auto-revert. ⚠ NOT a pure no-op: ~0–2% day-boundary edges (the reason it was HELD) now take core's verdict → real points/payback edge effects. Owner-aware go.
6. Revert anytime: `set_authoritative("twb","checkin",False)`.

## F1 — exceptions live-wiring (per toggle, each its own gate)
> **⚙ STATUS 2026-06-29 — STARTED (staging, NOT deployed).** Foundation `gm_bot/exceptions_live.py`
> (fail-safe; default {} = unchanged) + 4 tests. **`no_attendance` gate WIRED** at the check-in handler
> (`_handle_staff_location`) + scheduler + no-show sweep (generalises the hard-coded Tyty skip). Prod has
> **0 exceptions set** → deploying the wiring is a no-op; SETTING Tyty/Thyda's exceptions is the
> owner-gated flip (with a test-mode walk). **`no_supervisor_posts` MECHANISM + 10 main sites WIRED**
> (2026-06-29) — the gate lives in `_att_send` (the send chokepoint); each converted site passes
> `subject_staff_id`, un-converted sites post as today. Converted Thyda's day-to-day: sick (×4) · no-show ·
> own-sick · late-reason · reason-nudge · AL-approved · payback-booked. 4 gate tests; suppresses in test
> mode too. **STILL DEFERRED (own passes, mapped):** the RARE no_supervisor_posts sites (death/birth leave ·
> supersession announces ×8 · OT-rest · swap · family-status · callout — finish before Thyda go-live) ·
> no_points/no_lateness (needs audit-invariant handling: zero late-min when exempt) · no_payback (3 sites) ·
> payback_to_al (HIGH-RISK leave reroute, 2nd-opinion) · al/leave/swap approver overrides (NEW routing
> build) · no_al/no_ot.
Read `core.exceptions.get_exceptions("twb", staff_id)` at each live gate, 1-by-1 (each staging-proven, default=no-change):
- `no_nudges` → guard the nudge/reminder sends · `no_supervisor_posts` → guard the Supervisors-group post · `no_management_posts` → guard the Management post · `no_attendance`/`no_lateness`/`no_payback`/`no_al`/`no_ot`/`no_points` → guard the respective compute/record · `payback_to_al` → in the payback-debt path, deduct AL instead of booking payback · `*_approver_id` → override the approval routing.
- Owner's live set first: **Tyty** = vip_exempt (all) · **Thyda** = `no_supervisor_posts` + `payback_to_al` + AL-approver=Tyty (keeps points).

## D1 then D2 — money-path flips (HIGH-RISK; D1 first)
- **D1:** generalize the replay-scorer (`scripts/replay_checkins.py` is the check-in one) to score points/payback/settle candidates on real history (the per-path net for D2 + the fix-bake-off).
- **D2:** net + flip each, 1-by-1: recording → points → payback → settle. Each: per-path net (D1) → staging before/after on a real row → flag-off deploy → flip → watch. Auto-reverts on divergence.

## Phase 5 — the scheduled agent (makes Claude auto-aware) — OWNER SWITCH
Owner: enable a scheduled cloud agent (/schedule) with scoped repo + prod-read access. It runs (all already built): `scripts/morning_report.py` + sink read (`scripts/alarms.py`) + `core.sentinel.sweep` → confirms/extends auto-heals · PREPARES risky fixes as one-tap · DMs a digest. Never auto-moves money/payroll or auto-deploys.

## Also from the client/builder sweep (not payroll)
- Wizard builder/admin split (SECURITY, W3) · monitor-jobs extraction to a builder service (multi-client) · shadow_hook out of the client bot (at cut-over). Builder→client twins (client ops-digest).

## Owner-only (human login/UI — impossible for Claude)
BotFather test bot (validate onboarding) · server GitHub PAT (so `--sync` works) · `secret_guard.py:33` regex.
