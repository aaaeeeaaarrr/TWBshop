# Attendance Go-Live Walk — refined, step-by-step (Step 3)

> Hand-walk in `/test` as the owner. Everything is gated behind `attendance_live=OFF` — nothing here
> touches a real staffer. Each part says **what to tap** and **what to check**. Stop and tell me the
> moment anything reads wrong; that's the whole point of the walk.

## SETUP (once, before you start)
1. `/testmode on` — confirm it replies that test mode is ON.
2. `/testkhmer on` — so every card shows full bilingual (you proof-read the Khmer too).
3. `/testreset` then `/testseed` — clean slate + fresh AL balances / debts seeded from real numbers.
4. `/teststatus` — sanity line: live=OFF, test=ON, seeded counts.
5. `/test` → the **persona picker** opens. You'll switch personas with **🎭 Switch persona** as you go.

Personas you'll use: a **SENIOR** (call her *Senior-A*), a **2nd senior** (*Senior-B*, for co-approval),
a **staffer** (*Staff*), and for the swap part a staffer who has a real **partner**.

---

## PART 1 — A1: Change time +OT (the "extend / retime a working day" path)
*Persona: Senior-A.*

1. **About Work → 🗓 Staff Changes (1 time) → ⏱ Change time +OT.**
2. **Pick the staffer** (Staff). → 30-day day list appears (her day-offs are hidden — only working days).
3. **Pick a day.** → start-time screen. Two ways from here:
   - **⏱ Normal times** = her normal shift, **no OT** → goes **straight to the reason** (no end menu).
     This is the quick "just put her on her normal shift that day" path.
   - **To give OT: do NOT tap Normal times.** Pick a **START** time → the **end ladder** appears.
4. On the **end ladder**, pick an end past her normal end. → the tag reads in **minutes**, combined,
   e.g. **`+1h15 PB +45m OT`** (not decimals, not two separate lines).
5. **Reason is now mandatory.** Before typing, try sending a **blank/space-only** message →
   - ✅ CHECK: it **refuses** ("a reason is required…") and keeps waiting — nothing is submitted.
   Now type a real reason → submit.
   - ✅ CHECK (1a co-approval): because A1 *changes* a shift, it does **NOT** go straight to Staff. You
     should land on **"⏳ Awaiting another senior"**. The other seniors get a **co-approve card**.
   - ✅ EXCEPTION to confirm later (step 1c below): extending the shift **running right now** skips
     co-approval — that's intended.
6. **🎭 Switch persona → Senior-B.** Open the co-approve card.
   - ✅ CHECK (NEW): the co-approve card shows the **reason** — **"Why · មូលហេតុ៖ {your reason}"** — so the
     2nd senior can see *why* before deciding.
   - ✅ CHECK (NEW): the co-approve card now has a **👁 Show who's working** toggle — tap it, confirm it
     shows coverage for the changed day, tap **🙈 Hide** to collapse it.
   - Tap **✅ Co-approve.**
   - ✅ CHECK: it advances to **Staff** as the awaiting-approval card.
   - ✅ CHECK (NEW): **every** senior's card (the one you tapped AND the others) now reads
     **"⏳ Co-approved — awaiting {staff}'s approval"**, the Co-approve buttons are **gone**, but the
     **👁 toggle stays** so they can still re-check coverage (no dead buttons, no watchdog alert).
7. **🎭 Switch persona → Staff.** Open the card → ✅ confirm it shows **"Why · មូលហេតុ"** too → **✅ Approve.**
   - ✅ CHECK: the proposer's old "⏳ Awaiting" card **flips in place** to the approved verdict (no stale
     duplicate left behind).
   - ✅ CHECK (NEW): **every senior's card** updates to the staffer's verdict —
     **"✅ {staff} approved"** (or **"❌ {staff} did not approve"** if you decline) — not just the
     proposer's. The 👁 toggle is still there.
   - ✅ CHECK (NEW): the Supervisors group notice now states the change **and the reason**
     ("…is now {time}. Reason · មូលហេតុ៖ {reason}").

---

## PART 2 — A2: Change day off (a REAL move, not a vague "change")
*Persona: Senior-A.*

1. **About Work → 🗓 Staff Changes (1 time) → 📅 Change day off.**
2. **Pick the staffer.** → **pick the day to be OFF (X)** — 30-day working days.
3. **Pick the comp work day (Y)** — offered from her real day-offs within ±7 of X (override-aware).
4. Set Y's hours via the same start→end ladder (⏱ Normal times, or extend into OT).
5. The reason prompt appears.
   - ✅ CHECK (NEW): the A2 reason prompt now has a **👁 Show who's working** toggle that shows **BOTH
     days** — who covers X (now off) **and** who works Y. Tap it to confirm, then 🙈 Hide.
   - ✅ CHECK (NEW): a blank reason is **refused** here too (same as Part 1).
   Type a reason → submit → co-approval (Senior-B) → Staff approves (same as Part 1).
   - ✅ CHECK (NEW): the **co-approve card** carries the **reason** + the both-days 👁 toggle; once one
     senior co-approves, **all** seniors' cards move to "⏳ awaiting {staff}" (buttons gone, toggle stays),
     and after the staffer decides they **all** show the verdict ("✅/❌ {staff} …").
   - ✅ CHECK (NEW): the **Supervisors FYI** states the reason too (and both dates).
   - ✅ CHECK (1c — the big one): **every** notice/card states **BOTH dates** — "OFF on **X**, works **Y**".
     No message should mention only one date. The card frames it **"Day-off move — OFF X, work Y"**.
