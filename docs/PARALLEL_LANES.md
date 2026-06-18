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

---

## Build sequence (locked with owner, 2026-06-19) — the master to-do, in order

Stacks the lane infra + product work + the parked items + the owner-time bonuses. Greenfield-first;
shared / HIGH-RISK work earns full rigor. Mark items done as they ship.

### Phase A — Lock the lane infra  [DONE this session unless noted]
- [x] Lane map gains `gm` + `stock`; `lane_guard.py` **v2** (read any lane, write only your own +
      shared; `docs` is a SOFT lane = warn not block; `.lane_ack` overrides a deliberate cross-lane write).
- [x] `scripts/monitor.py` — read-only watcher (lane board + service health → owner DM; send-only).
- [x] `scripts/pull-all.ps1` — refresh every CLEAN worktree; skips dirty; abort+report on conflict.
- [x] `pull.ps1` upgraded — `pull` in a lane also merges `main` ("get me everything").
- [x] `.claude/settings.json` valid + lane_guard wired (owner); monitor bot live + DM verified.
- [ ] **A2 — commit + push the infra** so new worktrees inherit it. (owner: say `push`)
- [ ] **A3 — (owner choice)** switch this terminal to a guarded `lane/accountant` (+ park a `main`
      worktree) so every active terminal is guarded, OR keep `main` as integrator+accountant.

### Phase B — Fan out (shared groundwork single-threaded FIRST)
- [ ] B1 — define the SHARED stock tables once on `main` (`acc_items`, `acc_item_aliases`,
      `stock_movements`; design §E11) — the accountant↔stock seam, done before fan-out = no clash.
- [ ] B2 — open the `gm` and `stock` lane worktrees (`scripts/make_lane.ps1`).

### Phase C — Product work (parallel)
- [ ] C1 — Accountant: finish P1 capture → **P2** (slip relay + subset-sum/FIFO matcher +
      anti-double-pay). HIGH-RISK money, per-step owner approval.
- [ ] C2 — Stock lane: AppSheet structure + Postgres↔AppSheet sync + 143-item catalog seed;
      migrate GM's stock code out (`stock.py`/`stock_entry.py`/photo reader/7am job). First unknown
      to prove: **AppSheet↔DO-Postgres connectivity**.
- [ ] C3 — GM: staff stock-gateway **button** (link to AppSheet) + optional read-only "count done?"
      glance. GM owns no stock data.

### Phase D — Data-integrity cross-checks (needs C's data flowing)
- [ ] D1 — AppSheet prefills last count + **today's received** + shows the unit (kg/piece) → staff
      self-catch errors at source.
- [ ] D2 — Accountant **READ-ONLY** discrepancy / unit-mismatch cross-check → alert (group TBD);
      tune thresholds so small real-usage gaps don't false-alarm.

### Phase E — Owner-time bonuses (demand-pulled, once lanes run)
- [ ] E1 — Unified **"Needs You" inbox**: every lane writes owner-decisions to ONE shared
      `pending_decisions` table; one digest/menu, batch-clear. (Generalize `acc_pending_decisions`.)
- [ ] E2 — **Morning digest** from the watcher (lane board + services + pending count, one DM).
- [ ] E3 — **`status` word**: glance all terminals from one place.
- [ ] E4 — **Auto-refresh Stop-hook** (seamless): when a lane goes idle, **only if it's behind main**
      → merge (≈zero overhead otherwise). **Clean → silent/auto.** **Conflict → the lane's own Claude
      resolves it in place** (full context), commits on the lane, and the watcher DMs you the files +
      a one-line fix. **A conflict in a money-path file (defined sensitive list) instead PAUSES with
      "🛑 needs you"** — never auto-resolved. Safe because it all happens on a lane branch (pre-deploy);
      deploys stay manual/tagged/verified. Opt-out per lane via a `.no_autorefresh` marker.
      `.needs_pull` / `.no_autorefresh` are gitignored.

### Phase F — Deferred hardening (only if scaling past ~3 lanes)
- sparse-checkout · merge queue + auto-merge · server-side commit-scope CI · test-suite rollback
  refactor · monitor autonomy.
