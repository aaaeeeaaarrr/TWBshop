# Attendance Test-Walk Guide — every flow, what to expect, what's easy to miss

> For the owner's `/test` role-play before go-live. State right now: `attendance_live=OFF` (real staff
> untouched — only YOU get messages), `attendance_test_mode=ON`. Everything you do is `is_test`-tagged;
> **real balances are never moved.** Deployed code = the new unified schedule model (supersessions +
> notify-all + F14). Work through the sections; tick the "easy to miss" lines — those are the ones that
> bite. When done → `/audit` → `/testreset`.

---

## 0. SETUP (run these first, in order)
| Command | What it does | Expect |
|---|---|---|
| `/teststatus` | shows test state | confirms `test_mode=ON`, the pretend-clock, khmer flag |
| `/testkhmer on` | show FULL bilingual in your previews | so you can proof-read the Khmer that staff will see |
| `/testseed` | seeds test staff/shifts/debts so flows have data | "seeded … rows" |
| `/testclock +0d` or e.g. `tomorrow 06:00` | set a pretend "now" (only in test) | lets you reach time-gated steps (check-in window, nudges) |
| `/test` | opens the role-play shell → **persona picker** | pick which staffer you ARE; then their menu + the 7 dry-runs |

Two ways to test, use both:
- **Dry-runs (1–7):** canned previews of *every message* in a flow, in order — fast read-through to check wording/Khmer. No state changes.
- **Live role-play:** pick a persona → drive their real menu → real `is_test` rows move (a real, reversible rehearsal). This is where you catch behavior, not just wording.

**Reset anytime:** `/testreset` wipes all `is_test` rows. `/testclock off` returns to real time.

---

## 1. THE MENU TREE (what a staffer sees — your map)
```
Main menu (they get this on any message once live)
├─ 📍 Check in
├─ 🕘 Late
├─ 🧰 About Work        (rules for all; Give-OT / change-shift inside = seniors)
└─ 👤 About Me
   ├─ 📅 Book pay-back time   (only shows if they owe time)
   ├─ 🏖 Annual Leave (AL)
   ├─ 🕊 Special Leave        → Sick (Me / child / spouse / parent) · Marriage · Family death · Wife birth
   ├─ 🔁 Change day off       (swap with a partner)
   ├─ ⏱ OT
   └─ 📋 My schedule          (incl. ✕ Cancel AL)
```

---

## 2. CHECK-IN / CHECK-OUT  (Dry-run 1)
**Do:** Check in → share location (or use the `/test` check-in simulator buttons).
**Expect:**
- Prompts fire at the shift edges (T−10 / T0 / T+5) — needs the test clock at ~shift start.
- On-time → a clean verdict; late → lateness measured **against the redefined start** if a shift-change applies that day.
- Checkout: manual (share→out) AND silent **auto-checkout** at shift end if the live share stayed on & in-zone → settles OT + banks.
- Every successful checkout sends the warm `Checked out ✓ … 🤍` (KH `…ល្អៗ`).
**Easy to miss:** the verdict uses the **redefined** times if a Give-OT/shift-change was approved that day; queued check-ins are judged by the staffer's **send time**, not bot processing time (a deploy blip can't mark anyone late).

