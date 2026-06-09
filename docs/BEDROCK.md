# Bedrock — cross-project safety & quality system

**Bedrock = Standards + Guards + Ratchet.** A *floor, not a ceiling*: it prevents known bad failure
classes; it does not produce good work (judgment does). Denylists are incomplete — this is
defense-in-depth, not a force field. Slower-but-solid for high-risk; no ceremony for routine.

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
   Bidirectional (delta 5) or it is just a one-way accumulator.

## Current state (session 31)
- **BUILT + verified:** `highrisk_guard.py` (hard-block exit 2 in all modes), `secret_guard.py`
  (write-time secret scan), global install + bootstrap sync, marker protocol documented. Hard-block
  live-proven for the Bash tool this session.
- **PENDING:** the 5 deltas below, then the fresh-session wiring test (the only real proof).

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

## Implementation order (next session) — CORRECTED after the feasibility check
The OS boundary moves to LAST: locking the guards first would make every delta edit need an elevated
step. Finalize the code, prove it, THEN lock it.
1. **Claude** applies deltas 1, 3, 5 to the real files. The final guard write also REMOVES the
   `#HIGHRISK-OK` marker — a clean cutover: after it, guard edits hard-block with no override (soft
   self-protection even before the OS lock).
2. **Fresh-session wiring test — the only real proof.** In bypass mode: a catastrophic action must die
   on exit 2 with NO override available; verify the owner-run-manually path; grep for a DB write path
   that dodges the guard. Three advisors agreeing is still zero proof the hook fires.
3. **Owner LOCKS** the global enforcing files (delta 2, elevated shell) — upgrades soft self-protection
   to a hard OS boundary. Verify the resulting ACL together (real-path: read it back, don't assume).
4. Back to attendance flows. **No universal tests gate** — project-opt-in, push/deploy-time only, and
   only where a real test suite exists.
