# Late Sick-Informing — locked design (2026-06-16)

> Owner-locked over a long design chat. This doc is the source of truth (written before building so it
> survives context compaction). Gated behind `attendance_live` like everything else.

## The problem
People reporting sick **right at / after shift start** is usually a lie — you know you're unwell before
then. We want to discourage the late *notice*, **without** discouraging actually coming in.

## The model (LOCKED)
- **Own-sick reported late → −15 "Late Informing" 🔻.** Recorded silently at filing.
  - **Window: 30 min.** Late = you open *Sick → I'm sick* with **< 30 min** until your shift starts
    (or after it started). Constant `LATE_SICK_OWN_MIN = 30`.
  - **Papers do NOT wipe the −15.** Papers prove you were sick, not that you couldn't tell us earlier.
  - **Callout at the sick screen (no points talk — just the nudge):**
    - before start: `⏰ Only {X} minutes before your shift starts — that's very late to let us know. You usually know you're unwell before this; please tell us as soon as you can next time 🤍`
    - already started: `⏰ Your shift has already started — that's very late to let us know. Please tell us as soon as you feel unwell next time 🤍`
  - **The −15 is taught at their NEXT check-in** (not while they're sick): a soft one-liner, then cleared.
    Auto-expires after 7 days (the −15 still stands in their points; only the courtesy message expires).
    `Quick note 🤍 last time you let us know you were sick very late — that's −15 Late Informing 🔻. Earlier next time keeps your points safe.`
- **Family-sick reported late → soft note, NO points.** Window `LATE_SICK_FAM_MIN = 10` (family things
  can be sudden — only flag the very-late, and never penalise).
  `⏰ Thanks for telling us 🤍 Just a note — that's quite late. We know family things can be sudden, but the earlier you let us know, the easier for us to cover.`
- **Coming in must NEVER cost more than staying home** (the incentive fix). The −15 is the SAME whether
  they come or not; a sick person who comes in is **NOT** charged late-arrival points on top — they only
  owe pay-back for the hours they actually missed (wiped by papers), which is less than a full-shift
  stay-home. So coming in is always the cheaper, better choice. → at check-in, if they have an **open
  own-sick case today**, waive the late-arrival points (come-in grace).

## Implementation
- `LATE_SICK_OWN_MIN = 30`, `LATE_SICK_FAM_MIN = 10`, `LATE_INFORM_PTS = 15`.
- `_sick_late_mins(p)` → minutes until today's shift start (None if not working today). Uses `resolve_day`.
- **Callout display:** prepend to `sick_me_screen` (own, 30) and the family-sick entry (10, soft).
- **−15 + deferred reminder:** in `_sickme_book` (the canonical own-sick filing = the "really can't come"
  path). Idempotent per day (`late_inform_done:<sid>:<date>`). Sets `late_inform_notice:<uid>` (delivered
  + cleared at next check-in; 7-day expiry).
- **Come-in grace:** in the check-in verdict — if `_open_sick_case(staff)` for today, force the late
  verdict to a clean on-time check-in (no late points). Pay-back for missed hours is the sick mechanic,
  unchanged.
- **Fix:** `sick_me_cant` display "within 3 days" → **"within 2 days"** (enforcement is
  `PAPERS_GRACE_DAYS = 2`; the 3 was a stray display bug the owner caught).

## KNOWN GAP (honest — pre-existing, flagged to owner)
The **"come try"** path (`att:sp:meo` → `sick_me_time`) is currently **UI-only** — in live it shows a
preview but does NOT book a provisional case or send the Supervisors FYI. So today the −15 fires on the
**"really can't come"** filing (the stay-home case = the primary "lie" target), and the come-in grace
keys on an open sick case. Fully covering "come try" needs that path built out (book the case + FYI)
first; then the −15/grace ride on it automatically. **Follow-up, not built here.**

## Gender (separate, same session)
Store gender on `staff_registry` (additive column via `init`), populated from the owner's roster.
Currently cosmetic (the Khmer is gender-neutral `ប្អូន`) — for records / future use. Unmatched names
reported to the owner, never guessed.
