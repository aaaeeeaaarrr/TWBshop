# Bedrock — cross-project safety & quality system

**Bedrock = Standards + Guards + Ratchet.** A *floor, not a ceiling*: it prevents known bad failure
classes; it does not produce good work (judgment does). Denylists are incomplete — this is
defense-in-depth, not a force field. Slower-but-solid for high-risk; no ceremony for routine.

**Cadence (session 31):** lean/fast by DEFAULT — full rigor only on "bedrock this", auto on the
genuinely dangerous set, or when flagged `WE SHOULD BEDROCK THIS`. The Guards stay always-on regardless;
cadence governs rigor, not the hard-stops. (Canonical rule lives in `~/.claude/CLAUDE.md` → How to Behave.)

Converged design (owner + 3 adversarial advisor passes, session 31, 2026-06-10). **The architecture
review is CLOSED** — further changes come from a real incident or a failed drill, not another abstract
review. When review shifts from finding protection gaps to polishing wording, stop and go test/build.

## The one principle (the test for every guard)
**Anything Claude can produce or edit cannot be the thing that authorizes or verifies Claude.**
This single idea drives deltas 1, 2, and 4 below — see them as one principle, not three patches.

## Three layers
1. **Standards** — behavioral rules Claude follows (judgment). = the Real-Path Precision Standard
   (6 rules + modes) + How-to-Behave habits, already verbatim in `~/.claude/CLAUDE.md` and this repo's
   `CLAUDE.md`. NOT duplicated here (single source — avoid drift).
2. **Guards** — mechanical PreToolUse hooks that do NOT depend on Claude's judgment. Source of truth =
   `.claude/hooks/`; installed globally + synced to every machine by
   `bootstrap.py::_ensure_global_guards()`.
3. **Ratchet** — turn recurring failure classes into permanent protection; periodically COMPRESS.
   Bidirectional (delta 5, now LIVE — see "Ratchet removal trigger" below) or it is just a one-way
   accumulator.

## Ratchet removal trigger (delta 5 — the bidirectional rule, now standing policy)
Addition has a concrete trigger (a real incident or failed drill → add a guard/rule). Removal now has
one too, so Bedrock stays lean by design, not by cleanup panic. A guard pattern or standing rule is a
**compress-or-delete candidate** at the next review when ANY of these holds:
- it has **never once been the thing that caught a real problem** (not a drill) since it was added, AND
  has existed for **≥ 3 months**; or
- it is **redundant** — another guard already blocks the same action class (keep the broader one); or
- it produces **repeat false-positives** on legitimate work (≥ 2 distinct real tasks tripped wrongly) —
  fix the pattern or drop it; a guard that cries wolf trains the owner to ignore blocks.
How to act on a candidate: don't silently delete — at the review, state the candidate + which criterion
it meets + propose compress (tighten the regex) OR delete, and let the owner confirm. Record the removal
in this file's changelog so the Ratchet's *down* moves are as auditable as its *up* moves.
Each PROTECTED/SECRET pattern should be cheap to attribute: when a guard fires on a genuine catastrophe,
note it (date + what it caught) so "never once caught anything" is a checkable claim, not a guess.

## Current state (session 32, 2026-06-10)
- **BUILT + verified:** `highrisk_guard.py` and `secret_guard.py` rewritten — **deltas 1, 3, 5 SHIPPED**
  to both the repo copy and the live global `~/.claude/hooks/`. Global install + bootstrap sync intact.
- **Delta 1 LIVE:** the self-typed `#HIGHRISK-OK` marker is GONE. Every catastrophic match hard-blocks
  with no override; the block message leads with `🛑 NEEDS YOU — run in your terminal: ! <cmd>` so the
  owner (who reads only results) sees the one-paste fix. Guard now separates command-string checks from
  file-path checks → read-only `cat`/`Edit` on normal files no longer false-positive.
- **Delta 3 LIVE:** `secret_guard.py` scans staged changes before `git commit` and unpushed commits
  before `git push` (added-lines only; never blocks secret removal), on top of the write-time scan.
- **Delta 5 LIVE:** bidirectional Ratchet removal trigger written above (standing policy).
- **Wiring test PASSED (session 32):** 12/12 cases — destructive SQL / rm -rf / force-push / secrets.py
  path / guard-hook path / live API key all BLOCK (exit 2); git status / cat bot.py / edit normal file /
  key-into-secrets.py all PASS. Delta-1 no-override confirmed (a test cmd hard-blocked with no bypass).
- **PENDING:** delta 2 (OWNER OS-lock, elevated shell) + delta 4 (direction only, no build).

## Work queue — the 5 deltas (apply to the real files, then prove)
1. **Kill the self-typed `#HIGHRISK-OK` marker.** Claude can type it → it is self-approval, the exact
   dependency the guard exists to remove. Replacement: the catastrophic set (drop/truncate/delete-from ·
   `rm -rf` real paths · force-push / reset --hard · prod DB migration · prod service restart/deploy)
   BLOCKS, and the **owner runs the command manually** in their own shell. No Claude-typeable override.
   (A command *hash* is NOT enough — Claude can compute it.)
