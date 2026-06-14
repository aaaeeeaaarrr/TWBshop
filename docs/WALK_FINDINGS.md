# Go-Live Walk Findings — owner /test re-walk (Jun 14, 2026)

Punch-list from the owner's pre-go-live `/test` role-play as **PISEY**. Behind `attendance_live=OFF`.
Status legend: **OPEN** (to build) · **DONE** (built+proven) · **NOTE** (no code change).

**▶ BATCH BUILT (not yet deployed) — session, all behind attendance_live=OFF, suite 578 green:**
WF6·WF7·WF1·WF2·WF3 (commit 8a51a08) + WF5·WF9b. NEXT = one gm redeploy in a quiet window → owner
re-walk (incl. Step 8 with the new swap) → `/audit` → `/testreset` → flip `attendance_live`.
- **WF1 DONE** — late prompt drops the "Supervisors notified ✓" line (group heads-up stays).
- **WF2 DONE** — family-sick TIMES path now confirms AND actually files (was a stub that never booked).
- **WF3 DONE** — all family-sick night nudges removed; family-sick books terminal `'cleared'`.
- **WF5 DONE** — partner-swap rebuilt: pick PARTNER → valid date-pairings (both real day-offs ≤6 days
  apart, override-aware/WF9b) → reason. `req_off_date`=partner's day off (you take), `partner_off_date`=
  your day off (they take). Coverage-neutral by construction; card states cover on each date both ways.
  Engine `swap_approve_claim` unchanged. Pure `payback.swap_pairings` + mapping guard tested.
- **WF6 DONE** — `/testseed` deletes child rows first (no FK crash). **WF7 DONE** — terminal bookings
  release the menu singleton. **WF8/WF9a** = no build (reassurance / by-design).

---

## WF1 — Late: drop the staffer-facing "Supervisors notified ✓" line — OPEN
**Owner:** "No need to inform Pisey that 'Late 30mins supervisors notified' message — just straight to
'Type your reason' lines."
- **Where:** `gm_bot/attendance_ui.py:2624-2630` — the `_arm_prompt` shown after the staffer picks the
  late minutes. First line is `"Late ~%d min — Supervisors notified ✓ · មកយឺត ~%d នាទី — បានជូនដំណឹងបងៗ ✓"`.
- **Change:** remove that first line; start the prompt at `"📝 Type your reason …"`.
- **KEEP:** the Supervisors GROUP heads-up (separate message, `attendance_ui.py:2616`,
  "X will be ~Nm late … reason to follow") — unchanged. Only the staffer's own confirmation line goes.

## WF2 — Family-sick TIMES path needs a confirm step (mis-hit protection) — OPEN
**Owner:** "If sick-child full day there's a confirm button after; but selecting times goes straight to a
confirmed message — better the same, because they might mis-hit a wrong time button."
- **Where:** `gm_bot/attendance_ui.py:2510-2528`. Full-day `famf` (2514) does `_arm_pending` +
  `_confirm_prompt` when `_armed`. Times `famtt` (2526) goes straight to `sick_family_stub` — **no
  `_armed` check, no confirm, no reason-arm.** (Real flow, confirmed — not just the dry-run.)
- **Change:** make `famtt` mirror `famf`: when `_armed`, arm pending + show a confirm ("Family sick (X) —
  HH:MM→HH:MM — confirm?") before booking. (Also verify the times path actually FILES the sick row when
  armed — `famf` does via the armed pend; `famtt` currently only shows a stub.)

## WF3 — Remove ALL family-sick nightly nudges — OPEN
**Owner:** "Remove nightly nudges for all family sick. When they want another day/time they should do it
again themselves — no need to tell them that either. (They can only select 1 day or times within a day.)"
- **Where:** `gm_bot/bot.py:3410-3431` — the `sick_family_open_today` loop inside
  `_sick_papers_deadline_job` (the "I hope your {relation} is better 🤍 coming tomorrow?" nudge).
- **Retire too:** `_sick_family_nudge_callback` (`bot.py:3512`) + the `att:sfam:` handler reg
  (`bot.py:6404`) + `_sfam_book` if it becomes orphaned + the dry-run preview steps
  (`attendance_ui.py:619-622`, Dry-run 4 ⑩/⑪).
