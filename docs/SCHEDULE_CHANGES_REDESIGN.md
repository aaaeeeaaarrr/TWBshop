# Schedule Changes redesign (replaces "Give OT / change shift")

Brainstormed + converged with the owner (Jun 15, 2026). Behind `attendance_live=OFF`.
**Every new bilingual string → `docs/KH_REVIEW.md` (Pending) for the owner's translation pass.**

## Why
The old "Give OT / change shift" mixed change-time, change-day-onto-a-day-off, and full-day into one
flow — which caused the 8a confusion ("which day did my day off move to?"). Split it into two clean,
purpose-built actions. Senior-driven; staff approves. (Day-offs are hidden in the working-day pickers
on purpose — change-time/OT is for *working* days; see the owner's screenshot.)

## Entry — Senior "About Work"
- **Staff Changes (1 time)** → [A1 Change time +OT · A2 Change day off]   ← BUILD THIS
- **Staff Changes (forever)** → PARKED (permanent change; needs ALL available seniors + the staff +
  the OWNER to approve — seniors see "Awaiting Owner approval". Design later.)
*(Naming: "Staff Changes" per owner; consider "Schedule Changes" — minor, deferred.)*

## A1 — Change time +OT
1. Pick staff.
2. Pick a **WORKING day** within **30 days** (day-offs hidden).
3. Start time — top full-width button **"⏱ Normal times {ws}–{we}"** (one tap = normal start+end,
   **skips the end menu** straight to reason/confirm); otherwise pick a custom start.
4. End time — the **+PB/+OT** ladder (only when a custom start was chosen).
5. Reason → submit. **Staff approves** (proposing senior = the 1 senior).
- Card shows the new hours + PB/OT tag + the **👁 who's-working** toggle.
- This is today's change-TIME path carved out clean: **no full-day, no day-off option.**

## A2 — Change day off (a true MOVE, not "work a day off")
1. Pick staff.
2. Pick the **day they'll be OFF (X)** within **30 days** (a working day → becomes off).
3. Pick the **comp work day (Y)** = one of the staff's **day-offs within 7 days before/after X**
   (the day-off they give up to work instead → total days worked unchanged, fair).
4. Set **Y's hours** start→end with the **same +PB/+OT end ladder as A1**, top button **"⏱ Normal
   times"** (custom hours allowed — e.g. what Vannary did — AND they **can extend into OT** to cover).
5. Reason → submit. **Staff approves**.
- Card: "Off **X** · works **Y {hours}**" + the **👁 who's-working** toggle on BOTH dates.
- Coverage: X −1 body, Y +1. A **senior** may decide to accept that shift (authority); the toggle makes
  it an informed call. (A *staffer* can't dent coverage solo → they use SWAP instead. Clean split.)

### A2 implementation (owner: my chosen approach unless you object)
- Writes a **shift_change redefine on Y** (carries Y's hours, drives attendance/settle) + a
  **dayoff_override `kind='off'` on X** (the new rest day). resolve_day already handles both kinds.
- **A2 comp day CAN extend to OT** (owner, corrected): the end ladder offers +PB/+OT just like A1, so
  the comp shift can be normal-length OR extended to cover (OT banks at checkout via the redefine).

## END-ladder correctness (A1 + A2 — owner, must-fix during build)
The +PB/+OT tag on each end-time button MUST be accurate (it's money):
- **Use UNBOOKED payback, not raw debt.** Today `sc_end` (attendance_ui.py:1941) uses
  `minutes_owed − minutes_paid` (raw) — it ignores payback already booked elsewhere, so the +PB part can
  be overstated → double-credit risk. Switch to `pb.unbooked(balance, pending_ext)` (the `_pb_remaining`
  logic — fresh at the picker).
- **Show BOTH components when an extension spans both.** Today `ot._ext_tag` returns `+OT` *or* `+PB`,
  never both. Fix it to render e.g. **"+3PB +1OT"** — 3 unbooked PB hours + 1 OT hour for a 4h extension
  over 3h unbooked debt. (Verified example from the owner.)

## Universal (owner)
- The **👁 who's-working impact** toggle belongs on **every** schedule-change card — staff AND seniors,
  at every approve/disapprove stage — not just these. (Most already have it; fill any gaps.)
- A1 and A2 first-step day pickers both extend to **30 days**.

## 8a conclusion (so we don't re-litigate)
- **8a-1 (stale "⏳ Awaiting approval" card):** REAL bug, **folded into this build** — the new A1/A2
  cards flip the proposer's awaiting card to the verdict in place (no orphan), built correctly from the
  start. Not a separate task.
- **8a-2 (incomplete "where did my day off go?"):** **OBSOLETED** by the restructure — A2 makes the
  day-off move explicit ("Off X · works Y"), so the confusion can't happen. No separate fix.

## Parked (come back after the structure) — ▶ REMIND THE OWNER when we reach 8b
- **Staff Changes (forever)** approval ladder.
- **8b leave-vs-commitment refund model** (situations #4–#9: confirm/cancel/refund + notify-all). The new
  A1/A2 plug straight into it later; building the structure first does not lose that work.
  **Concrete examples to walk through when we build it:**
  1. *Payback slot:* Chomreun owes 90 min, booked Wed 6–9pm. Requests full-day AL Wed. → Today: blocked.
     8b: "This AL cancels your payback Wed 6–9pm — 90 min returns to your debt to re-book. Confirm?"
  2. *OT-rest:* Davy banked 2h, booked it as rest (leave 2h early) Fri. Sick Fri. → 8b: auto-cancel the
     rest, **+2h back to the bank**, FYI to Davy + Supervisors.
  3. *Partial hours-AL:* Por has an after-shift payback Thu 6–8pm, takes a 9–11am hours-AL Thu (no time
     overlap). → 8b "just-cancel" option: still cancel + re-book (with the confirm) — simpler & safe.
  4. *Swap-work day:* Pisey swapped to work Mon (Heng's off). Requests AL Mon. → 8b: "This AL voids your
     swap with Heng (you off Mon / Heng off Thu) — Heng is told. Confirm?" → swap voided both ways.
  5. *Senior OT redefine:* Anan given +2h OT Tue, then takes AL Tue. → AL supersedes it (already happens);
     the **OT vanishes** (not worked) — the notice states the resulting hours.
  **Owner refinements (Jun 15) to apply when building 8b:**
  - **8b.1:** on any cancel of an older commitment, **details ALWAYS go to the Supervisors group** (on top
    of the involved parties). Supervisors are informed of every change/cancellation.
  - **8b.3 (hours-AL, refined):** for an *hours*-AL (not a full day) the staffer already knows they kept
    part of the day, so the message is RESULT-oriented: *"After this change ({details}), you will work
    only {resulting times} that day — confirm?"* And if the payback/OT slot is **genuinely still extra
    hours** outside the AL window, it may **stay** (not auto-cancelled) — show that in the resulting
    picture. (This is smarter than blunt "just cancel everything": keep real extra-hour PB/OT.)
  - **8b.4:** voiding a swap on a leave tells **the partner AND the Supervisors group** (Supervisors always
    informed of changes/cancellations).

## Build order
Phase 1 = A1 (mostly restructuring the existing `sc_*` flow). Phase 2 = A2 (new move primitive +
flow). HIGH-RISK (schedule/balance) → staging proof + second-opinion before "done". Re-walk after.
