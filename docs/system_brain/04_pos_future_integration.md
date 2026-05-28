# 04 — POS Future Integration

## Current state

There is no POS system yet. Orders are taken manually or via the Telegram ordering bots (retail and B2B). Cash handling, voids, discounts, and cashier reconciliation are done off-system.

This document captures what the POS integration should eventually look like and why it matters to the rest of the system — particularly hiring, staff assessment, and trial validation.

## Why POS connects to the people system

Cashier behavior is one of the highest-signal staff assessment dimensions:

- **Cash handling accuracy** — does the till balance at end of shift?
- **Void and discount patterns** — are discounts applied correctly? Are voids suspicious?
- **Speed under pressure** — service quality during peak hours
- **Honesty under low supervision** — does behavior change when management is not watching?

These are exactly the dimensions the quiz attempts to predict. Part A honesty section (A2), quiet-time ethic (A4), and commitment (A6) all contain questions whose real-world test is cashier behavior. A candidate who scores high on those sections should perform better on the POS. If they don't, that is a rubric calibration signal.

## The integration model (when built)

```
POS transaction log → ops_messages or dedicated pos_transactions table
→ nightly reconciliation job
→ per-staff cashier performance record
→ links to candidate_id via staff_identity_aliases
→ feeds into trial outcome and ongoing staff assessment
```

The POS system does not need to be custom-built. It needs to output a transaction log that the system can read. The minimum useful data per transaction:
- staff_id or cashier name (for alias resolution)
- timestamp
- amount
- payment method
- void flag
- discount applied (amount and reason)
- till reconciliation result

## What POS data would answer

| Question | Quiz prediction | POS validation |
|----------|----------------|----------------|
| Do they handle money honestly? | A2-Q13 (honesty tick) + C-Q8 (written) | Void pattern, discount pattern, till balance |
| Do they work properly when unsupervised? | A4 quiet-time section | Behavior consistency across shifts with/without manager present |
| Are they reliable at close-of-day? | A6 commitment section | Reconciliation completion, no walk-off |
| Do they learn from mistakes? | C-Q8 (written response) | Error rate over time |

This closes the loop that hiring alone cannot close: the quiz predicts, the trial tests briefly, but POS data over months gives real longitudinal evidence.

## Cashier-trust tier

Not all staff touch the POS. The integration should maintain a cashier-trust tier that is separate from salary tier:

- **Tier 0** — no POS access
- **Tier 1** — supervised POS (trainee)
- **Tier 2** — independent cashier
- **Tier 3** — can close and reconcile

Quiz risk profile should inform which tier a new hire enters at. A candidate with honesty=weak in their risk profile should start at Tier 1 regardless of role seniority.

## Salary privacy implications

POS reconciliation data may reveal effective hourly rates or tip income. Same privacy rules apply: cashier-level earnings visible to management; supervisor/manager-level earnings owner-only. The `filter_shareable_answers()` pattern should extend to any POS summary that goes to a group chat.

## Connection to Facebook Messenger

Historical customer orders came through Facebook Messenger (Sara Bologna account). Messenger export is pending. When imported, it will provide:
- Customer purchasing history
- Order patterns
- Complaint signals (late delivery, wrong item, etc.)

Customer complaints linked to specific staff members on specific shifts would be a high-value connection to the POS layer: if a complaint rate spikes during one cashier's shifts, that is a signal the system should surface.

## What to decide before building

1. Which POS system? (custom vs. third-party — e.g. iPos, iCash, or a simple Google Sheet export)
2. Does it integrate via API, file export, or Telegram photo of the reconciliation sheet?
3. Which staff roles have POS access?
4. What is the minimum viable data format?

The direction does not need to be decided before the hiring bot is live or before trials are running. But it should be decided before the first trial outcomes are recorded — because retroactively adding POS correlation to existing trial records is harder than building the link from the start.