- **After:** a family-sick entry = one day / one time window; to add another, the staffer re-requests via
  the menu. No bot message prompting them.
- **SCOPE:** family sick ONLY. Leave OWN-sick (me) return-check (`bot.py:3400-3409`,
  `_SICK_RETURN_CHECK` within the papers window) untouched — owner scoped this to family sick.

## WF4 — Dry-runs are read-only (usage note, no build change) — NOTE
**Owner:** "The simulation doesn't allow me to press buttons, it just moves to the next card, so I don't
know if numbers (AL etc.) are changing."
- The Dry-runs (1–7) are **canned read-only previews** (`att:drs:noop` buttons) — by design, no state
  moves. To test behavior + see balances move, drive the **live persona menu** with `/testmode on`
  (as was done successfully for the swap). Not a bug.
- *(Optional, not requested:)* could label dry-run buttons "(preview)" to make the distinction obvious.

---

## WF5 — Rework "Change day off" into a clean partner-swap (Option A) — OPEN (design locked)
**Owner:** today's swap is wrong — it lets the requester pick an ARBITRARY day off, derives the 2nd
date from the *requester's* own weekday (ignores the partner's real day off), so it's **not
coverage-neutral** (e.g. picking a day both normally work leaves the shop short) and the partner can end
up with **two days off**. The card also hides the "work" side, so it never says who covers whom.

**The flaw (current code):** `attendance_ui.py:2737-2758` — `req_off` is any day the requester picks;
`partner_off` = next occurrence of the **REQUESTER's** `day_off` weekday (line 2746-2748); the partner's
real `day_off` is never read. `dayoff_partners` only filters by overlapping shift hours.

