# Governance Inventory — WORKING ARTIFACT (not ratified doctrine)

> **STATUS: evidence for the parked LEAN/UNIFY advisor pass** (`docs/ACTIONS_LEDGER.md` → Parked →
> "ADVISOR REVIEW of the Bedrock/rule additions"). This is a READ-ONLY stock-take produced 2026-06-14.
> It changed **zero rules and zero code**. It is NOT the lean standard and must not be promoted to one
> by a later session — the lean set is decided by the owner + advisors, then installed. Its job is to
> show, with cited artifacts, **which rules exist, what KIND each is, and whether it actually FIRES** —
> so the advisor pass can lean/unify without weakening precision.
>
> Method (per the advisor preamble): every "enforced" claim names the **artifact + the trigger that
> makes it fire + whether that moment matches the risk**. A file existing ≠ enforced. No trigger = prose.

---

## 0. The honest ceiling (read first — it bounds everything below)
A **command/path pattern** or a **secret shape** can be matched by a hook and hard-blocked before it
runs. A **data invariant** can be checked after the fact by `/audit`. But a **judgment** ("did you
retrieve the decision before asking · prove the real path · sweep the whole system · is it walk-ready")
**cannot be verified by any hook** — there is nothing to pattern-match at the moment it matters. For
judgments the only available mechanism is to **force a populated artifact to appear** (a filled report,
not a ✓). So "make the missing parts mechanical" has a hard limit: the dangerous-command and secret
gates are fully mechanical; the closing/sweep/retrieve gates can be **surfaced, never auto-proven**.
This inventory can point at where a gate is prose-only; it cannot convert a judgment into a check.

---

## 1. Where the rules live (sources)
| Source | Holds | Loaded when |
|---|---|---|
| `~/.claude/CLAUDE.md` (global) | "How to Behave" (Bedrock cadence · second-opinion · simpler-path · scope-honesty · HIGH-RISK guard desc) + Real-Path Precision Standard (6 rules) + SOPs (Push/Pull/New-Machine/New-Project/Secrets/Large-Files/Automatic-Actions) | every session, all projects |
| project `CLAUDE.md` | FULL copy of the Standard + Core Architectural Rules 1–6 (Rule 5/6 = tripwires) + Deploy Discipline + Operational-Instructions/Ledger rule | every session, this project |
| `docs/STATE_INTEGRITY_LAWS.md` | S1–S5 (data integrity) — tripwire target of Core Rule 6 | on demand (when Rule 6 trips) |
| `docs/STATEFUL_MENU_PATTERNS.md` | Menu Laws 1–9 (UI integrity) + F1–F14 backlog — tripwire target of Core Rule 5 | on demand (when Rule 5 trips) |
| `docs/BEDROCK.md` | **Bedrock = Standards + Guards + Ratchet** + the "one principle" + the 5 deltas (see §7 — it is NOT just history; the Ratchet is the existing lean/remove policy) | on demand |
| machine-local memory (`~/.claude/.../memory/*.md`) | standing feedback rules (breadth-over-narrowness · precision/deploy · second-opinion · operational-instructions · owner-always-approves) — mostly already CODIFIED into `CLAUDE.md`; NOT in the repo, so advisors can't see them directly (see §7) | every session (this machine only) |

## 2. Mechanical enforcement reality (what actually FIRES)
| Artifact | Wired by / trigger | Fires on | Covers | Honest limit |
|---|---|---|---|---|
| `.claude/hooks/highrisk_guard.py` | **global** `~/.claude/settings.json` PreToolUse **and** project `.claude/settings.json` | Bash · PowerShell · Edit · Write · MultiEdit · NotebookEdit, **pre-action** | destructive SQL · DB migration · `rm -rf` · force/reset git · `systemctl stop/disable` + non-app restart · secret/session/guard writes via shell · KHQR/Bakong · payroll/salary/staff_registry keywords · ban/offboard · PATH writes to secrets.py/.env/.bootstrap_token/.claude settings+hooks/.session/config.py. **No override.** | denylist, never complete; the real prod-data lock is the staging-DB checkpoint (not yet done) |
| `.claude/hooks/secret_guard.py` | **global + project `.claude/settings.json`** (asymmetry CLOSED 2026-06-14 — was global-only) | written text (Write/Edit/MultiEdit) + staged diff on `git commit` + unpushed commits on `git push` | live secret shapes (keys/tokens/private-key/DB-URL-with-pw). **No override.** | denylist of key shapes is never complete; novel formats slip past |
| `.githooks/pre-push` (surfacing gate, 2026-06-14) | git pre-push, `core.hooksPath=.githooks` | when **code** is pushed (silent on docs-only) | PRINTS the DONE-CLAIM skeleton (retrieve-first · evidence · system-sweep · walk-ready) — a forcing function, NOT a verifier; always exit 0 | covers the push boundary only; a chat "done" with no push is unreachable by any hook (the ceiling); relies on the agent filling it truthfully |
| `gm_bot/audit.py` (`run_audit`) via `_auto_audit_job` (bot.py:4881) | daily **07:30 PP**, real rows, silent-when-clean + owner DM on problems; also on-demand `/audit` | **after the fact** | 20 validators: `v_payback · v_al · v_special · v_shift_changes · v_pb_overbook · v_sessions · v_ot_bank · v_noshow_vs_sessions · v_bookings · v_booking_redefine_pair · v_buybacks · v_sick · v_swaps · v_swap_exclusivity · v_exclusivity · v_one_active_redefine · v_late_points · v_al_same_day_gate · v_dead_taps · v_staff_sanity` | a **detector**, not a preventer — flags a broken invariant the morning after, doesn't stop the write |
| test suite (573, `tests/`) | dev / pre-push (manual) | when run | S2/S3 (atomic+race tests), menu Laws 2/3/4 (`test_multimenu.py`), shadow-import AST scan (`test_attendance_live_entry.py`), AL atomic (`test_al_atomic.py`/`test_al_step3.py`) | **no artifact forces it to run before push** — running it is discipline |

## 3. Rule inventory — KIND × ENFORCEMENT
Legend — KIND: **INV** invariant · **STOP** escalation/stop-condition · **GATE** check at a named
moment · **SOP** runbook step · **META** rule-about-rules. ENF: **MECH** auto-fires (artifact cited) ·
**SURF** surfaced (tripwire/checklist, needs judgment) · **PROSE** no artifact (fires only if remembered).

| Rule | KIND | ENF | Artifact + trigger (or "prose-only") |
|---|---|---|---|
| **Std R1** one real system / no behavior fork | INV | SURF/PROSE | `TWBSHOP_ENV` switch (structural) + highrisk_guard on prod-touching cmds; prod-cred-absence checkpoint NOT done |
| **Std R2** proof-not-echo (pushed≠live, written≠saved) | GATE | **PROSE** | nothing verifies an independent post-settlement read happened |
| **Std R3** files are truth | INV/SOP | MECH-ish | git history is the artifact; "persist as you go" is prose |
| **Std R4** every actor + **DONE-CLAIM GATE** (v2026-06-14-A) | GATE | **PROSE** | the populated report IS the mechanism; no hook surfaces it at the done-moment |
| **Std R5** cover every branch | INV | MECH(partial) | test suite is the artifact; not CI-gated. Menu Law 9 is its menu instance |
| **Std R6** report faithfully + closing evidence block (+ "don't ask unless needed") | GATE+STOP | **PROSE** | prose-only |
| **HtB** Bedrock cadence (lean default · auto-bedrock dangerous set · "WE SHOULD BEDROCK THIS") | STOP/META | SURF/PROSE | dangerous-set overlaps highrisk_guard patterns, but cadence itself is judgment |
| **HtB** second-opinion pass (high-stakes / standing / any rule edit) | GATE | **PROSE** | prose-only (was just run by hand on R4) |
| **HtB** simpler-path / scope-honesty / if-it-doesn't-work | INV/behav | PROSE | prose-only |
| **HtB** permissions · HIGH-RISK guard | — | MECH | `.claude/settings.json` + the two hooks (§2) |
| **Core R1** AI only via `shared/ai_client.py` | INV | PROSE | no grep/import test found enforcing it |
| **Core R2** build interface (stub) first | SOP | PROSE | prose-only |
| **Core R3** confirmation gate mandatory | GATE | MECH | enforced in bot flow code (the confirm step); **duplicates** key-decision "no silent AI guessing" |
| **Core R4** modular files | INV/style | PROSE | prose-only |
| **Core R5** stateful-menu TRIPWIRE → Menu Laws | INV | SURF | tripwire prose + `test_multimenu.py`, `/audit v_dead_taps/v_exclusivity/v_swap_exclusivity` |
| **Core R6** balance/state TRIPWIRE → S1–S5 | INV | SURF | tripwire prose + atomic CAS in code + `/audit` validators + AL atomic tests |
| **S1** reversible-by-construction | INV | MECH(partial) | pairing detectors `v_booking_redefine_pair`, `v_pb_overbook`; "missing inverse" otherwise prose |
| **S2** idempotent / apply-once | INV | **MECH** | CAS in code (`*_claim*`) + regression tests |
| **S3** atomic claim-or-reject | INV | **MECH** | advisory lock + race tests |
| **S4** shown == true | INV | MECH(partial) | tests; no live detector |
| **S5** multi-feature resolver / supersede-own / symmetric / undo / orphan | INV | MECH(partial) | `/audit v_one_active_redefine · v_exclusivity · v_swap_exclusivity`; resolver/symmetry/undo are prose. Explicit twin of Menu Law 3+7 |
| **Menu Laws 1–8** | INV/GATE | SURF | `test_multimenu` (2/3/4), `/audit v_dead_taps` (5), `v_exclusivity` (7); rest prose; F1–F14 backlog partly open |
| **Menu Law 9** ≥3 tests before the human walk | META/GATE | **PROSE** | prose-only; instance of R5 + a walk-readiness precondition |
| **Deploy Discipline** (quiet window · batch · changed-service-only · verify) | SOP | PROSE | prose-only (verify step overlaps R2) |
| **Operational-Instructions / Ledger** (do real-data writes now or log Open) | SOP/GATE | SURF | the ledger file is the artifact; updating it is judgment |
| **SOPs**: Push · Pull · New-Machine · New-Project · Secrets · Large-Files · Automatic-Actions | SOP | mixed | Secrets backed by `secret_guard`; rest prose/runbook |
| **collapse-don't-accumulate** | META | SURF(partial) | the REMOVAL side IS formalized — the Bedrock **Ratchet** removal trigger (`docs/BEDROCK.md` §7); the "lean as you go" habit is otherwise prose (memory `breadth-over-narrowness` + this advisor item) |
| **Bedrock "one principle"** — anything Claude can produce/edit can't authorize/verify Claude | INV/meta | MECH(partial) | drives the no-override guards (delta 1: `#HIGHRISK-OK` marker removed → catastrophic set blocks, owner runs manually); the OS-lock that fully realizes it (delta 2) is PENDING (owner task) |
| **Bedrock Ratchet** — bidirectional add/remove trigger | META | SURF | `docs/BEDROCK.md`; **the formal home of "remove/compress a rule"** — add needs a real incident/drill; remove at review when a guard/rule never-once-caught-a-real-problem in ≥3mo, or is redundant, or repeat-false-positives. The lean pass should USE this, not reinvent it |
| **Bedrock deltas 2 + 4** | — | PENDING | delta 2 = OWNER OS-lock of the global guard files (`~/.claude/hooks/*` + settings) — NOT done, the only step that turns soft self-protection into a hard OS boundary; delta 4 = native-permissions direction (no build) |

## 4. Overlaps / candidate collapses (QUESTIONS for the advisor pass — not decisions)
1. **Escalation stated in 3 places** — HtB "only stop if truly blocked" + Std R6 "don't ask unless needed"
   + Bedrock-cadence escalation. → one **stop-condition / retrieve-before-asking** rule?
2. **Closing gates in 4 places** — Std R4 DONE-CLAIM GATE + Std R6 evidence block + Menu Law 9 + walk-readiness.
   → one **closing gate** with walk-readiness as its strictest subset?
3. **Cover-every-branch** — Std R5 ⊇ Menu Law 9 (Law 9 is the menu instance). Collapse Law 9 into R5?
4. **Supersession/exclusivity** — S5 ↔ Menu Law 3 + Law 7 (S5 already declares itself the data twin).
   Unify into one principle stated at two layers, or keep deliberately separate (data vs UI)?
5. **Second-opinion pass** appears in HtB + the S1–S5 checklist + the Standard. One home?
6. **Confirmation Gate** (Core R3) == key-decision "no silent AI guessing." Straight duplicate.
7. **DO-NOT force-merge** (advisor warning, already on record): S2 (real-path/epistemic), S3/S5 (architectural),
   S1 (transactional) are different load points — a smaller count here would be lossy. Lean the redundancies,
   not the invariants.

## 5. Prose-only gates = the rot list (no artifact fires at their moment)
Std R2 · Std R4 (DONE-CLAIM GATE) · Std R6 · second-opinion pass · Bedrock cadence · Menu Law 9 ·
collapse-don't-accumulate · Deploy Discipline · S1 missing-inverse (partial). **These are exactly the
rules that did not self-trigger before** (the re-sweep miss). They can be **surfaced** (a pre-push hook
could print the checklist) but not **verified**. Highest-value mechanical move available: a pre-push /
pre-"done" hook that *prints the populated-report skeleton* so the gate at least appears — it still
relies on me filling it truthfully.

## 6. What this inventory does NOT do
It does not build any mechanism, edit any rule, or pick the lean set. It is the input. Next, per the
advisor preamble: owner + advisors decide the lean standard from this evidence; only then does the
builder install the ratified result + wire whatever surfacing is agreed. The Codex/tool-switch question
stays in its own ledger note (finding on record: the failures here are process-enforcement, portable to
any tool — not a capability gap).

## 7. Bedrock + the memory layer (added Jun 14 — were under-represented above)
**Bedrock (`docs/BEDROCK.md`) is the meta-framework these rules grew from — Standards + Guards + Ratchet.**
- **Standards** = the Real-Path Precision Standard + How-to-Behave — already inventoried (§3); Bedrock
  doesn't duplicate them (single source, no drift).
- **Guards** = the two hooks — already inventoried (§2).
- **Ratchet** = the bidirectional add/remove policy — **this is the existing answer to "keep rules lean."**
  Add a rule/guard only on a real incident or failed drill; REMOVE/compress at review when it (a) never
  once caught a real problem in ≥3 months, (b) is redundant with a broader guard, or (c) repeat-false-
  positives on legit work. **The lean/unify pass should run THROUGH this policy, not around it** — every
  collapse the advisors propose is a Ratchet "down" move and should cite which criterion it meets.
- **The one principle** (drives every guard): *anything Claude can produce or edit cannot be the thing
  that authorizes or verifies Claude.* Delta 1 realized it (the self-typed override marker is gone →
  catastrophic actions block, owner runs them). **Delta 2 (PENDING, owner)** is the OS-lock of the global
  guard files — until done, a future session could still rewrite the guards; it's the one piece that turns
  soft self-protection into a hard boundary. Delta 4 = native-permissions direction (recorded, not built).
- Bedrock is explicitly a **floor, not a ceiling** (prevents known bad classes; judgment produces good
  work) and its **architecture review is CLOSED** — changes come from a real incident/failed drill, not
  another abstract review. A lean/unify pass is legitimate (it's compression, not re-architecture), but it
  should not reopen the closed protection-design debate.

**Memory layer (machine-local, not in the repo):** standing feedback rules live in
`~/.claude/.../memory/*.md` — `breadth-over-narrowness` (the universal lessons from higher-model reviews,
incl. the re-sweep-didn't-self-trigger diagnosis that motivated this pass), `precision/deploy`,
`second-opinion`, `operational-instructions`, `owner-always-approves`. **Most are already codified into
`CLAUDE.md`** (precision/deploy → the Standard; second-opinion → How-to-Behave; operational-instructions →
the Ledger rule), so the inventory's §3 covers their codified form. The one not fully codified is the
re-sweep diagnosis — which is exactly the input the Advisor Brief summarizes. Advisors don't need the raw
memory files; the codified rules + the brief's failure summary carry the content.