2. **Guard self-integrity (OWNER task, OS-level).** A guard Claude can edit/neuter/commit/re-sync is not
   a wall. The hook scripts, `.claude/settings.json`, the global hook/settings files, `bootstrap.py`, and
   the integrity manifest all need protection. On Windows Claude runs as the user, so this needs an
   **admin-set boundary the user cannot write** — a checksum stored beside the scripts is theater.
   `bootstrap` should refuse to install/sync a guard whose checksum differs from an owner/admin-owned
   trusted manifest. Same principle as delta 1: the verifier must live where Claude can't reach.
3. **Secret scan before EXFILTRATION, not only at write.** Keep the cheap write-time scan AND gate
   `git commit` · `git push` · upload-like commands (`curl`/`wget`/`scp`/`rsync`/`gh` with a payload) on
   a clean working-tree scan of staged + unstaged + untracked changes. The leak vector is usually the
   command *after* the write. Never block secret removal.
4. **Native permissions for the catastrophic surface (DIRECTION, not a build now).** Prefer "cannot
   access" (native deny / sandbox / owner-run) over regex "I catch it" for the worst actions. Allowlists
   are complete by construction; denylists never are. Record the direction; don't redesign now.
5. **Bidirectional Ratchet.** Give removal a trigger as concrete as addition: a guard that hasn't fired
   in N months, or a rule that has never once been the thing that caught a problem, is a compress/delete
   candidate at the next review. Keep Bedrock lean by design, not by occasional cleanup panic.

## Reporting constraint — the owner reads ONLY results (his own words, session 31)
The owner gives instructions and reads the OUTCOME only — not the assistant's prose. So a guard block
buried in explanation is invisible to him; a blocked-but-needed task would just look like "it didn't
work." Therefore:
- When a guard stops an action needed to finish his instruction, LEAD the reply with an unmissable
  `🛑 NEEDS YOU — paste this: ! <exact command, ready to run>`. One paste, pre-written. Never bury it.
- TUNE the guard patterns so HARMLESS actions never trip (today's blunt false-positives blocked even
  read-only commands). The only block he should ever see is a rare, genuinely-catastrophic one.
- Protection against the assistant's autonomous mistakes still works without him reading anything (the
  hard-stop fires regardless) — only the NOTIFICATION must move into the results channel. This is a
  hard requirement for delta 1 ("block-and-owner-runs") to actually function for this owner.

## Owner's one hands-on task (delta 2)
The OS write-boundary cannot be built by Claude — no script Claude writes can establish the wall meant
to constrain it. The owner sets the GLOBAL enforcing guard files to admin-owned / user-read-only, from
an elevated shell. Exact `icacls`/`Set-Acl` steps to be verified together on the machine — do NOT run
unverified admin commands blind.

**FEASIBILITY — VERIFIED (session 31, this machine `DESKTOP-CM74LHT`):** a real boundary IS achievable.
- Claude runs as `Papa`, **non-elevated** (filtered token, no admin rights). `Papa` is in Administrators,
  but UAC is ON (`EnableLUA=1`) and prompts on the secure desktop (`ConsentPromptBehaviorAdmin=5`) → a
  non-elevated process **cannot silently elevate**; any elevation needs a human UAC consent. That is the
  human gate that makes the wall real.
- So: change OWNER of the global enforcing files to `Administrators`/`SYSTEM` and grant `Papa`
  **ReadAndExecute only** (drop Write/Modify/FullControl, which also removes implicit ACL-change rights).
  Then non-elevated Claude can run-but-not-modify them; updates require Papa to elevate (UAC).
- **Lock the GLOBAL enforcing copies only** — `~/.claude/hooks/*.py` + `~/.claude/settings.json` — NOT the
  repo source (`git pull` rewrites those; locking them would break pull). Cover bootstrap's reach too.
- **Tradeoff to accept:** after locking, `bootstrap --sync` silently no-ops on the locked files (harmless
  — its writes are already best-effort/swallowed), and updating a guard becomes a deliberate elevated
  step. That friction is the point.

## Implementation order — STATUS (session 32)
1. ✅ **DONE (session 32).** Deltas 1, 3, 5 applied to repo + global guards; `#HIGHRISK-OK` marker
   removed (clean cutover — guard edits now hard-block with no override even before the OS lock).
2. ✅ **DONE (session 32).** Wiring test ran — 12/12, including delta-1 no-override confirmation. The
   guards are syntactically valid and live in this session (a real DROP-TABLE-bearing command was
   hard-blocked mid-session). Still TODO when convenient: grep for any DB write path that dodges the
   guard entirely (e.g. a script that imports psycopg2 and runs DDL without matching a CMD pattern).
3. ⏳ **OWNER, NOT DONE — delta 2, elevated shell.** Lock the global enforcing files
   (`~/.claude/hooks/*.py` + `~/.claude/settings.json`) to admin-owned / Papa-ReadAndExecute. Feasibility
   verified session 31 (UAC gate is real). Verify the resulting ACL by reading it back. This is the only
   step that turns soft self-protection into a hard OS boundary — until then a future session could still
   rewrite the guards (as session 31→32 did, legitimately).
4. Back to attendance flows. **No universal tests gate** — project-opt-in, push/deploy-time only, and
   only where a real test suite exists.
