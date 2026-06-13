# State-Integrity Laws — universal, project-agnostic

> **TRIPWIRE.** Writing or changing any code that moves a **balance or persistent state** — leave days,
> debt, an OT bank, points, a booking, a status, a claimed resource — STOP and apply these laws first.
> Nothing here is about bakeries or Telegram; it's about any system that holds a number or a state a
> human depends on. Companion to `docs/STATEFUL_MENU_PATTERNS.md` (that one is UI/menu integrity; this
> one is DATA integrity). Both are meant to be universal — the project is only the worked example.

The origin: the AL-deduction bug (Jun 2026) — approving leave deducted **nothing** because the effect
was spread across a no-op + a daily job + a stale-balance read; fractional leave was free; staff could
over-book. The cure the owner chose — **"just deduct, and refund on cancel"** — *is* Law S1.

---

## S1 — Reversible by construction (apply once, reverse with one clean inverse)
A committed state change is **applied in exactly ONE place** and **reversed by exactly ONE clean
inverse**: `deduct ↔ refund` · `claim ↔ release` · `earn ↔ spend` · `set ↔ clear` · `add ↔ remove`.
- **Never reconstruct** the effect from scattered steps, background jobs, or "computed later" reads —
  if the truth lives in three places, it's wrong in at least one.
- **Every forward operation that a human can undo MUST have its inverse wired at the same time** — a
  cancel that doesn't refund, an approval that doesn't deduct, a booking that doesn't release are all
  half-laws that drift into silent wrongness.
- **Prefer "commit now + reverse on undo" over "defer the effect"** — deferring (charge it later, when
  the date passes…) splits the truth between "what's shown" and "what's real," which then needs a
  second correction everywhere it's read (the message, the over-booking gate, the audit). Two clean
  operations beat a million compensating reads. (Owner, Jun 13: *"just 2 things — deduct + refund —
  easier, and it eliminates overbooking.")*

## S2 — Idempotent / apply-once
A forward operation must apply **exactly once** even if the trigger fires twice (double-tap, retry,
crash-redelivery, a job re-run). Flip the gating status **FIRST**, before the balance moves, and make
the move conditional on that flip — so a second attempt finds nothing to do. (Already live here:
OT-banking's atomic `shift_change_claim_settle`; the AL deducted-days marker is what makes the daily
job idempotent.)

## S3 — Atomic claim-or-reject for a shared resource
When two actors might commit mutually-exclusive things to one resource (a staff-date, a seat, a slot),
the claim and the commit happen in **one transaction** that either wins or is cleanly refused — a
read-then-write check across separate transactions races. Use a unique constraint or a conditional
`UPDATE … WHERE … RETURNING` (compare-and-swap), not a check followed by a hopeful write. First commit
wins; the rest get an honest "no longer available" + (where a human should override) an explicit,
balance-aware override. (This is the F14 attendance guard's required shape.)

## S4 — The number you SHOW is the number that's TRUE
A balance displayed to a human, and the gate that guards it (e.g. "can you afford this?"), must read
the **same source** the real deduction moves. If "available" is computed differently from "deducted,"
they drift, and someone is misinformed or over-committed. (S1 makes this automatic; deferral breaks it.)

---

## Pre-ship checklist (run before shipping balance/state code)
- [ ] Does every forward op (deduct/claim/book/set) have its **inverse** wired in the same change? → **S1**
- [ ] Is the effect in **ONE** place, or reconstructed across job + read + write? → **S1**
- [ ] Does a double-tap / retry / job re-run apply it **twice**? Status flipped first? → **S2**
- [ ] Can two actors commit conflicting things to one resource without an **atomic** claim? → **S3**
- [ ] Does the **shown** balance and the **gate** read the same source as the real move? → **S4**
- [ ] HIGH-RISK (money/leave/payroll/staff records): real before/after proof on a real row, ideally on
      a **staging DB**, plus a second-opinion pass, before it's called done.

## Worked example — TWBshop attendance (status)
- **AL deduction → S1:** owner chose deduct-at-approval + refund-on-cancel (Option i). Build PENDING
  (HIGH-RISK; do on staging w/ proof). Today's bug: deferred + scattered (the anti-pattern). See
  `docs/ACTIONS_LEDGER.md`.
- **Points on a cancelled request → S1 gap:** short-notice-AL penalty points are applied at approval
  but **not reversed** when the AL is cancelled — a forward op with no inverse. To fix with the AL work.
- **Day-off swap override → S1 gap:** `dayoff_set_override` on approve has **no clean removal** on
  swap-undo. To fix with the AL work.
- **OT bank (add/spend), payback (add/credit) → S1 satisfied.** Clean pairs.
- **F14 cross-request guard → S2 + S3** (atomic claim; idempotent). Build PENDING on the corrected AL base.