6. The move is confirmed by the chain completing + the cards stating both dates (above). It will
   surface in *real attendance* on X (she isn't expected / no no-show) and Y (the bot checks her in
   for the chosen hours).
   - ⚠ NOTE: **My Schedule does NOT show one-off moves** — it's a static summary of the *recurring*
     pattern (weekly shift + weekly day-off weekday + balances), so "Day off · Tue" staying put there
     is correct. A one-off A2 move lives in `dayoff_overrides` (read by `resolve_day()`), not on that
     card. (If we ever want the staffer to see "this week: off X, working Y", that's a net-new
     My-Schedule line reading the overrides — not built.)

---

## PART 3 — 8b: taking leave on a day she's already committed to
*The new "leave-on-a-committed-day" model — the part most worth abusing.*

> 🎭 **TEST-MODE REALITY (read once — it changes how Parts 3–4 read).** In test mode **every** card
> (staff request, senior approval, partner, Supervisors FYI) routes to **YOU**, and the senior/staff
> role-checks are **bypassed**. So you switch persona (🎭) only to **INITIATE** an action *as* a
> specific person — e.g. be on the **Staff** persona to *request* AL (it's her balance), or a **Senior**
> to *propose*. To **approve/decide**, you do **NOT** switch — just tap the card that lands in your chat.
> Every balance check below: after you act, **ask me to DB-verify the row** (I read it back independently).

### 3a — AL on an A2 comp-work day → it COEXISTS and is CHARGED 1
1. On the **Staff** persona (the one you moved in Part 2, now working Y), **request AL on Y** (full day).
   Note her **AL balance before**.
2. **Tap the AL approval card** (no persona switch) → **✅ Approve**.
   - ✅ CHECK: AL is **charged 1 day** — *not 0* — even though Y was her original day-off; the move made
     it a real work day. (Ask me to verify `deducted_map[Y] == 1` and `al_left` dropped by 1.)
   - ✅ CHECK: the **Y redefine still stands** — the move is **not** cancelled; they **coexist**.
   - ✅ CHECK: this reminder fires to her **and** Supervisors (both dates):
     **"🔁 {name} took AL on {Y} — the day-off move STAYS: they're still OFF on {X}. Please re-arrange cover if needed."**

### 3b — AL on a payback / OT-rest slot → the slot is REFUNDED (no dead-end)
1. On **Staff**, book a **payback** slot on a clean day Z (About Me → Book payback). Note her **debt before**.
2. On **Staff**, **request AL on Z** → tap the approval card → **✅ Approve**.
   - ✅ CHECK: it does **NOT** block. The notice is a **refund**, not a block:
     **"↩ {name} took AL on {Z} — the payback slot ({mins}) is returned to their debt to re-book."**
     (For an **OT-rest** slot instead: **"…the OT-rest is cancelled, +{mins} back to their OT bank."**)
   - ✅ CHECK: her **payback debt / OT bank returns to exactly what it was before she booked the slot**
     (ask me to verify the debt/bank row).

### 3c — AL on a swap-work day → the swap is VOIDED for BOTH, both reminded
1. Set up a swap (the 🔁 Change-day-off / partner-swap flow) so **Staff** has a swapped **work** day W.
2. On **Staff**, **request AL on W** → tap the approval card → **✅ Approve**.
   - ✅ CHECK: it does **NOT** block. The whole swap is **voided** — both parties go back to their normal
     days — and **both** + Supervisors get:
     **"🔁 The day-off swap between {A} and {B} is off — {name} is now away. Both are back to their normal days; please arrange cover if needed."**
   - ✅ CHECK: ask me to verify all 4 `reason='swap'` overrides are gone and the swap row is `superseded`.

### 3d — the AL picker hides days she isn't there
1. On **Staff**, open the **AL** request day picker.
   - ✅ CHECK: it offers **only resolved-working** days — her plain day-offs are **not** listed (no more
     "0 AL on an off day"). A1/A2-moved working days **do** appear (she's working them).

---

## PART 4 — Step 8 resume: the collision backstop (F14)
*The point we paused at last walk. (`al_date_conflict` now blocks only an already-**approved** AL day or a
settled `'done'` redefine — everything else flows to the refund/void paths in Part 3, by design.)*

1. **Double-AL same day (request-side block).** Get an AL **approved** on day D. On **Staff**, try to
   request AL **again on D**.
   - ✅ CHECK: refused **at submit** —
     **"⚠ You already have approved leave or a scheduled shift change on: {D}. Pick other day(s)."**
2. **Redefine over your OWN approved AL (confirm-revoke — the silent-override killer).** With an approved
   AL on D, propose an **A1 change** on D for that same staffer, then approve it *as that staffer*.
   - ✅ CHECK: instead of a dead-end, the card asks an explicit confirm —
     **"⚠ You have approved AL on {D}. Approving this shift change ({win}) will CANCEL that leave (your AL
     is refunded) and schedule you to work. Confirm?"** with **✅ Yes — cancel my leave & work** /
     **✋ Keep my leave**.
   - Tap **✋ Keep** → the AL stands, the redefine is declined, and the proposing senior is told.
   - Tap **✅ Yes** (re-run) → the redefine takes and the AL is **refunded** (ask me to verify `al_left`
     went back up and the redefine is `approved`).
3. (Optional, fast) `/testclock +Nd` then `/testrun <job>` to watch a time-driven escalation in seconds.

---

## WRAP
1. `/audit` → must read **✅ clean** on the test rows. Paste me anything it flags.
2. When every ✅ above held: `/testreset`, tell me, and the only thing left is flipping
   `attendance_live` — which I will NOT do until you sign off zero-problems.

> Anything that reads wrong, screenshot it — I'll batch-fix the same way we did the last punch-list,
> then we re-walk only the parts that changed.
