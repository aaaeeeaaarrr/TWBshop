# Parallel Lanes — operational guide

How to run several Claude Code terminals on this repo at once without one breaking another.
Design rationale (with the advisor critique folded in): `C:\Users\Papa\twbshop-parallel-lanes-briefing.md`.

> **Status: machinery built but DORMANT.** The pieces below exist; nothing is active until you
> (a) wire the lane-guard hook into `.claude/settings.json` and (b) create a lane with `make_lane`.
> Until then the repo behaves exactly as before.

---

## What a "lane" is
One independent stream of work = one **git worktree** = one branch `lane/<name>` = (usually) one
service. Worktrees share one `.git` but have separate folders, so two terminals can't clobber each
other's files. Git also refuses to check out the same branch twice — one lane = one terminal.

## The lane map — `parallel_lanes.json`
The single source of truth for which files belong to which lane (and which are `shared`). It is an
S5 resource: every tracked file is owned by exactly one lane OR is `shared`; editing the map itself
is integrator-only. The lane guard reads it.

## Cross-lane warning — `scripts/lane_guard.py`  (WARN-only v1)
A PreToolUse hook. When a lane edits a file outside its own paths it prints a loud warning naming the
lane(s) that file concerns, so you can pause them. **v1 only warns — it never blocks** (so it can't
lock up your workflow). On `main` it's silent (you're the integrator).

**To activate it** (owner step — the highrisk guard blocks Claude from editing `.claude/`): add a
third command to the existing `PreToolUse` hook array in `.claude/settings.json`:

```json
{ "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/scripts/lane_guard.py\"" }
```

(Use `/update-config` or edit by hand. It self-filters to Edit/Write tools, so the shared matcher is fine.)

## Start a lane — `scripts/make_lane.ps1`
```powershell
.\scripts\make_lane.ps1 accountant      # -> ..\twbshop-accountant on branch lane/accountant
```
Then per the printed steps: `bootstrap.py --sync`, a per-lane venv, `TWBSHOP_ENV=staging`, `claude`.

## The rules that keep lanes safe
1. **Each terminal commits its own lane, anytime — committing is never coordinated** (it's local to
   that branch and can't touch another lane's files).
2. **Only `main` is integration; deploy from a TAG, never a branch tip.** prove on staging → green
   suite → tag → `git checkout <tag>` on the server → restart → verify. (Phase 0 was the first one.)
3. **Merge-to-main is the one serialized step** — one lane at a time; rebase onto `main` first; run
   the FULL suite against current `main` before merging (catches clean-but-broken merges).
4. **`TWBSHOP_ENV=staging` in every dev shell.** Prod is fail-closed: an unset env refuses to connect.
5. **Never run a live bot loop locally** (the runtime guard refuses unless `TWBSHOP_POLL_OK=1` / a dev
   token + `ALLOW_LOCAL_POLLING=1`). One token = one poller.
6. **Lane-local notes go in `CLAUDE.local.md`** (gitignored — never merge-conflicts). Tracked
   `CLAUDE.md` is global only.

## Deferred hardening tier (build when actually running 2+ concurrent lanes)
- **Sparse-checkout** so other-lane files are physically ABSENT in a worktree (absence beats a warning).
- **Hard-block-with-ack** + a live sibling-worktree dirty check in the lane guard.
- **Server-side commit-scope CI** (GitHub branch protection) so a cross-lane commit can't merge.
- **Observational monitor daemon** (watch worktrees/services/DB read-only → Telegram), then a
  localhost browser board. Partly overlaps the existing collection watchdog for the live side.
