# OT (Overtime) — settled design (session 31)

OT is being rebuilt on one idea: **OT = a sanctioned extension of a working day's shift edge** —
earlier start and/or later end. No separate "Now/Later/session" flows. The existing shift lifecycle
(check-in, verdict, checkout, points) does the work; OT just moves the edges.

## Entry (senior gives OT)
Give OT → **full staff list** → **date** → **start time**, where the picker only offers times that
*connect to the shift*:
- **Before-shift:** up to **4 hours** before shift-start (e.g. 3/4/5/6am for a 7am shift). Picking a
  start **auto-confirms** to `[start → shift-start]` (end pinned at shift-start; no gap). 4h cap is
  configurable.
- **After-shift:** start pinned at shift-end; pick the end (e.g. 5/6/7/8pm, 4h cap).
- **Mid-shift, same day (shift already running):** only the after-shift start; pick the end.
- **Day off:** **NOT OT** — redirect to a day-off swap / call-in. OT never invents a shift.

## Money / credit (banked at completion)
- **OT credit = in-zone time ∩ the UNION of sanctioned OT windows**, capped by the windows,
  **banked only at the day's checkout** (completion proof). Pro-rated to actual time.
- **Overlapping/duplicate grants never double-bank** — union (earliest pre-start, latest post-end),
  counted once.
- **Time worked is ALWAYS paid**, regardless of any penalty (the lawful anchor — never withhold pay
  for real labour).

## Points (the consent card promises these)
- **+10** if they arrive early to the OT start (beat it by > 5 min). Before-shift only (after-shift
  they're already at work).
- **−10** if **"very late"** = they completed **under HALF** the committed OT (a no-show *or* a
  5-minute cameo both land here). **The half-threshold is SECRET** — the card only says "very late"
  so they can't game it ("we showed up!" doesn't beat a −10, and they can't reverse-engineer 51%).
- Early can **never** combine with a no-show (kills the arrive-early-then-leave loophole).
- Repeats → a **documented warning** (the real "lawful" escalation; a single −10 stays recoverable
  vs a +10 early day).

## Two reference lines (don't merge them)
- **Lateness for the core shift** is measured against the **core shift start** — so an OT no-show
  (did the shift, skipped the early OT) reads as *on-time shift*, never "4h late."
- The **OT early bonus** is measured against the **OT start**.

## Staff-facing messages (EN done; KH = DRAFT — review in ChatGPT before go-live)

**Consent card (shown on the OT ask, before Yes/Can't):**
> 🕒 **OT offered — [window]**
> Why: [reason]
> Tap ✅ **Yes** and come work it — you're **always paid for the time you work**.
> 🌟 Come early → **+10 points**
> ⚠️ Come very late → **−10 points**
> [ ✅ Yes ] [ ❌ Can't ]

> 🕒 **ផ្តល់ OT — [window]**
> មូលហេតុ៖ [reason]
> ចុច ✅ **យល់ព្រម** ហើយមកធ្វើ — អ្នក**ទទួលបានប្រាក់តាមពេលដែលអ្នកបានធ្វើ** ជានិច្ច។
> 🌟 មកមុនម៉ោង → **+10 ពិន្ទុ**
> ⚠️ មកយឺតពេក → **−10 ពិន្ទុ**

**No-show notification (sent when the −10 triggers):**
> ⚠️ You accepted OT on [date] and didn't do it — recorded as very late (−10 points).
> ⚠️ អ្នកបានយល់ព្រម OT នៅ [date] ប៉ុន្តែមិនបានធ្វើ — កត់ត្រាជាការមកយឺតពេក (−10 ពិន្ទុ)។

> **ChatGPT review note:** confirm the Khmer reads naturally and matches the file's register (បងៗ /
> warm-firm). The English is owner-approved; the Khmer above is Claude's draft. Card promises +10/−10;
> the secret half-threshold and "time always paid" must NOT appear in any staff message.

## Build phases
1. **Pure logic** (`gm_bot/ot.py`) — credit (union/pro-rate/cap), no-show/points outcome, picker
   window math. Unit-tested, no DB. ← building first.
2. **DB + handlers** — merged Give-OT picker (`attendance_ui`), grant lifecycle (accept → completion),
   bank at checkout (`_handle_staff_location`), points events, no-show detection + notify. Additive
   schema only (`IF NOT EXISTS`), `is_test`-isolated.
3. **Test harness** — `/test` OT flow updated to the merged model; suite green.

Tunable constants live in `gm_bot/ot.py`: `NO_SHOW_RATIO=0.5`, `EARLY_GRACE_MIN=5`, `PTS_EARLY=10`,
`PTS_NO_SHOW=-10`, `MAX_PRE_SHIFT_HOURS=4`.