## 3. LATE  (Dry-run 2)
**Do:** Late → pick how many minutes.
**Expect:** declaring late the MOMENT you pick the minutes informs Supervisors and splits points (before the declaration = −2/min, after = −1/min → **declaring is visibly cheaper**); a typed reason ATTACHES to the existing record (doesn't create a second). Missed time becomes **pay-back**.
**Easy to miss:** the points SPLIT shown in the sim; the Supervisors heads-up fires on minute-pick even with no reason yet.

## 4. ANNUAL LEAVE (AL)  (Dry-run 3) — HIGH-RISK, watch balances
**Do:** About Me → Annual Leave → pick day(s) **or** hours → (👁 toggle to see who's working) → type reason → senior ✅/❌.
**Expect:**
- **Deduct-at-approval:** balance drops the moment a senior approves (days AND fractional hours). The approval card and the over-balance gate read the **same** balance.
- Over-balance → YOU (the staffer) get "⚠ you only have X — pick smaller", request NOT submitted.
- Senior ❌ → act-first, then it asks the senior for a one-line reason that's relayed to the staffer.
- Supervisors group gets the approved notice (with back-at-work date / hours window).
- Reason prompt **edits in place** into the staffer's own "⏳ Awaiting approval" card, with the 👁 coverage toggle persisting through pending→approved/rejected.
**Easy to miss:** check the balance **before and after** (it should move exactly once); hours-AL shows the **actual AL amount** ("…9pm–12am = 0.3 AL"), day-offs excluded; the bilingual "AL" wording (we unified to bare `AL`, refund reads `ដាក់ត្រឡប់ចូលវិញ`).

## 5. CANCEL AL  (My schedule → ✕ Cancel AL)
**Do:** My schedule → ✕ Cancel AL → pick a day → "Are you sure?" → confirm.
**Expect:** the **exact frozen amount** returns to balance (1 day, or `%g AL` for hours, or "no AL — this day costs none" for a day-off day). Forward short-notice points reverse too.
**Easy to miss:** a day that already started → "too late to cancel" toast; the refund amount equals what was deducted (not recomputed).

## 6. SPECIAL LEAVE — Sick  (Dry-run 4)
**Do:** Special Leave → Sick → Me / child / spouse / parent.
**Expect:**
- **Me:** "take medicine, come try, what time?" → picks an arrival → Supervisors preview; missed time = pay-back unless doctor papers arrive in 3 days (papers → real sick day, no pay-back/points/AL).
- **Family (child/spouse/parent):** AL-funded, one day at a time; nightly expectation-first nudge ("I hope your {relation} is better 🤍 coming tomorrow?") → "no" costs a typed reason that reaches Supervisors → books tomorrow (burns 1 of the 7-day family pool).
- **NEW (schedule model):** a sick day **supersedes** — if that day had a planned AL, the AL is **refunded** (sick never also burns AL); a senior shift-redefine that day stands down; both announced ("🔁 … is out sick …").
**Easy to miss:** the `{relation}` renders as a **Khmer noun** (child→កូន), never raw English; the 10/20-min silence nudges then auto-resolve at 30 ("no reason given — asked 3×"), reality still covered.

## 7. SPECIAL LEAVE — Marriage / Family death / Wife birth  (Dry-run 5)
**Do:** Special Leave → Marriage / Family death / Wife birth → pick dates.
**Expect:** AL-funded (never salary); death has 2 tiers; **NEW:** these **supersede** across their whole span (refund any planned AL on those days, stand down redefines, announce).
**Easy to miss:** the compassion wording (warmer KH); the span (multi-day) supersedes each day, not just day 1.

## 8. CHANGE DAY OFF (swap)  (Dry-run 6)
**Do:** Change day off → pick your off-day + a partner + their day → partner ✋ accept/decline → senior ✅.
**Expect:** partner asked FIRST, then seniors, same-week rule; both parties' cards carry the 👁 toggle showing BOTH affected days' coverage; decline relays the typed reason.
**Easy to miss:** **NEW** — if one party later goes away (sick/special), the swap is **voided**, both revert to normal days, and **both + Supervisors** are told ("🔁 the swap … is off — … now away"). The machine never auto-rearranges the partner (human re-covers).

## 9. OT / SHIFT-REDEFINE + GIVE-OT  (seniors; About Work or ⏱ OT)
**Do (senior persona):** About Work → Give OT / change a shift → pick staffer → work-day → change time **or** change day → start/end ladder (tags show +PB/+OT) → reason → staff approves.
**Expect:** OT is **emergent** = minutes worked beyond the normal shift length; one currency with payback (extension clears debt first, then banks); at checkout `_settle_redefined_shift` banks/credits, clamped to the approved window (early arrival earns points not OT; lingering past end banks nothing).
**Easy to miss:** payback **slots ARE shift-redefines** (a day-off slot = window with normal_len 0 → every worked minute credits); the **mid-shift "Extend the end"** path locks the start; banked OT can be **spent back as rest** (buyback offered after settle).

## 10. PAY-BACK BOOKING  (About Me → 📅 Book pay-back time — only if you owe)
**Do:** Book pay-back time → pick from the offered slots (the shop's neediest times within shift hours).
**Expect:** picker shows Debt / Booked list / "choose the times we need you most"; remaining-only (balance − pending), 15h/day cap; booking auto-creates an approved redefine; settle credits the debt and flips it 'done'.
**Easy to miss:** slots NEVER mint OT (capped); a stale/clashed slot → "that time isn't available — pick again".

## 11. THE F14 CONFLICTS + CONFIRM-REVOKE  (the new collision layer — walk deliberately)
These are the freshly-built ones most worth testing:
- **AL on a day that has a senior redefine** → AL approval **supersedes** the redefine automatically (away-over-work); senior + Supervisors told.
- **A payback/OT-rest slot or a swap-work day** still **BLOCKS** an AL approval (F14) → "❌ couldn't approve — …".
- **Approving your own redefine on a day you hold approved AL** → you get an explicit **CONFIRM card**: "⚠ approving cancels your AL that day (AL refunded) — confirm?" → ✅ revokes+refunds+schedules work, or ✋ keeps the leave (proposing senior told).
- **Submitting** a day already committed → request-side block "⚠ you already have approved leave/shift change on … pick other day(s)".
**Easy to miss:** the AL is **refunded** when a redefine revokes it (not lost); two AL on the same day can NEVER both deduct (race-proof).

## 12. MENU-LAW BEHAVIORS  (tap the edges, not just the happy path)
- **Expired button** → fresh "❗ NOT CONFIRMED — TRY AGAIN" push + 📋 Open menu, stale card removed (not a silent dead tap).
- **✕ Cancel** on an armed prompt → disarms (a later stray "thank you bong" can't become a filed request).
- **Voice note / photo** sent where a typed reason is expected → "🎤 I can't read that — type one line", prompt stays armed.
- **Supersession honesty** → starting a 2nd reason prompt edits the 1st to "↩ Replaced — answer the newer prompt below".
- **Typing mid-selection** ("and also the 24th") → "you're mid-pick, tap ✅ Done / ✕ Cancel" (doesn't wipe your picks).
- **Maintenance toast** → with `attendance_live` OFF, a non-owner tap shows "🔧 paused for maintenance" (you won't see this as owner — it's the staff path).

## 13. CROSS-CUTTING — check on EVERY flow (the most-missed)
- **Bilingual:** every staff-facing line is EN + KH; with `/testkhmer on` you see both — proof-read the KH (esp. the new AL/refund/supersede strings SM1–SM12).
- **Supervisors group notices:** every CONFIRMED outcome should land in the group (approved AL, swap, OT rest, supersessions); rejections/completions are deliberately silent. Verify the group preview appears.
- **Balance before/after:** for any AL/payback/OT step, note the number before and after — it must move **exactly once**, in the right direction.
- **is_test isolation:** real balances must be **untouched** — `/audit` (test mode) audits your role-play rows; real rows are separate.
- **Points:** +10 early ⭐ (with the star), −1/−2 late split, −2/min no-show, +15 doctor-return, short-notice AL −0.1/min; check the right one fires.
- **👁 Show/Hide who's working** toggle works on every card state (pre-reason, awaiting, approved, rejected).

## 14. THE SCHEDULED JOBS  (`/testrun <job>` — fire on demand against the test clock)
| `/testrun` | fires | walk it to see |
|---|---|---|
| `checkin` | the scheduler tick (incl. auto-checkout) | prompts + silent checkout + banking |
| `noshow` | the no-show sweep | no-show points, and that AL/sick days are NOT mis-flagged |
| `ladder` | payback warn / auto-book | day-3/4 escalation (set `/testclock +3d` first) |
| `booking` | booking reminder | the reminder message |
| `sickdeadline` | sick papers deadline | papers-not-arrived → becomes pay-back |
**Easy to miss:** set `/testclock` to the right pretend-time BEFORE `/testrun`, or the job has nothing due.

## 15. FINISH
1. `/audit` → expect **✅ clean** (it audits your test rows in test mode). If it lists problems, paste them to Claude.
2. `/testreset` → wipes all `is_test` rows (real data was never touched).
3. `/testclock off` · `/testkhmer off` if you want.
4. Go-live (separate, deliberate): `/testmode off` → flip `attendance_live` only after sign-off + staff briefed.

---

## EASY-TO-MISS CHECKLIST (the ones that bite)
- [ ] Balance moved **exactly once** on every AL/payback/OT action (not zero, not twice).
- [ ] The **Supervisors group** got every confirmed outcome (and nothing on rejections/completions).
- [ ] Khmer reads naturally on the NEW strings (AL / refund `ដាក់ត្រឡប់ចូលវិញ` / supersede 🔁 / relation nouns).
- [ ] A **sick day refunded** a planned AL (didn't double-charge); special leave did the same across its span.
- [ ] The **confirm-revoke** card appeared (not a dead-end) when approving a redefine over your own AL; AL was refunded.
- [ ] Expired/dead taps → a fresh "TRY AGAIN" push, never a silent nothing.
- [ ] Points showed the **late split** (declaring cheaper) and the ⭐ on positives.
- [ ] `/audit` clean at the end; `/testreset` actually emptied the test rows.
- [ ] Anything that ended in a button doing **nothing with no message** → note it (that's a bug).
