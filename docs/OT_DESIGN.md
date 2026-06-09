# OT / Shift-Redefine — settled design (session 31, UNIFIED model)

The whole thing collapses to one idea: **a senior can REDEFINE a staffer's shift for a working day —
retime it, move it to another day, and/or extend it — and the staff approves.** OT is not a separate
object; it's an *emergent property*: **any approved shift longer than the person's normal shift length
has OT = the excess.** Everything else reuses the normal shift lifecycle (check-in, early/late verdict,
checkout, points, payback).

> This SUPERSEDES the earlier "OT shift-extension window / +10/−10 OT card" design. Length-based, not
> window-based. No OT-specific consent card or −10 — normal shift rules already cover every case.

## 1. Entry — the picker
Button: **"Give OT + Change Time"**. Ladder:
- **Choose staff** → **choose a work day** (do NOT show their day-offs in this list — they're not
  scheduled then).
- Then two stacked buttons: **Change day** (own ladder) · **Change time** (own ladder).

**Change time ladder:**
- **Start** buttons: 12am → 11:30pm, 30-min steps. *(48 buttons; could go hourly-then-:30 — minor.)*
- **End** buttons (wider, 2/row), shown relative to the chosen start + the normal length, e.g. start
  1pm, normal end 10pm: `10pm` · `11pm +1OT` · `12am +2OT` … The `+NOT` tag = hours beyond normal
  length. **If the staffer owes payback, the first extra hours clear it:** `11pm +1PB` · `12am +2PB`
  · `1am +1OT` · `2am +2OT` (extension pays down PB first, then banks OT — see §4).

**Change day ladder:** pick one of the **nearest 2 day-offs**, then the same time ladder. Moving to a
day off = the shift MOVES there (the original work-day becomes off): **same number of days, no extra
pay** unless also extended. Day-off windows are anchored to the person's **regular shift hours** (a
9pm–6am person gets a night window, never a 5am call), overnight-safe.

**Today edges:** future days are unconstrained. For **today**: start options only from **now forward**
(no past). If the staffer is **already mid-shift** → only the **extend-the-end** options (can't change
a start that happened or move them off today). If today's shift hasn't started → retime (start ≥ now)
+ extend.

## 2. Approval
**Every redefine needs the staff's approval** (they usually pre-discussed it). The card shows the
redefined shift exactly, e.g. *"Your shift: 1pm–12am (+2 OT). Approve?"* — Approve / Can't. A later
re-edit that removes/shrinks OT also needs approval/notice (they were counting on those hours).

## 3. Pay & attendance — it's just a (possibly longer/moved) normal shift
- **OT earned = hours actually worked beyond the normal shift LENGTH.** Worked length is the in-zone
  time; late/short naturally reduce it.
- **Late-to-start · leave-before-end · no-show = NORMAL payback / no-show**, measured against the
  *approved* `[start, end]`. **+10 early** vs the approved start. No OT-specific penalty — the normal
  rules already punish not doing the hours you agreed to.
- Worked examples (approved 1pm–12am, normal 1pm–10pm = 9h):

| Did | Worked | OT | Payback |
|---|---|---|---|
| full 1pm–12am | 11h | +2h | 0 |
| arrive 3pm (2h late) → 12am | 9h | 0 | 2h (late) |
| on time, leave 10pm (skip OT tail) | 9h | 0 | 2h (left early) |
| no-show | 0 | 0 | normal no-show |

- **Banked at completion** (the day's in-zone checkout). No checkout in-zone → nothing banks.

## 4. PB ↔ OT are one currency (time)
- PB = time owed; OT = time earned. **OT earned pays down PB FIRST, the remainder banks as OT.**
  3h OT + 2h PB → clears the debt, banks 1h. **My Schedule shows the net (1 OT).**
- The **extension ladder shows the split** (`+PB` then `+OT`) so the senior sees that extending first
  clears the debt.
- **Points stay SEPARATE.** Lateness already cost reputation points (−1/−2); netting the *time* must
  not erase that. Time nets; reputation doesn't. (OT can't buy back reliability.)
- **Agreed OT shields the PB ignore-ladder** (no auto-booking) — the OT will clear the debt. Holds
  only if the OT lands **before the PB deadline**; otherwise the ladder still runs.

## 5. Cancellation (no standalone "cancel OT" button)
OT vanishes only by **re-defining the shift**:
- **Explicit:** senior re-edits the day to no-OT (change time back to normal, or move to a no-OT day).
  Needs approval/notice; only valid **before the OT starts**.
- **Implicit:** the staff becomes **absent** that day (AL / sick / approved leave / day-off swap).
- Either path **re-exposes any PB the OT was shielding** (resume the ladder, restore the deadline).
- A *declined* proposal never took effect (not a cancellation).

