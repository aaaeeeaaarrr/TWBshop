# Advisor Brief — lean/unify the operating standard (without weakening precision)

> Hand this to the advisors **together with `docs/GOVERNANCE_INVENTORY.md`** (the evidence). This file
> is the framing + the questions; the inventory is the cited stock-take of every rule and whether it
> actually fires. Paste both.

## Who you are in this
You are the **advisor lane**. The owner runs an AI coding agent ("the builder") that builds + proves +
deploys in the repo and OBEYS the standing rules. The builder must NOT design its own constitution —
that creates a second law-review track (a "silent parallel truth"). **You design the lean standard from
the evidence; the owner ratifies; the builder then installs the ratified result + wires whatever
surfacing is agreed.** Your output is a recommended lean set + reasoning — not code.

## The goal (precise)
Make the rule set **leaner and more universal WITHOUT losing precision**. A smaller rule count is NOT
the goal; **no precision loss** is the goal. Lean the *redundancies*; never force-merge distinct
invariants to hit a smaller number.

## Why this exists (the failure that triggered it)
Two repeated failures, both **process-enforcement**, not capability:
1. The agent asked the owner to re-decide things the design docs already settled (didn't retrieve first).
2. A "whole-system re-sweep" rule existed — **freshly written in the same session** — and still didn't
   fire until the owner prompted it. So **a prose rule that says "do X proactively" does not reliably
   self-trigger, even one just written.**
The lesson: judgment rules rot unless they (a) collapse rather than accumulate, and (b) fire at a named
boundary as a *populated artifact*, not a checkbox.

## Hard constraints (do not violate)
- **Don't force-merge the data invariants.** In the inventory, S1 (reversible/transactional), S2
  (idempotent), S3 (atomic claim), S5 (multi-feature resolver) and "real-path" (epistemic) are
  DIFFERENT load points. Merging them to look lean is the lossy move. Lean redundancies only.
- **"Don't lean if it costs precision"** — the owner's standing line. Preserve by-construction safety,
  anti-fraud, permissions, data integrity, auditability, no-behavior-fork, real-path proof.
- **A judgment cannot be verified by a hook** — only *surfaced*. The mechanical guards (dangerous
  command / secret shape) are real; the closing/sweep/retrieve gates can only be forced to *appear* as a
  populated report. So the lever for those is "mandatory populated section," not "a new wire."
- **Persistence:** for every surviving rule, say WHERE it lives so it can't rot — global `CLAUDE.md`,
  project `CLAUDE.md`, a hook, `/audit`, a test, or a runbook/SOP (NOT a chat turn).

## The questions to answer (candidate collapses — from the inventory)
1. **Escalation stated 3×** (HtB "only stop if blocked" + Std R6 "don't ask unless needed" + Bedrock
   cadence). Collapse into one **"retrieve-before-asking / stop-condition"** rule? What's its trigger?
2. **Closing gates stated 4×** (Std R4 DONE-CLAIM GATE + Std R6 evidence block + Menu Law 9 "≥3 tests
   before the walk" + walk-readiness). Collapse into ONE **closing gate** with walk-readiness as its
   strictest subset? Does it belong as a REQUIRED line in Rule 6's evidence block — i.e. is it "the
   definition of done" for SHIPPABLE/HIGH-RISK?
3. **Cover-every-branch:** Std R5 ⊇ Menu Law 9 (Law 9 is just R5 for menus). Collapse Law 9 into R5?
4. **Supersession/exclusivity:** data-layer S5 ↔ UI Menu Laws 3 + 7 (S5 already calls itself the data
   twin). One principle stated at two layers, or keep deliberately separate? (Watch the force-merge rule.)
5. **Second-opinion pass** appears in 3 places (HtB + the S1–S5 checklist + the Standard). One home?
6. **Confirmation Gate** (Core R3) == key-decision "no silent AI guessing." Straight duplicate — drop one?
7. **Work-rhythm / SOPs** (Push · Pull · Deploy Discipline · New-Machine, etc.): should these LEAVE the
   constitution into a runbook/checklist (they're procedures, not laws)?
8. **Meta:** "collapse-don't-accumulate" is currently only in a memory note. Should it be a formal
   standing meta-rule?

## What to return
A recommended **lean standard**: the surviving rules (ideally a small set of invariants + a stop-condition
+ one closing gate + a meta-rule), each with **(kind · where it lives · what trigger makes it fire)**;
the collapses you endorse WITH a one-line precision-loss check each; and which items to demote to a
runbook. Flag anything you think the inventory mis-classified.

## Already settled — do not re-litigate
- **The tool switch (Codex vs the current agent).** Every fix in this whole effort is **portable to
  either tool** — so the observed failures are process-enforcement, not a capability gap. The tool
  decision is parked on its own; only raise it if you see a concrete capability one tool has that the
  other can't match. "It understands my mind better" is not supported by the evidence.
- The inventory is a **working artifact, not ratified doctrine.** Treat it as evidence.
