# Attendance Go-Live Checklist

> The single tracked list for flipping `attendance_live`. Updated as items close. Companion to
> `ATTENDANCE_SYSTEM_DETAILED.md` (the full spec). Everything below is gated OFF until the flip.

## A. Built & shipped this session (✅ done, live on server, gated OFF)
- ✅ **OT / shift-redefine** end-to-end: propose → staff approve → attendance uses redefined times →
  checkout banks OT (clamped to the approved window) → buyback offer. Overnight-safe (right date).
- ✅ **Shield** — an approved upcoming OT pauses the payback ignore-ladder before its deadline.
- ✅ **Auto-checkout** — live share still in-zone at shift end closes silently + thanks them; detects
  a stopped share so it can't be gamed.
- ✅ **My Schedule** — `Payback debt: 5h (4h booked)` + `OT bank: Xh (Yh upcoming)`, no double-count.
- ✅ **Khmer batch** wired (ChatGPT pass) + `+10 points ⭐` convention; coverage label `ពេលនោះ`.
- ✅ **Owner tools:** `/pb` (who owes pay-back + booked), `/commands` (full help list).
- ✅ **Group-redirect** — Supervisors group only, rotating zero-API wording, tags the sender (uid-safe).
- ✅ **`/test` harness:** simulate-checkout, test clock (`/testclock`), job triggers (`/testrun`).
- ✅ **Guard tuning** (dev-machine only): allow our own app-bot restarts; don't scan commit-message text.

## B. To wire/finish before the flip (⏳)
1. ✅ **Summary/digest SOURCE switch — DONE (split digest).** When `attendance_live`, the weekly digest
   is now Brain-computed from the button tables (`gm_weekly_attendance_facts`): exact time-ledger
   ("staff owe Xh · shop owes Yh"), this week's late/no-show/AL/special counts, open-debt list, and
   `frequency.detect` pattern flags — all deterministic, Brain never miscounts. Opus 4.8
   (`narrate_attendance_week`) then writes ONLY the narrative over the verbatim reasons (told never to
   recount). The pre-live AI digest stays as the fallback. The owner walks it via `/testrun` once seeded.
2. ✅ **Khmer proof-read tooling — DONE (`/testkhmer on|off`).** Test mode stripped Khmer→English on
   the `_att_send`-routed bodies (approval cards, thank-yous, group notices); the dry-runs and nav
   screens were always bilingual. `/testkhmer on` keeps the routed bodies bilingual too, so EVERYTHING
   shows Khmer for proof-reading. The proof-read walk itself is part of B3.
3. ⏳ **Owner role-play sign-off** — walk every flow as each persona + every `/testrun` job; tweak any
   wording. **Then run `/audit`** — it cross-checks every input → stored result over the TEST rows
   (AL deducted right, payback math, OT banked ≤ cap, sessions sane, no-show vs check-in, bookings,
   swaps, staff schedule sanity). ✅ clean = the role-play actually produced lawful data; ❌ = a
   paste-to-Claude problem list. Then `/testreset`. (After live, `/audit` checks the real rows —
   run it whenever you want assurance. First real-data run 2026-06-11: CLEAN.)
4. ✅ **Points ACTIVATED (owner, 2026-06-11)** with the catalogued values: early +10 · late
   informed −1/min · late uninformed −2/min · no-show −2/shift-min · return-after-doctor +15 ·
   OT no-show −30 · short-notice AL −0.1/affected-min. Found+fixed at activation: the verdict
   charged EVERYONE late_uninformed (placeholder) — now reads the declare flag; short-notice AL
   was displayed but never recorded — now recorded at approval. Also built: the AL-today gate
   (shift started + no check-in → no AL-today button; kills no-show laundering).

## C. The flip
1. Owner confirms role-play is clean → `/testreset` (wipe test rows) → `/teststatus` shows zero.
2. Brief staff; everyone has pressed Start (done 33/33).
3. Set `attendance_live='true'`. Live-location requirement waits until the owner has explained it.

## D. Standing (not attendance, but on the books)
- 🔒 **Bedrock delta 2** — owner OS-locks the global guard files (elevated shell).
- ⏰ **Staging Postgres** by 2026-06-30 — get the prod DB credential out of dev.
- 🔁 **Deploy discipline** — quiet-window · batched · single-service restarts, always verify after.
  Full rule in `CLAUDE.md` → "Deploy Discipline". OT-banking is crash-safe (atomic claim); keep new
  balance-moving paths idempotent (status flips FIRST). `TimeoutStopSec=15` set on all `twbshop-*` units.

---
### Open question for the digest-source item (B1)
- When live, **replace** the AI digest with the structured one, or **show both** (structured facts +
  AI's softer pattern notes)?
- Any **other** GM summaries beyond the weekly digest that should switch source? (daily report
  watchdogs and the receipt/finance reports read different systems and likely stay as-is.)
