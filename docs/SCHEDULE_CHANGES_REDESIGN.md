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
4. Set **Y's hours** start→end, top button **"⏱ Normal times"** (sometimes they cover a *different*
   window — e.g. what Vannary did — so custom hours must be allowed, not forced normal).
5. Reason → submit. **Staff approves**.
- Card: "Off **X** · works **Y {hours}**" + the **👁 who's-working** toggle on BOTH dates.
- Coverage: X −1 body, Y +1. A **senior** may decide to accept that shift (authority); the toggle makes
  it an informed call. (A *staffer* can't dent coverage solo → they use SWAP instead. Clean split.)

### A2 implementation (owner: my chosen approach unless you object)
- Writes a **shift_change redefine on Y** (carries Y's hours, drives attendance/settle) + a
  **dayoff_override `kind='off'` on X** (the new rest day). resolve_day already handles both kinds.
- **A2 comp day does NOT mint OT** — it's a fair *move*, normal-length shift (custom hours = retime to
  cover, same length). If genuine OT is wanted, that's **A1**. (Settle still clamps to real presence.)

## Universal (owner)
- The **👁 who's-working impact** toggle belongs on **every** schedule-change card — staff AND seniors,
  at every approve/disapprove stage — not just these. (Most already have it; fill any gaps.)
- A1 and A2 first-step day pickers both extend to **30 days**.

## Parked (come back after the structure)
- **Staff Changes (forever)** approval ladder.
- **8b leave-vs-commitment refund model** (situations #4–#9: confirm/cancel/refund + notify-all). The new
  A1/A2 plug straight into it later; building the structure first does not lose that work.

## Build order
Phase 1 = A1 (mostly restructuring the existing `sc_*` flow). Phase 2 = A2 (new move primitive +
flow). HIGH-RISK (schedule/balance) → staging proof + second-opinion before "done". Re-walk after.
