# Operational Actions Ledger

> Every owner instruction that changes **real data** (payback · AL · balances · staff records ·
> payments) or is a concrete operational task gets ONE line here the moment it's given — Open or
> Done-with-proof. Chat is disposable; this file is truth. Claude reads this at session start (with
> Current Status) and, at the end of any turn where an instruction was given, states the open loops
> ("Open items: none" or the list). **Default: do real-data writes immediately, with independent
> before/after proof — never defer them.**

## Open (not yet done)

- _(none)_

## Done (with proof)

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
