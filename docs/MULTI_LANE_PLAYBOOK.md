# Multi-Lane Parallel Development — PLAYBOOK (portable)

> **What this is.** The complete, reusable method for running **several Claude Code terminals on one
> repo at the same time** — each on its own slice of the work — without them breaking each other, with
> a Telegram dashboard watching it all, and with mechanical guards so nothing depends on anyone
> *remembering*. Built and proven on **twbshop**; written to be **lifted into any new project** where
> you want to work on multiple dimensions at once.
>
> **Keep this file alive.** Every time we improve the setup (a new guard, a new monitor command, a new
> ritual), update this doc. It is the single source of truth for "how we run parallel lanes."
>
> The original design briefing (with the advisor critique) is `twbshop-parallel-lanes-briefing.md`.

---

## 0. The one goal

**Maximum parallel output, minimum owner attention, zero risk to anything live.** You open a few
terminals, give each one a "lane," and from then on you mostly answer a handful of yes/no questions.
Everything mechanical — isolation, warnings, syncing, verification — is automated or guarded. The
guiding rule for every piece below: **if it relies on a human remembering, it doesn't count.**

---

## 1. The model

- **Hub** = the original repo folder, on branch **`main`**. It is the **integrator/trunk**: where lanes
  merge together, where you `push` from, where shared/cross-cutting edits happen, where the monitor and
  the integration audit run. It is **not** a feature lane.
- **Lane** = one stream of work = one **git worktree** (a separate folder) on branch **`lane/<name>`** =
  usually one service/module. Worktrees share one `.git` but have separate files, so two terminals
  **cannot** clobber each other. Git refuses to check out the same branch twice → one lane = one terminal.
- **The map** (`parallel_lanes.json`) is the **single resolver** (State-Integrity Law **S5**): every
  tracked file is owned by **exactly one lane** OR is **`shared`**. Editing the map is integrator-only.

```
twbshop            (main)            ← HUB: push / pull-all / shared edits / monitor / audit
├─ twbshop-<lane1> (lane/<lane1>)    ← a guarded lane
├─ twbshop-<lane2> (lane/<lane2>)
└─ twbshop-<lane3> (lane/<lane3>)
```

---

## 2. The toolkit (the portable kit — copy these into a new project)

| File | What it does |
|---|---|
| **`parallel_lanes.json`** | The map: `lanes` (name → owned path prefixes) + `shared`. The S5 resolver everything reads. **Must be complete** — every tracked file owned or shared (the audit enforces this). |
| **`scripts/lane_guard.py`** | PreToolUse hook. Derives your lane from the branch. On a file **edit**: own lane → silent · `shared/` → **WARN** · another code lane → **BLOCK** (exit 2) · `docs` (a SOFT lane) → warn · `CLAUDE.md` (HUB-ONLY) → **BLOCK**. Reads are never touched. Loud ASCII banner. Appends every crossing to `~/.twbshop_lane_events.jsonl` so the monitor DMs you. Override a deliberate cross-lane write with a gitignored **`.lane_ack`** file (or `LANE_ACK=1`). Fail-open on its own error (a guard bug never locks the workflow). |
| **`scripts/make_lane.ps1`** | `make_lane.ps1 <name>` → creates `..\<repo>-<name>` worktree on `lane/<name>` + prints the per-lane setup steps. |
| **`scripts/checkpoint.ps1`** | The **`push`** engine. Run from ANY worktree: merges every `lane/*` that's ahead into `main`, pushes `main` + all lane branches, **verifies `main == origin/main`**. On a real conflict it **aborts that one lane** (main untouched) and reports it. Never resets, never force-pushes. |
| **`pull.ps1`** | The **`pull`**: fetch-all, rebase, secrets sync, pip. **In a lane it also merges `main`** → "pull = get me everything" (its own work + every merged lane). Only merges when clean. |
| **`scripts/pull-all.ps1`** | Refresh **every CLEAN worktree** in one command (skips dirty so it can't stomp in-progress work; aborts+reports a conflict). |
| **`scripts/monitor.py`** | Read-only watcher + data layer: `lane_board()` (each worktree: dirty/ahead/behind), `service_health()` (systemd via SSH), `anomalies()` (DM trigger = a service that should be up is down), `issues()` (needs-you + a fix each). Send-only Telegram (never polls). CLI: board / `--watch` / `--test`. |
| **`scripts/monitor_bot.py`** | **Interactive dashboard** (owner-only — ignores everyone else). Commands: `/board` `/health` `/issues` `/crossings` `/audit`. Jobs: service-down DM (silence = healthy) + cross-lane-edit DM (`🚨🔴`, reads the event sink). Wires `make_error_handler`. (PTB v21; needs the Py-3.14 `asyncio.set_event_loop(...)` line before `run_polling`.) |
| **`scripts/integration_audit.py`** | The integrator's **cross-lane sweep** (what no single lane can see): **map integrity** (no unowned/double-claimed file) + **no cross-lane commit** (no commit touches 2+ lanes' dirs, docs excluded) + optional **`--suite`** (run the tests). Exit 0 = clean. `import`-able by the monitor (`/audit`). |
| **`tests/test_*_no_drift.py`** | **Drift guards** — when the same logic is duplicated across lanes during a handover, an AST-level test asserts the copies stay identical (drift → red suite). Auto-skips once one copy is removed (cutover). |
| **`.claude/settings.json`** | Wires `lane_guard.py` as a 3rd PreToolUse hook (alongside the high-risk + secret guards). |
| **`.gitignore`** | `CLAUDE.local.md` (per-lane notes) + `.lane_ack` (cross-lane override marker). |

