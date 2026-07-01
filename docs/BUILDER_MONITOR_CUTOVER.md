# Builder-monitor cut-over (W3 #5 / Sep-F2) — move the monitoring jobs out of the client gm bot

**Law (client/builder separation):** the builder/system monitoring — telling **us** the platform is healthy —
must not run inside a **client** bot process. Today the read-only monitoring JOBS run inside `twbshop-gm`
(the TWB client bot). That's the last piece of the separation the s58 sweep didn't close.

**Scope-honest status (owner, 2026-06-30):** this is a **multi-client** structural item. It is *tolerable in
gm today because TWB is the lone tenant*, and `gm_bot.audit.run_audit` audits TWB's **legacy single-tenant**
ledger (so its audit half is twb-only; only the Sentinel half is already org-scoped). A full always-on all-org
monitor service is therefore **ahead of need** for one tenant. This doc + `scripts/builder_monitor.py` are the
**turnkey foundation**; the cut-over itself is **owner-gated** (it restarts the live gm bot). Do it at
multi-client, or after the core cut-over makes the ledger org-scoped.

## The 5 builder/monitoring jobs in `gm_bot/bot.py` (enumerated — the CLASS, grepped not guessed)
| job | cadence | what it does | route |
|---|---|---|---|
| `_auto_audit_job` | daily 07:30 | `run_audit` over the real ledger → problems | `_alarm("daily_audit")` → sink+Monitor |
| `_live_watchdog_job` | every 3 min | `run_audit` + `_watchdog_delta` (new/cleared) + self-close | `_alarm("watchdog")` → sink+Monitor |
| `_sentinel_sweep_job` | every 30 min | `core.sentinel.sweep("twb")` + `_sentinel_new_alarms` dedupe | `_alarm("sentinel:…")` → sink+Monitor |
| `_shadow_digest_job` | nightly | `core.shadow.build_digest` (cut-over readiness) | `_monitor_send_sync` → Monitor |
| `_test_watchdog_job` | every 60 s (test-mode) | `run_audit(test_rows=True)` + delta | `_alarm("test_watchdog")` → sink+Monitor |

All **output** is already Monitor-routed (H1 + the s58 separation sweep) — only the **jobs themselves** still
live in the client process. Everything else in the gm scheduler (checkin · AL · no-show · pay · reaper ·
session-closer · re-ping · digests) is genuine **client-ops** (owner-as-client-manager) and correctly stays.

## What already runs standalone (no cut-over needed)
- **The daily read-only DIGEST** — `scripts/morning_report.py` (audit + Sentinel + alarm-sink + shadow →
  Monitor), server crontab `0 1 * * *` (08:00 PP). This is the once-daily builder view, already outside gm.

## The foundation built now (additive · INERT · not scheduled/deployed)
- **`scripts/builder_monitor.py`** — the **alerting** half (the piece still embedded in gm): a standalone,
  org-scoped, read-only sweep (audit for the legacy live org + Sentinel per org) that **dedupes** (its own
  `bmon_*` state so a manual run can't corrupt gm's state) and routes **NEW** alarms to the durable sink +
  the Monitor. **Dry-run by default** (prints, writes nothing); `--send` persists + DMs the Monitor (prod-gated
  by `notify_monitor`). Iterates every org (`all_orgs()`; today just `twb`). Re-uses the live logic; its dedupe
  is parity-locked to the gm originals by `tests/test_builder_monitor.py` so the two copies can't drift.
- ⚠ Do **not** schedule it alongside the gm jobs — both would alarm the same problem. It is a manual/on-demand
  independent sweep until the cut-over removes the gm jobs.

## Owner-gated CUT-OVER steps (when multi-client / after the core cut-over)
1. **Stand up the builder monitor** as its own unit (a `twbshop-monitor`-style systemd service or a crontab):
   `TWBSHOP_ENV=prod python scripts/builder_monitor.py --send` on a short interval (e.g. every 3–5 min), + keep
   `morning_report.py --send` for the daily digest. Verify it alarms into the sink + Monitor from a **non-gm**
   process.
2. **Remove the 5 jobs from gm** (`gm_bot/bot.py` `run_repeating`/`run_daily` registrations for the 5 above) and
   restart `twbshop-gm` **in a quiet window** — HIGH-RISK (live attendance bot) → tag-deploy + verify (server
   HEAD==tag · gm active NR=0 · a check-in still works · the builder monitor is the one now alarming).
3. **Verify no gap + no double-alarm:** exactly one process runs each check; the sink shows alarms coming from
   the builder monitor, not gm.
4. At true multi-client, make `run_audit` (or its successor) org-scoped, or replace it with the core per-org
   audit, so the loop genuinely sweeps every tenant's ledger.

## Trigger
Do NOT cut over for a single tenant — it adds a process + a live-gm restart for no functional gain today. The
value lands when there is a **2nd client** (a client bot must not run our cross-client monitoring) or when the
ledger becomes org-scoped. Until then: gm runs the jobs (tolerable), `morning_report` gives the standalone daily
view, and `builder_monitor.py` is the ready on-demand sweep + cut-over foundation.
