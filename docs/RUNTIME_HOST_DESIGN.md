# MULTI-TENANT RUNTIME HOST — design (S60 A6, 2026-07-03) + inert skeleton

> The wall it kills: today each tenant bot = one OS process (~40–60 MB, own long-poll) → a 2 GB box
> caps at ~30 processes (docs/CAPACITY_AND_SCALE.md §2). The host runs N tenants' bot applications
> in ONE asyncio process → marginal tenant cost ≈ 1–5 MB + one idle socket → hundreds per small box.
> Design now (before client #5, per the capacity plan); NO live change until a 2nd tenant exists.

## Shape

ONE process, one asyncio loop, N python-telegram-bot `Application`s — each tenant keeps its OWN
token, handlers, and error handler; they share only the loop and the DB pool:

    tenants = load_tenant_specs()          # orgs × enabled telegram channel, tokens from core_org_secrets
    host.run(tenants)                      # build → initialize → start → start_polling, per app; idle; graceful stop

- **A tenant spec is config, not code** (the platform law): `{org_id, bot_token, registrar}` where
  `registrar(app, org_id)` attaches the tenant's handlers — e.g. `adapters/telegram_onboarding.register`
  or, later, the full ops adapter. The BRAIN stays in `core/*`; the host is plumbing.
- **PTB mechanics:** don't use `run_polling` (it owns the loop). Per app:
  `await app.initialize(); await app.start(); await app.updater.start_polling()` — then one
  `asyncio.Event` idles the host; reverse order on shutdown. This is the documented PTB multi-app
  pattern and needs no fork of PTB.

## Isolation & observability (the laws applied)

- **Crash isolation:** handler exceptions stay inside PTB's per-app error handler (each app gets
  `make_error_handler("host:<org>")` → sink + Monitor, the existing chokepoint). One tenant's dead
  token = that app's polling retry-loops; others unaffected (supervised per-app start with backoff).
- **Liveness (T3):** the host beats `svc:runtime_host` each supervision tick + one beat per tenant app
  (`host:<org>`) with a declared gap — a silent tenant is visible even while the process lives.
- **DB:** all tenants share the ONE pooled `shared.database._db` (A1: ThreadedConnectionPool, cap 4)
  — N tenants add ~zero connections. org_id scoping is already universal in core (173 verified sites).
- **Security:** tokens come from `core_org_secrets` (encrypted at rest once `ORG_SECRET_KEY` is set);
  never logged (log_redact hygiene installs once per process).

## What it is NOT (yet)

- NOT running TWB's live bots — gm/retail keep their processes until the platform cut-over; the host
  serves NEW platform tenants (demo/onboarding bots first — `run_onboard_demo.py` becomes a 1-tenant host).
- NOT a webhook ingest — that's the tier-2 flip (capacity doc §3); polling per tenant is fine to ~thousands.
- NO service unit installed until a 2nd real tenant exists (the trigger written in the capacity plan).

## Skeleton (inert, tested)

`runtime_host/host.py` — `TenantSpec` + `build_apps()` (pure assembly, unit-testable offline) +
`run()` (the loop plumbing above). `tests/test_runtime_host.py` proves: 2 specs → 2 independent
Applications each carrying its tenant's handlers + error handler; a bad spec is skipped with a
report (fail-soft, the fleet must not die on one tenant's typo'd token).

## The scaling ladder it slots into

tier 0 (now): six single-tenant processes ✓ · tier 1 (~100s): THIS HOST + pgbouncer + retention ✓
(this doc) · tier 2 (~10k): webhook ingest + stateless workers · tier 3 (1M): shard by org_id.
