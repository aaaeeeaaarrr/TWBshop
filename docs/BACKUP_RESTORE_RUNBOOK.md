# BACKUP / RESTORE RUNBOOK — DO managed PG (S60 A7, drilled 2026-07-03)

> The droplet is cattle (repo + secrets + bootstrap rebuild it). The DATA lives in the managed-PG
> cluster `twbshop-db` (pg 16, sgp1) — this runbook is how it comes back. Drilled end-to-end
> 2026-07-03 via the API (fork → verify rows → delete); re-drill after any major schema era.

## What DO gives us (verified 2026-07-03)

- **Daily automatic backups**, ~20:13 UTC (≈ 03:13 PP), 7-day window (8 were listed), ~0.23 GB each.
- Point-in-time is NOT part of this plan (basic tier) — worst-case data loss = up to ~24 h back to
  the newest backup. Acceptable at TWB scale; revisit the tier when clients' money history grows.

## Restore = FORK, never overwrite

A restore creates a NEW cluster from a backup — the damaged original stays for forensics. Two ways:

**API (drilled, scriptable):**
1. List backups: `GET /v2/databases/<cluster-id>/backups` (token: `secrets.DO_API_TOKEN`).
2. Create the fork: `POST /v2/databases` with
   `{"name":"twbshop-db-restore-<date>", "engine":"pg", "version":"16", "size":"db-s-1vcpu-1gb",
     "region":"sgp1", "num_nodes":1, "backup_restore":{"database_name":"twbshop-db",
     "backup_created_at":"<backup ts>"}}`
3. Poll `GET /v2/databases/<new-id>` until `status: online` (drill: ~10–15 min), then connect with
   the fork's own `connection.uri` and VERIFY real rows (staff_registry ≈ 42, orders, sessions).
4. Cut over = point `DATABASE_URL` in secrets at the fork (`bootstrap.py --push-secrets`, restart
   services) — or copy data back. The drill only verified + deleted.
5. Drill hygiene: `DELETE /v2/databases/<new-id>` the moment verification passes (it bills hourly).

**Console (fallback):** Databases → twbshop-db → Backups → Restore to new cluster.

The drill script (steps 1–3 + delete, with credential-safe logging) ran from the session scratchpad;
re-create it from this runbook when re-drilling — it is deliberately NOT a repo tool (a casual
`--apply`-style restore tool would be an attractive nuisance next to prod).

## The other halves of disaster recovery (already standing)

- **Repo/code**: GitHub (private) + deploy-by-tag; server rebuilds via `bootstrap.py`.
- **Secrets**: the `-secrets` repo (push changes with `bootstrap.py --push-secrets` — the 2026-06-26
  gm-token incident is why the repo must stay canonical).
- **Droplet**: no unique state outside `/root/TWBshop` + systemd units; snapshot optional.
- **Detection**: a dead DB alarms within minutes (heartbeats + collection watchdog + sentinel
  `db_headroom`/`stale_heartbeats` — the s59 net).

## Drill log

- **2026-07-03 (S60 A7):** backups listed (8) → fork `twbshop-db-restore-drill` created from the
  2026-07-01T20:13Z backup via API → **online in ~7 min** → verified real data: staff_registry=42
  (the full roster), attendance_sessions=342, payback_debts=38; `core_job_heartbeats` absent —
  CORRECT, the backup predates the s59 deploy that created it (faithful point-in-time proof) →
  fork deleted (~7 min of the smallest cluster ≈ half a cent). Outcome: **API path PROVEN
  end-to-end; no console dependency; restore-time budget ≈ 10 min + verify.**
