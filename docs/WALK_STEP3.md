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
3. **Pick a day.** → start-time screen.
   - ✅ CHECK: there's a **⏱ Normal times** button. Tap it → it sets her real start+end and **skips
     straight to the end ladder** (no separate "change day" step — that's gone).
4. On the **end ladder**, pick an end past her normal end. → the tag should read in **minutes**, combined,
   e.g. **`+1h15 PB +45m OT`** (not decimals, not two separate lines).
5. Type a reason → submit.
   - ✅ CHECK (1a co-approval): because A1 *changes* a shift, it does **NOT** go straight to Staff. You
     should land on **"⏳ Awaiting another senior"**. The other seniors get a **co-approve card**.
   - ✅ EXCEPTION to confirm later (step 1c below): extending the shift **running right now** skips
     co-approval — that's intended.
6. **🎭 Switch persona → Senior-B.** Open the co-approve card → **✅ Approve.**
   - ✅ CHECK: now it advances to **Staff** as the awaiting-approval card.
7. **🎭 Switch persona → Staff.** Open the card → **✅ Approve.**
   - ✅ CHECK: the proposer's old "⏳ Awaiting" card **flips in place** to the approved verdict (no stale
     duplicate left behind).
   - ✅ CHECK: a Supervisors group notice fires stating the change.

---

## PART 2 — A2: Change day off (a REAL move, not a vague "change")
*Persona: Senior-A.*

1. **About Work → 🗓 Staff Changes (1 time) → 📅 Change day off.**
2. **Pick the staffer.** → **pick the day to be OFF (X)** — 30-day working days.
3. **Pick the comp work day (Y)** — offered from her real day-offs within ±7 of X (override-aware).
4. Set Y's hours via the same start→end ladder (⏱ Normal times, or extend into OT).
5. Type a reason → submit → co-approval (Senior-B) → Staff approves (same as Part 1).
   - ✅ CHECK (1c — the big one): **every** notice/card states **BOTH dates** — "OFF on **X**, works **Y**".
     No message should mention only one date. The card frames it **"Day-off move — OFF X, work Y"**.
6. After Staff approves, **verify the move actually landed**: as Staff, open **My Schedule** —
   - ✅ X now shows as a **day off**; Y now shows as a **working day** with the chosen hours.

---

## PART 3 — 8b: taking leave on a day she's already committed to
*This is the new "leave-on-a-committed-day" model — the part most worth abusing. Persona: Staff.*

### 3a — AL on an A2 comp-work day → it COEXISTS and is CHARGED 1
1. Using the A2 move from Part 2 (Staff now works Y), as **Staff request AL on Y** (full day).
2. **🎭 Senior-A → approve the AL.**
   - ✅ CHECK: the AL is **charged 1 day** (not 0 — even though Y was originally her day-off, the move
     made it a real work day). Look at her AL balance before/after.
   - ✅ CHECK: the **Y redefine still stands** (the move is NOT cancelled — they coexist).
   - ✅ CHECK: a reminder fires — **"took AL on Y, still OFF on X"** to her + Supervisors.

### 3b — AL on a payback / OT-rest slot → the slot is REFUNDED (no dead-end)
1. First make a slot: as **Staff**, book a **payback** slot on some day Z (My Schedule → Book payback).
2. As **Staff request AL on Z** → **Senior-A approve**.
   - ✅ CHECK: it does **NOT** block. The payback booking is **cancelled/refunded** and she gets a
     **refund notice** (for an OT-rest slot instead: the OT bank is refunded, "OT rest" reminder).
   - ✅ CHECK: her payback debt / OT bank returns to what it was before she booked the slot.

### 3c — AL on a swap-work day → the swap is VOIDED for BOTH, both reminded
1. Set up a swap (Part-2-style or the swap flow) so Staff has a swapped **work** day W.
2. As **Staff request AL on W** → **Senior-A approve**.
   - ✅ CHECK: it does **NOT** block. The **whole swap is voided** — both staffers go back to their
     original days — and **both** get a reminder.

### 3d — the AL picker hides days she isn't there
1. As **Staff**, open the **AL** request day picker.
   - ✅ CHECK: it only offers **resolved-working** days — her plain day-offs are **not** listed (no more
     "0 AL on an off day"). A1/A2-moved working days DO appear (because she's working them).

---

## PART 4 — Step 8 resume: the collision backstop (F14)
*The point we paused at last walk. Persona: Staff + Senior-A.*

1. Request AL on a day, get it **approved**. Then try to request AL **again on the same day**.
   - ✅ CHECK: the second request is **refused at submit** ("already booked / unavailable").
2. With an approved AL on a day, as Senior-A try to **redefine that same day** via A1.
   - ✅ CHECK: the senior is asked to **confirm it cancels her AL that day (AL refunded)** — an explicit
     confirm, not a silent override and not a dead-end. Decline → AL stands, proposer told.
3. (Optional, fast) `/testrun` the relevant job if you want to see a time-driven escalation.

---

## WRAP
1. `/audit` → must read **✅ clean** on the test rows. Paste me anything it flags.
2. When every ✅ above held: `/testreset`, tell me, and the only thing left is flipping
   `attendance_live` — which I will NOT do until you sign off zero-problems.

> Anything that reads wrong, screenshot it — I'll batch-fix the same way we did the last punch-list,
> then we re-walk only the parts that changed.
