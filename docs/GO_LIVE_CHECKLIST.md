# Attendance Go-Live Checklist — SINGLE SOURCE

> The one tracked list for flipping `attendance_live`. Consolidated 2026-06-16 from the three places
> this used to live (this file, the embedded list in `ATTENDANCE_SYSTEM_DETAILED.md`, and the greeting
> notes). Everything is built behind the `attendance_live` master switch (default OFF = zero staff
> contact). When in doubt about *behaviour*, the spec is `ATTENDANCE_SYSTEM_DETAILED.md`; this is the
> go/no-go.

---

## ✅ BUILT, SHIPPED, GATED OFF (the whole system)
Check-in (scheduler + live-location + verdict + sessions) · late→payback (debt, slot picker, ignore-
ladder, Supervisors notice) · **auto-checkout** (live-share in-zone at shift end) · **AL** request/approve
with deduct-at-approval + refund-on-cancel · **Special Leave** (own-sick anti-fake ladder + papers AI,
family-sick, marriage, family-death two-tier, wife-birth) · **OT / shift-redefine** (emergent OT, bank,
buyback) + shield · **Staff Changes** A1 (change time +OT) / A2 (move a day off) with 2-senior co-approval
+ staff approval · **day-off swap** (partner-first → seniors, ≤7 days) · **8b** leave-on-a-committed-day
(coexist/refund) · **F14** collision net (AL↔AL, AL↔redefine confirm-revoke, AL↔swap coexist) · points
engine (activated, catalogued) · group-redirect · My-Schedule · weekly digest (Brain-computed) · `/test`
harness (personas, `/testclock`, `/testrun`, simulate-checkout) · watchdogs + daily `/audit` ·
test-mode isolation (`is_test`) · KH batch wired + vetted.

## ✅ VERIFIED THIS GO-LIVE PASS (Jun 16)
- Owner role-play walk **Parts 1–4 complete** (A1 · A2 · 8b 3a/3b/3c/3c-2/3d · F14 double-AL + confirm-revoke).
- Staging end-to-end **balance proof** (double-redefine no-double-bank · AL-on-swap coexist charge · confirm-revoke refund).
- `resolve_day` **collision matrix** (one coherent decision per day, no double-work).
- `/audit` **clean** on test + real rows (only a historical dead-tap that clears on `/testreset`).
- Tests now run on **staging** (conftest) — the suite can no longer pollute prod.
- **Late sick-informing** (−15 own / soft-note family / come-in grace) + **gender** column (26/26 matched)
  built, tested (suite 617), deployed inert; all KH vetted (ChatGPT) + wired.
- **Go-live tooling** built: `/golive` (stamps + flips, with grace for staff already on shift), `/broadcast`
  (one-time greeting + "try it now"), `/golivestatus` (who tried check-in).

---

## ⏳ REMAINING BEFORE THE FLIP

### A. Content — ✅ DONE (built + vetted, all behind the flip)
1. **GM greeting** — reworded (dropped the obsolete 📋 Menu line) + the "tell us early or lose points 🔻"
   disclaimer; canonical text embedded as `_GREETING`; sent by **`/broadcast`** at flip (idempotent) with a
   "try it now" nudge to staff on shift. KH vetted (ChatGPT).
2. **Rules screen** — the **doctor's-papers → no pay-back** line is **wired** (KH vetted). +15 part-duty left OUT.
3. **Khmer** — greeting / rules / broadcast vetted+wired; **late sick-informing** callouts + deferred −15
   reminder + mandatory-reason term vetted+wired (Jun 16). No content blockers remain.

### B. The launch gate
4. `/audit` on the test rows reads ✅ clean (done — re-run anytime for assurance).
5. `/testreset` → `/teststatus` shows zero test rows.
6. Confirm **every active staffer has pressed Start** (last count 33/33 — re-confirm).
7. **🔴 Remove ex-partner (Paul) admin from ALL Telegram groups** (owner, in-app) — before the GM bot is
   prominent in groups. Claude can't touch group admins; **remind the owner at the flip.**
8. Brief staff on what's changing.

## 🚦 THE FLIP — owner runbook (owner commands, in order)
1. `/testmode off` → `/testreset` → `/teststatus` shows zero test rows.
2. **Remove ex-partner (Paul) admin from every group** (in-app; Claude can't).
3. `/golive confirm` — stamps `attendance_live_at`, then flips `attendance_live='true'`. The grace exempts
   anyone already on shift at the flip (they couldn't check in pre-live).
4. `/broadcast confirm` — one-time greeting DM to all active staff + "try it now" to those on shift.
5. `/golivestatus` — of staff on shift now, who tried check-in vs not. **Verify** a real staffer routes to
   themselves (not the owner) and a test tap no longer hijacks.
6. **Live-location requirement stays OFF** until the owner has explained it to staff (staged go-live).

---

## 🅿️ POST-LIVE (parked, not blockers)
- **Owner test capability after live** — owner wants to rehearse new features post-live. The current
  `attendance_test_mode` is a GLOBAL switch (routes *all* messages to owner + tags *all* writes `is_test`
  + warps the clock) → **unsafe to flip while live.** Safest path: a **separate test bot** (own token,
  own process) pointed at the **staging DB** — shares nothing with live, so it can't corrupt live data.
  (An in-process owner-scoped redesign is possible but carries a real residual data-corruption risk;
  the separate bot avoids it.)
- **Digest source when live** — replace the AI digest with the structured one, or show both? (owner decision)
- **Bedrock delta 2** — owner OS-locks the global guard files (elevated shell).
- **Staging cutover** — route the raw-`psycopg2` run-scripts through `_db()` so they honor the env switch too.

---
> The old embedded checklist in `ATTENDANCE_SYSTEM_DETAILED.md` (§"⛔ BEFORE GO-LIVE") is **superseded by
> this file** — it was a stale running log (listed long-built features as "not built"). Spec/behaviour
> detail still lives there; the go/no-go is here.