---

## 3. The daily workflow

- **commit** = per-terminal. Each lane's Claude commits **its own** work (with a real message). You
  never type "commit" — saying **`push`** commits the terminal you're in first.
- **`push`** (from ANY one terminal) = *commit this terminal* **+** *merge & push every lane that's
  already committed*. It does **not** grab another terminal's **unsaved** work. So: to get *everything*
  out, say `push` in each terminal that has unsaved work (or let each lane commit as it goes, then one
  `push` sweeps it all up).
- **`pull`** (in a lane) = get everything — its own branch **and** `main` (other lanes' merged work).
- **`pull-all`** (from the hub) = refresh every clean worktree at once.
- **The shared-file dance** (only when two lanes need the *same* shared file): the others commit → one
  `push` → the editor `pull`s, edits, `push`es → others `pull`. Usually unneeded — just edit + push;
  checkpoint auto-merges non-overlapping changes and only stops on a real conflict.
- **Sync-before-build rhythm:** to start fresh work on a lane, **`push` → `pull` → build**. `push`
  saves/integrates what the lane has; `pull` brings `main`'s latest in (the guard, shared modules,
  other lanes' merged work); then build on the current base. `pull` only merges `main` when the lane is
  **clean**, so the push/commit is what *lets* the pull bring `main` in — skipping it means building on
  a stale `main` and a bigger merge later.
- **Gotcha:** the **hub must be clean** before a lane can `push` (checkpoint needs the main worktree
  clean to merge into). Commit/stash hub work first.

---

## 4. The safety layers (each independent, mechanical)

1. **Worktree isolation** — separate folders → no on-disk clobber. The only collision is at git merge.
2. **`lane_guard`** — read any lane, write only your own + shared; block another lane / `CLAUDE.md`;
   warn on shared; **alert every crossing to Telegram**. (`.lane_ack` = deliberate override.)
3. **The monitor** — `/board` `/issues` on demand; DMs you on a service-down or a cross-lane edit.
4. **`checkpoint`** — merge is serialized, **abort-on-conflict**, never force-push/reset; verifies
   `main == origin`.
5. **`integration_audit`** — map integrity + no-cross-lane-commit (the checks no lane can run itself).
6. **Full suite on merged `main`** — catches a clean-but-broken merge (`integration_audit --suite`).
7. **Per-lane self-review** before compacting a session (§5).
8. **Deploy from TAGS**, never `main` tip — prove on staging → green suite → tag → checkout tag on the
   server → restart → verify (`HEAD == tag`, active, running code carries the change). `main` may carry
   WIP from every lane because deploys come from tags.

---

## 5. The rituals

### A. Per-lane self-review (before you compact/clear a lane's session)
Paste into each lane terminal:
```
Before I compact you — full self-review of everything you changed this session in THIS lane,
no claims without proof:
1. `git branch --show-current` (confirm lane) + list every file you created/changed + one line each.
2. PROVE it: run this lane's own tests on staging + exercise the real paths. Paste results.
   Re-verify anything you earlier called "done".
3. Find discrepancies: stubs/TODOs, half-finished functions, untested branches, claims that don't
   match the code, contradictions.
4. Hygiene: confirm you did NOT edit another lane's files or the tracked CLAUDE.md (notes go in
   CLAUDE.local.md). Flag it if you did.
5. Commit with a clear message, then `push`.
6. Report: ✅ solid (evidence) · ⚠️ incomplete/risky · ❌ broken + a short to-do.
```
Do lanes one at a time if test runs get flaky (they share the staging DB).

### B. Integrator cross-lane verify (the hub, before trusting a merge or compacting the hub)
- `python scripts/integration_audit.py --suite` → map + no-cross-lane + full suite on merged `main`.
- Check the **handover seams** by hand where two lanes touch the same concept (e.g. a ported file →
  add an AST drift guard test; a shared table → confirm both lanes import the shared module, no fork).
- This is the only place the *whole* system is checked — a lane passing is not the system being correct.

### C. Deploy-from-tag — see §4.8.

### D. When a lane changes LIVE or HIGH-RISK code
Lane isolation protects the *codebase*; this protects the *running system*. A lane editing a path that
runs in production (a live bot handler, a payment / attendance / auth path) follows the project's
real-path standard on top of the lane rules: **investigate read-only on prod first** (confirm the
problem is real — it's often a false alarm, not a bug), **propose + get owner sign-off before building**
(never auto-ship a live change), **prove on staging**, then **deploy by TAG in a quiet window + verify**
(§4.8) — not a casual restart. *(Worked example: a lane found a "no response" report was actually a
correct check-in, proposed a small UX fix to the live handler, and asked before building — exactly right.)*

---

## 6. The monitor / dashboard (your single pane of glass)

Owner-only Telegram bot (`monitor_bot.py`). **Silence = healthy.** It DMs you only on a real problem
(a service that was up going down) or a cross-lane edit (`🚨🔴`). On demand:
`/board` (lanes) · `/health` (services) · `/issues` (needs-you + fixes) · `/crossings` (recent
cross-lane edits) · `/audit` (the integrator sweep). Run it on the hub; server-host it for always-on.

---

## 7. Set this up in a NEW project (step-by-step)

1. **Copy the kit** (§2): `scripts/{lane_guard,make_lane,checkpoint,pull-all,monitor,monitor_bot,integration_audit}.*`,
   `pull.ps1`, and a fresh **`parallel_lanes.json`** (edit `lanes`/`shared` for the new repo's layout —
   then `python scripts/integration_audit.py` until **map integrity is clean**).
2. **Wire the guard** — add `lane_guard.py` to the `PreToolUse` hooks array in `.claude/settings.json`.
3. **`.gitignore`** += `CLAUDE.local.md`, `.lane_ack`.
4. **Monitor bot** — BotFather `/newbot` (privacy ON for an alert-only bot; you must press Start so it
   can DM you) → put the token in `secrets.py` as `MONITOR_BOT_TOKEN` → `python scripts/monitor_bot.py`.
   Set the owner chat id in `monitor.py`/`monitor_bot.py`.
5. **Shared seam first** — define any cross-lane shared module **single-threaded on the hub** before
   fanning out (so the lanes never both invent it).
6. **Fan out** — `make_lane.ps1 <name>` per lane → in each: bootstrap, venv, the dev-env var, `claude`,
   brief it ("you're the X lane — read the build plan, do what's next").
7. **Live-bot safety** — a poll-guard in each `run_*.py` (refuse a prod token off-server), one poller
   per token, never run the live bot locally.

---

## 8. The "up our game" backlog (build as demand pulls)

- **E4 auto-refresh Stop-hook** — a stale/skipped lane self-heals when it goes idle: if behind main →
  merge; clean → silent; conflict → flag (the lane's Claude resolves with context; money-path → pause).
  Never blind-resolves. Opt-out marker per lane.
- **Server-host** the monitor + the serverless bots (systemd, deploy-from-tag) so they're always-on.
- **Merge-queue / suite-on-merge** — `checkpoint` runs the suite before a merge lands (needs the
  test-suite rollback refactor so concurrent lane test runs don't collide on the staging DB).
- **Unified "Needs-You" inbox** — every lane writes owner-decisions to one shared `pending_decisions`
  table; one digest, batch-clear.
- **Morning digest** DM; **sparse-checkout** (other-lane files absent); **server-side commit-scope CI**.
- **Cap/rotate the cross-lane event sink** (`~/.twbshop_lane_events.jsonl`) — it grows unbounded today,
  and a manual truncate needs a monitor restart (the read-offset goes stale). A size cap + offset reset
  makes it self-maintaining.

---

## 9. Hard-won lessons (paid for in real time)

- **ASCII-only in the terminal.** A Windows console can't encode emoji — a stray em-dash/emoji in a
  hook banner can make the hook swallow the whole message. **Emoji live in Telegram**, never the banner.
- **PowerShell: never `2>&1` on a native exe** (git, python). PS 5.1 turns its normal stderr into a
  terminating error and halts the script (it broke a `checkpoint` mid-push once).
- **Python 3.14:** `run_polling()` needs `asyncio.set_event_loop(asyncio.new_event_loop())` first.
- **One poller per token;** never run a live bot locally (the poll-guard enforces it).
- **Lanes never edit the tracked `CLAUDE.md`** — it conflicts across lanes. Lane notes → `CLAUDE.local.md`;
  only the hub updates Current Status. (Enforced by the `lane_guard` HUB-ONLY hard-block.)
- **Hub clean before a lane pushes** (checkpoint needs the main worktree clean).
- **The map must be complete** — an unowned file means the guard can't reason about it. The audit
  enforces it.
- **"Behind main" is normal churn**, not an alert — show it on the board, never DM it.
- **A lane passing ≠ the system is correct.** Only the integrator's cross-lane sweep + the full suite
  on merged `main` proves the whole.
- **Out-of-repo writes are silent.** A scratch file in the system Temp dir (or any path outside the
  worktree) isn't lane-relevant — the guard only reasons about repo files. (Early versions warned on
  these as "unowned"; fixed to resolve the path and skip anything outside the repo root.) The monitor
  also filters out-of-repo events as a second line of defense (in case a lane runs an old guard).
- **Don't test the guard's `main()` against the live event sink.** `main()` *logs* every crossing to
  the shared file the monitor watches — testing it pollutes the alert channel (it once DM'd test
  inputs to the owner as if a lane had done them). Test the **pure `_decide()`** instead; only
  `main()` does I/O.