## 6. Day-off payback (the standing ask — wire it)
The agreed but never-built "ONE day-off option" in `_payback_slot_keyboard`: a payback slot **within
the staff's regular shift hours** on their day off, need-ranked. **Cap = natural shift-length** (you
can't work more than your normal hours' worth in a day-off window; a big debt spreads across slots over
the 14-day deadline). Uses the shared `payback.dayoff_windows` primitive (overnight-safe).

## Full decision log (the long talk — nothing dropped)
**Live in this design:**
- Motivating case: **Vannary** moved a staffer to another **day & time** to cover a gap (AL staff out)
  — NOT a swap; the system had no home for it. That's what "change day / change time" serves.
- OT = redefine-a-shift (retime / move / extend); OT is **length beyond normal**. [§1, §3]
- Merged the old **Now/Later** split into one flow; **30-min** step picker. [§1]
- **7-day** work-day list, today first; day-offs **excluded** from that list; **change-day** targets
  the **nearest 2 day-offs**. [§1]
- **Today edges:** no past start; if **already mid-shift** → extend-the-end only. [§1]
- **Approval on every change** (usually pre-discussed). [§2]
- Pay = **time worked, always paid**; **banked at checkout** (completion). [§3]
- Normal **late / leave-early / no-show** rules vs the approved `[S,E]`; **+10 early** vs approved
  start. [§3]
- **PB ↔ OT one currency:** extension / earned-OT **pays down PB first**, **net** shown in My Schedule;
  **points stay separate** (reputation never nets); **agreed OT shields the PB ladder** while it lands
  before the PB deadline. [§4]
- **OT bank cap = 14h**; banked OT is spent as **REST via buyback** at the shift edges (come late /
  leave early) — existing `payback.takeback_windows`.
- **Cancellation** = re-edit (explicit; before start; needs approval/notice) OR **absence**
  (AL/sick/leave/swap); both **re-expose** any PB the OT was shielding. No standalone cancel. [§5]
- **Day-off payback:** ONE option within **regular shift hours**, **natural shift-length cap**;
  overnight-safe primitive (a 9pm–6am person gets a night window). [§6]
- **Swap stays SEPARATE** — bilateral exchange (two people, mutual consent) ≠ unilateral change-day
  (one person). They coexist, neither replaces the other.
- A **re-edit REPLACES** the day's shift definition (no stacking, no double-bank).

**Considered, then SUPERSEDED (kept so they're not re-litigated or re-added):**
- The OT-specific consent card with **+10 / −10 "very late"** and the **secret half-completion
  threshold** → replaced by "it's a normal shift," so normal late/no-show rules cover it. (The +10
  early survives as the normal early bonus.)
- The **owner reject / silence-is-approval veto window** → replaced by **staff approval** +
  re-edit-before-start.
- **Window-based** OT credit (time outside the normal window) → replaced by **length-based** (worked
  beyond normal length), because a *moved* shift broke the window idea.
- The **5-min cameo** and **arrive-early-then-leave** exploits → now caught by normal no-show /
  leave-early rules (5 min of an 11h shift = a normal no-show/payback); no special threshold needed.
- Banking **at accept** (the original "leave early keep OT pay" bug) and **Later-OT-never-banks** →
  replaced by **bank-at-checkout** for everything.

## Build phases
1. ✅ Pure logic foundations: `payback.dayoff_*` (done), and `ot.py` reworked **length-based + PB
   split/net + end-tag ladder** (this phase).
2. DB + grant/shift-redefine lifecycle (additive schema, `is_test`), approval card, bank-at-checkout,
   OT→PB netting, the shield.
3. The redefine picker UI in `attendance_ui` (staff→day→change-day/time ladders, today-edges, tags).
4. Day-off payback wiring into `_payback_slot_keyboard`.
5. Test harness `/test` updated; suite green.

## Staff-facing messages (EN owner-approved-ish; KH = DRAFT — review in ChatGPT)
**Shift-redefine approval card:**
> 🕒 **Shift change — [day]: [start]–[end][ (+N OT)]**
> [reason]
> You're paid for the time you work; come early → +10 points; normal late/no-show rules apply.
> [ ✅ Approve ] [ ❌ Can't ]

> 🕒 **ប្តូរវេន — [day]៖ [start]–[end][ (+N OT)]**
> [reason]
> អ្នកទទួលបានប្រាក់តាមពេលដែលអ្នកធ្វើ; មកមុន → +10 ពិន្ទុ; ច្បាប់យឺត/អវត្តមានធម្មតាអនុវត្ត។
> [ ✅ យល់ព្រម ] [ ❌ មិនអាច ]

Tunables in `gm_bot/ot.py`: `OT_STEP_MIN`, `MAX_EXTRA_HOURS`, plus bank cap (14h) in the existing block.
