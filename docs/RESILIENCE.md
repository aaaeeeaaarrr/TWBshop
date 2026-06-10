# Resilience — every "system down" safeguard in one place

> The single record of what protects the bots when something fails, with status and proof.
> Update this whenever a safeguard is added/changed. (Created 2026-06-11 after discovering the
> collection watchdog had been built in session 28 but never armed — the cron daemon was inactive
> and nobody had one place to notice.)

## Layer 1 — nothing is lost during short outages (inherent)
- **Telegram queues every update for up to 24h** while a bot is down (we long-poll; never switch
  to webhooks — a down webhook endpoint DROPS messages, the poll queue keeps them).
- **Queued updates are judged fairly** — `_msg_time_pp` (gm_bot/bot.py): check-ins/pings/checkouts
  are timed by the staffer's Telegram-stamped send time, never by when a recovering bot processes
  them. A punctual staffer can't be marked late by OUR downtime. (Fixed + tested 2026-06-11.)

## Layer 2 — crashes self-heal (on-server)
- **systemd `Restart=always` + `RestartSec=10`** on all five `twbshop-*` units: a crashed process
  is back in ~10s, automatically. (Every real crash in the server's 20-day history self-healed.)
- **`TimeoutStopSec=15`** on all five units: a hung shutdown is bounded, protecting the clean
  SIGTERM path (clean poll-offset ack → no duplicate re-delivery). (Set + verified 2026-06-11.)
- **Listener `_catch_up`** (session 28): on every startup the listener BACKFILLS missed group
  history per chat — its data gap closes itself once restarted. (Bot-API bots can't backfill;
  that's why gm downtime in Supervisors/Management matters doubly — see watchdog.)

## Layer 3 — money/data can't corrupt across restarts
- **Idempotent OT banking** — `shift_change_claim_settle` atomic compare-and-swap: exactly one
  checkout path banks a shift; crash-redelivered duplicates and concurrent auto+manual checkouts
  bank nothing. (2026-06-11, regression-tested.)
- **Status-first writes everywhere else** — AL approval, shift-change decisions, daily AL
  deduction flip status BEFORE moving balances; no-show is UNIQUE-constrained.
- **Live flow state in DB** (`gm_flow_state`) — a staffer mid-flow keeps their place across a
  restart.

## Layer 4 — someone notices (the May 28–31 lesson: a silent 3-day listener crash-loop)
- **Collection watchdog** — `run_collection_watchdog.py`, cron **every 1 minute** on the server:
  - services: `twbshop-listener`, `twbshop-gm`, `twbshop-hire` must be active;
  - data: any ops_messages silence > 3h; per-chat cadence (REPORT/Stock 26h, COMMS 48h,
    Supervisors 96h);
  - alerts the OWNER by Telegram (direct Bot-API call — works even while the bots are down),
    throttled to one per 6h, with the fix command in the message.
  - ⚠ **History:** built session 28, but the cron DAEMON was inactive — it never ran until
    **2026-06-11**, when this was discovered, cron was enabled (`systemctl enable --now cron`),
    and the next minute's tick was verified writing `logs/watchdog.log` ("ok").
  - ⏳ Alert path (the 🚨 DM itself) is owner-verified: stop a bot briefly and run the script
    (guard blocks Claude from `systemctl stop`).
- **Hire bot as backup recorder** for Supervisors/Management (same message_id space →
  duplicate-free dual write) — gm's senior-room recording survives a gm outage.

## Layer 5 — humans don't cause the outage
- **Deploy Discipline** (CLAUDE.md): quiet-window (05:30–07:00 · 14:00–15:30 · 20:30–21:30 PP),
  batch deploys, restart only the changed service, verify after (HEAD==origin · active · grep).
- **HIGH-RISK guard hooks**: destructive commands hard-block, no override; app-bot restarts
  allowed; `stop`/non-app restarts owner-only.
- **`docs/ACTIONS_LEDGER.md`**: real-data instructions logged Open/Done so none drop.

## Layer 6 — the platform
- **DB**: DigitalOcean managed Postgres (their HA + backups). The bots reconnect per-operation.
- **Droplet**: 0 downtime in its recorded life (since 2026-05-21).

## Known gaps (accepted, with reasons)
1. **Droplet-level death** — the cron watchdog dies with the server. Mitigation parked:
   healthchecks.io dead-man switch (free, external, alerts Telegram). Revisit if the droplet ever
   actually fails, or before the shop depends on sub-hour recovery. (0 occurrences in 20 days.)
2. **Cron-daemon death** (the watchdog's watchdog) — same answer as #1; an external dead-man
   switch is the only true fix. Accepted for now.
3. **Outage > 24h** — Telegram's queue limit; updates older than 24h are gone (listener backfills
   its groups; gm DMs are not backfillable). The 1-minute watchdog makes an unnoticed >24h outage
   practically impossible.

## Incident history (worst first)
- **May 28–31: listener crash-loop, ~3.2 days** (~22,800 restart cycles) — unnoticed because no
  watchdog ran. Produced the session-28 reliability package (watchdog + `_catch_up` + backfill).
- **May 21–22: retail/b2b setup-day loops** (first-deploy config issues).
- **May 26 + May 30: gm blips, ~30s/~80s** — bad deploys, fixed in ~1 min while deploying.
- **Since June 1: zero failures, all services.**
