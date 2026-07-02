# CAPACITY & SCALE — measured today, designed for millions (2026-07-03)

> Owner questions: how much of the server is used? · how much does each client add? · can we handle
> millions, and shadowruns? · design it so no AI/observer can easily learn the system. Measured
> read-only on prod; the per-client model and the tier plan follow from the numbers.

## 1. TODAY — measured (droplet 129.212.228.102 + managed PG)

| Resource | Capacity | Used | Verdict |
|---|---|---|---|
| CPU | 1 vCPU | load 0.08 (≈idle) | ~5% at full TWB operation |
| RAM | 2 GB (+2G swap) | 577 MB (1.4 G available) | all six services = **226 MB combined** (gm 60 · listener 45 · retail 40 · hire 38 · wizard 30 · automations 13) |
| Disk | 48 GB | 9.4 GB (20%) | repo+logs+receipt archive = 635 MB |
| DB total | managed PG | **177 MB** | 156 MB of it = `ops_messages` (TWB's comms-archive add-on, not a platform requirement); the ENTIRE attendance platform ≈ 2 MB |
| DB connections | **25 max** | **16 in use** | ⚠ the tightest constraint in the whole system — per-call `_db()` with no pool |

Reading: one full-featured, 24/7, 42-staff business — bots, brain, shadowrun, observability net —
costs ~a quarter of the smallest droplet. The system is *light by construction*.

## 2. PER-CLIENT footprint — the "levers" intuition is correct, with one asterisk

A tenant = an `orgs` row + config JSONB (KBs — the levers) + staff rows (KBs) + their EVENT stream.
- **Data:** a TWB-scale client ≈ 0.5–2 MB/month of events (attendance/sends/heartbeats/points).
  The comms-archive layer (ops_messages-style) is the one heavy option (~150 MB/6mo) — sold as an add-on
  with retention policy, not default.
- **Compute:** near-zero CPU (events are sparse — humans check in a few times a day).
- **The asterisk — the RUNTIME shape:** today each bot = one PROCESS (~40–60 MB) with its own Telegram
  long-poll. Replicated per client, a 2 GB box caps at ~30 processes. The design step (before ~client #5):
  a **multi-tenant runtime host** — ONE process running N tenants' bot applications in one asyncio loop.
  Marginal cost per tenant in-process ≈ 1–5 MB + one idle long-poll socket → hundreds of tenants per
  small box. The BRAIN needs no change: `core/` is already org-scoped everywhere (verified — 173 query
  sites in the security sweep); the single-tenant hardcodes live only in the legacy gm bot, which retires
  at cut-over.

## 3. THE TIER PLAN — what changes at each order of magnitude

| Tier | Clients | What must change | What NEVER changes |
|---|---|---|---|
| 0 (now) | 1–10 | nothing but a **DB pooler** (16/25 conns already) | the org-scoped brain · config-as-levers · append-only events · the observability law |
| 1 | ~100s | multi-tenant runtime host · pgbouncer · event partitioning + retention jobs · 2–4 GB box (~$40–80/mo) | same |
| 2 | ~10k | **the polling→webhook flip**: at fleet scale an LB'd always-up HTTPS ingest + queue + Telegram's own retry beats 10k pollers (the "down endpoint drops" objection is solved by redundancy + queue-ack — the law was written for ONE box, and says so) · stateless workers · read replicas | same |
| 3 | 1M+ | shard by org_id (already the universal key = shard-ready) · event bus · worker fleet · real infra team. 1M × ~100 events/day = 100M rows/day — heavy but standard SaaS engineering | same |

**Shadowruns at scale:** a shadow ≈ 2× the (tiny) per-event compute + comparison rows. Shadowing 100%
of a small fleet is free-ish; at large N you don't shadow everyone forever — you shadow **cohorts on
version boundaries** (canary discipline, already our doctrine) + the replay accelerator runs batch
off-peak. Shadow cost is a feature dial, not a wall.

**The honest bottleneck order:** DB connections (now) → process-per-bot RAM (~30 clients) → poller
count (~thousands) → DB write volume (~100k+). Each has a named, standard cure above; none requires
re-architecting the brain.

## 4. ANTI-LEARNING / IP posture — "no AI can easily read or learn it" (all domains)

Threat model, honestly: an observer (human or AI) can only learn from (a) what the client device
RECEIVES, (b) what the API ANSWERS, (c) leaked source. Our standing law already closes (c) and shapes
(a)/(b): **the brain executes only on our servers; clients receive rendered views + their own entitled
data + config knobs — never code, never rules, never the "why" beyond the knob.**

What a determined observer probing THEIR OWN tenant can learn: coarse behavior of rules they can
toggle ("there is a lateness grace; 6 min was late"). That black-box residue is irreducible for every
SaaS on earth. What they CANNOT get, and what the real IP is: the engine internals (resolver
precedence, settle math, flip/shadow nets), the verification & self-healing substrate (fully
server-side, invisible), cross-tenant anything, and — most valuable — the **accumulated ontology**:
which knobs exist, sane defaults, presets, and the fault library learned from TWB's shadowruns. That
never crosses the wire.

Standing hardening (mostly already law/built): server-side brain ✓ · entitled-data-only payloads ✓ ·
authn + org-scoping fail-closed (W3, built) ✓ · rate-limit + input validation (W3 #4, built) ✓ · no
verbose errors ✓ · thin clients forever (a future app = a shell over the same scoped API; **no logic
ships, so there is nothing to decompile** — obfuscation is never the moat, absence is) · per-tenant
canary values to detect scraped/shared exports (cheap, future) · an anomalous-access detector on the
sentinel (queries-per-tenant profile, future rule) · if WE ever embed an LLM feature, it receives
scoped tenant context only, never repo/rule text. Biggest realistic leak channel = a human resharing
their own dashboard — mitigated by entitlement scoping + watermarks + the visible layer being knobs,
not mechanisms.

## 5. DESIGN ACTIONS QUEUED (in bite order)

1. **DB pooling** (pgbouncer or app-side) — relieves today's 16/25 AND is the tier-0→1 gate.
2. **Multi-tenant runtime host** design — before client #5.
3. **Retention/rollup jobs** (send_ledger · flip_log · heartbeats · ops_messages policy) — already in
   PENDING; add ops_messages retention as a product knob.
4. **Backup/restore drill** — managed PG has DO backups; PROVE a restore once (droplet itself is
   cattle: repo + secrets + bootstrap rebuild it).
5. **Webhook-ingest tier** — documented here as the tier-2 flip; do NOT build early, do NOT foreclose.
6. Sentinel **anomalous-access rule** + per-tenant canaries — with first external clients (W3 window).
