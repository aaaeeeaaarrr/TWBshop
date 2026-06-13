# Go-Live Walk Findings — owner /test re-walk (Jun 14, 2026)

Punch-list from the owner's pre-go-live `/test` role-play as **PISEY**. Behind `attendance_live=OFF`.
Status legend: **OPEN** (to build) · **DONE** (built+proven) · **NOTE** (no code change).

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
- **Step 8 F14 collision layer:** NOT yet walked (next).
