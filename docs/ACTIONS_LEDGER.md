# Operational Actions Ledger

> Every owner instruction that changes **real data** (payback · AL · balances · staff records ·
> payments) or is a concrete operational task gets ONE line here the moment it's given — Open or
> Done-with-proof. Chat is disposable; this file is truth. Claude reads this at session start (with
> Current Status) and, at the end of any turn where an instruction was given, states the open loops
> ("Open items: none" or the list). **Default: do real-data writes immediately, with independent
> before/after proof — never defer them.**

## Open (not yet done)

- **🛑 2026-06-13 (CRITICAL BALANCE BUG — found by Fable's pre-guard review, NOT yet fixed, awaiting
  owner decision): AL deduction is split-brained; HOURS-AL is never deducted at all.** `_al_finalize`
  flips the request to `status='approved'` (bot.py:2550) BEFORE computing `nw = staff_absent_dates()`
  (bot.py:2558), and `staff_absent_dates` returns ALL approved AL days for the staffer (database.py:3704)
  — so the request's own days are excluded as "already absent" → `al_day_count = 0` → `al_deduct(…, 0)`
  deducts NOTHING at approval. **Days-AL** is then charged only by the daily job `al_apply_due_deductions`
  as dates pass. **Hours-AL** (fractional, e.g. "9pm–12am = 0.3 AL") is charged by NEITHER (the job
  filters `kind='days'`, database.py:2818) → **fractional leave is currently FREE**. Side effects: the
  approval message shows the uncharged balance, and the request-time over-balance gate reads the unmoved
  `al_left` → staff can stack approved future AL beyond their balance. **DECISION NEEDED (owner):** which
  is the ONE canonical deduction path — (i) finalize deducts immediately (compute amount before the
  status flip; retire the daily job; update /audit), or (ii) the daily job deducts (extend it to hours-AL
  pro-rata; fix the message + gate to account for approved-but-undeducted). HIGH-RISK / auto-bedrock:
  fix with real-path before/after proof on a real row; ideally after the staging-DB lock. Blocks the F14
  guard (Stage 5b) — the guard's "each approved AL-day deducts once" invariant + override-refund are
  unspecifiable until exactly one thing charges.
  **→ OWNER DECISION (2026-06-13): Option (i) — DEDUCT-AT-APPROVAL + REFUND-ON-CANCEL.** Finalize
  computes the amount BEFORE the status flip and deducts (days AND hours); Cancel-AL refunds the same
  amount; retire/neuter the daily `al_apply_due_deductions` job; update `/audit` (`v_al`) to the
  deduct-at-approval model + cover hours-AL. Rationale (owner): "just 2 things, eliminates overbooking."
  Still HIGH-RISK/auto-bedrock: implement with real before/after proof on a real row, ideally after the
  staging-DB lock. Then build the F14 guard on top.
  **→ DESIGN REDONE (2026-06-13) after Fable red-team:** my first design (reorder + mark deducted_days
  + daily-job backstop) shipped 2 Criticals on paper (daily-job double-charge of excluded days;
  cancel double-refund/mint via stale buttons) + a crash window. **REPLACED** with a per-day
  `{date: amount}` map on the row + two atomic functions (`al_approve_and_deduct` /
  `al_cancel_and_refund`, each one CAS transaction) — fewer parts, mechanically auditable. Full build
  brief + the 5 must-hold invariants + my added checks → **`docs/AL_DEDUCTION_REDESIGN.md`**. Build on
  staging, then the F14 guard on the corrected base.

- **⏰ Jul 1 (AUTOMATED · MUTED · SELF-DESTRUCT — owner: no redundancy): Kimying full-split
  restore.** `_pay_restore_job` (daily 07:05 PP) restores 145/30 from her seeded `pay_restore:42`
  record once June passes, and DMs the owner. Do NOT mention in open-loops reports; act ONLY if no
  DM arrived by Jul 2. **Once fired & good: DELETE this entry entirely** — her state record is
  auto-cleared by the job itself, the job is GENERIC (serves every future hire — stays), and her
  proration history lives in Done below. Nothing Kimying-specific remains in code after that.

## Done (with proof)

- **2026-06-11 — dead `secretary.service` removed from the server.** The Personal project's bot
  unit (pointed at /root/Personal) was already stopped+disabled by the owner; the unit file was the
  last remnant — deleted + daemon-reload, verified gone ("could not be found"). No cron entries, no
  twbshop-code references existed. `/root/Personal` itself NOT touched (separate project decision).
- **2026-06-11 — Davy (id 26): payback cleared ("she paid").** Real debt #5 (60 min) + test mirror
  #45 credited → cleared. No attached bookings (checked first). Independent re-read: both open
  debts now None. (Rath explicitly NOT touched — owner's hypothetical only.)
- **2026-06-11 — Tyty (id 28): pay record corrected + included in /menu pay views.** salary 1500→
  1700 (stale), 1st stays 1700, 2nd 0, bonus 0 (owner: "only on the 1st, $1700, no bonus"). Views
  now include her (1st list only; zero-2nd staff skip the 2nd list). Verified fresh-process re-read.
- **2026-06-11 — Sun Kimying (id 42): June prorated + joined date.** Joined 2026-06-04 → 27/30
  payroll days → 144 prorated; 1st = 80%×144 = 115.20 → next 5/0 up = **120**; 2nd = 24 base +
  15 bonus (kept, not prorated) = **39** stored. joined_date set 2026-06-04. Verified fresh-process
  re-read. Full split restores ~Jul 1 (see Open).

- **2026-06-11 — cron daemon enabled on the server (the watchdog was never running).** The
  session-28 collection watchdog (`run_collection_watchdog.py`, crontab every 1 min) had NEVER
  executed: the cron daemon itself was `inactive`. `systemctl enable --now cron` → `active` +
  `enabled`; proof: the next minute's cron tick wrote `logs/watchdog.log` ("ok") on its own.
  ⏳ Owner-step pending: fire the alert path once (stop a bot briefly) to see the 🚨 DM arrive.

- **2026-06-11 — Chantrea (id 15): cleared ALL open payback.** Real debt id 2 (27 min) + test debt
  id 43 (27 min) → both `None`/cleared. Her AL untouched (2.0). Method: `payback_credit` of the full
  remaining balance. Verified by an independent fresh-process re-read.
- **2026-06-11 — Davy (id 26): −1.0 AL.** 15.0 → 14.0 (`al_deduct(26, 1.0)`, real). His 60-min
  payback (debt id 5) left untouched — not instructed. Verified by an independent fresh-process re-read.
  - *Note: both were instructed earlier in session 32 and dropped at the time; surfaced + executed when
    the owner re-checked. This ledger exists so that never recurs.*