**Correct model (a true trade of two people's days off — coverage-neutral by construction):**
- On each swapped date exactly one of the pair was originally off; they flip → headcount unchanged on
  both dates, regardless of calendar week.
- Flow: 🔁 Swap day off → **pick the PARTNER** → **pick one of the valid date-pairings** → reason →
  partner agrees → seniors approve. (No arbitrary-day picking; the two dates ARE the two people's real
  upcoming day-off occurrences.)

**Decision LOCKED (owner, Jun 14):**
- Pair each person's **upcoming real day-off occurrences** where the two dates are **≤ 6 days apart**.
- **Show ALL valid pairings within that 6-day window and let the staffer pick one** (e.g. "your Thu 18 ↔
  Heng's Mon 15" and "your Thu 18 ↔ Heng's Mon 22").
- **Drop** the "same calendar week" constraint (replaced by the ≤6-day gap) and **drop** arbitrary-day
  picking entirely. (Option B — a one-off "I need a specific day, someone covers" request — NOT wanted;
  if it ever is, it's a separate leave/coverage request, not a swap.)
- **Card states cover explicitly** on each date, both languages: "PISEY takes Heng's day off (Mon 15) —
  Heng covers · Heng takes PISEY's day off (Thu 18) — PISEY covers."

**Engine:** `swap_approve_claim` already writes 4 overrides from two arbitrary dates → **unchanged**.
This is date-derivation (use BOTH people's `day_off`) + the pairing/picker UI + the card wording + the
≤6-day check replacing same-week. F14/supersede net still applies to each swapped date.

---

## Walk progress (Jun 14)
- **Step 1 Check-in:** skipped (owner not at location; previously verified working).
- **Step 2 Late:** walked → WF1.
- **Step 6 Sick:** walked (via dry-run) → WF2, WF3.
- **Step 7 Swap:** ✅ COMPLETE & CORRECT — full flow PISEY↔Heng: submit → partner agree → ✅ I agree →
  2 senior approvals → Approved → requester + partner + Supervisors notices all routed to owner (test).
  (Earlier confusion: in test mode every party's message routes to the owner — no persona-switch needed;
  the walk instruction was wrong, the build is current.)
- **Step 8 F14 collision layer:** PARTIAL — 8a done+verified; 8b mis-fired; 8c/8d not done. Findings WF6–WF9 below.

---

## Step 8 walk (Jun 14) — results + new findings

- **8a Supersede (AWAY beats a planned redefine):** ✅ DONE & DB-VERIFIED. Anan (id 5) took AL on Tue
  23/06 which carried a senior redefine (9pm–10am). Result on real test rows: `shift_changes` id 19 →
  **`cancelled`** (superseded ✓); AL request 88 `deducted_map = {'2026-06-23': 0}` → **0 AL deducted**,
  balance unchanged (7 left). **0 is CORRECT** — 23/06 is Anan's day-off (day_off=Tue), and "Day off =
  No AL used"; once the redefine stood down, the day reverts to a day-off so no AL is spent. Supersede
  notices reached the senior (Por) + Supervisors. *(Nuance to remember: superseding a redefine that sat
  on a day-off costs 0 AL — the number correctly does NOT move.)*
- **8b Block:** mis-fired — see WF9. The owner tried to book a payback slot on the **redefined** date,
  which the PB picker excludes by design, so the "PB-slot-blocks-AL" path wasn't exercised. Re-run on a
  CLEAN (non-redefined, non-day-off) date.
- **8c Confirm-revoke / 8d Request-side block:** NOT yet walked.

## WF6 — /testseed crashes (FK) once any approval/booking exists — OPEN (real bug, test-harness)
`attendance_testseed` (`shared/database.py:2627-2628`) deletes `is_test` rows from `al_requests` and
`payback_debts` **without first deleting their child rows** — `al_approvals` (→al_requests) and
`payback_bookings` (→payback_debts), neither ON DELETE CASCADE. After any walk that approves an AL (8a)
or books a PB slot (8b), re-running `/testseed` hits a ForeignKeyViolation and crashes; it keeps
crashing on every retry (looks "not recognized") until `/testreset`, which deletes child-first via the
correctly-ordered `_TEST_TABLES`, clears them. **Fix:** seed must delete children first (mirror
`_TEST_TABLES` order, or `DELETE FROM al_approvals WHERE is_test AND request_id IN (…)` then al_requests;
same for payback_bookings→payback_debts). **Workaround now:** `/testreset` before `/testseed`.

## WF7 — Terminal "booked ✓" confirmation gets collapsed by the menu singleton — OPEN (real UX bug)
After booking a PB slot, the harmless terminal confirmation (PB details, no actionable buttons) is the
edited-in-place picker message, which is STILL registered as the P1 singleton's `att_menu_msg`. The PB
booking path never calls `_menu_release`, so the next menu-open collapses it to "⤵ Menu continues
below", destroying the details. Design intent (attendance_ui.py:2304 `_menu_release`) is that terminals
unregister — the booking paths just don't. **Fix:** call `_menu_release(context)` at terminal
confirmations (PB booked; audit AL/swap/sick "booked ✓" too). Matches owner's ask: harmless buttonless
endings must not collapse. *(Owner alt: send terminal as a NEW message that deletes the old menu.)*

## WF8 — (reassurance, NO bug) a senior cannot shorten a shift below normal
Owner asked: if a senior picks fewer hours, does the staffer owe payback? **No — shortening isn't even
offered.** `ot.end_option_tags` builds the END ladder starting at `start+normal_len` (the FULL length,
untagged) and only longer (+PB/+OT). A redefine either MOVES the shift (same length) or EXTENDS it;
the staffer always works ≥ their normal hours, so a redefine never mints payback debt. No change needed.

## WF9 — PB picker excludes redefined dates (by design) + ignores day-off OVERRIDES (latent) — NOTE/OPEN
(a) **By design:** `_sc_taken_dates`→`shift_change_upcoming_dates` removes any date holding an approved
redefine from the PB picker (`bot.py:1465`) — a PB slot IS a redefine and would supersede the existing
one; the existing extension already pays down debt at checkout. So the owner's "changed date doesn't
show" is intentional. (b) **Latent gap (deeper):** the picker computes working-days/day-offs from the
STATIC `staff['day_off']` weekday (`working_days_ahead`/`dayoff_dates_ahead`) and does NOT consult
`dayoff_overrides` — so after a swap, a traded day-off isn't reflected (could offer a slot on a now-off
day, or miss a now-working day). Separate from WF1–WF5; fold into the resolver-consistency pass.
