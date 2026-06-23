# Wizard quickstart — how to actually drive the platform

> Practical operator guide (the "how"). The "why"/design lives in `docs/WIZARD_DESIGN.md`,
> `docs/ONBOARDING_DESIGN.md`, `docs/PLATFORM_VISION.md`; current build-state in `docs/PLATFORM_COVERAGE.md`.
> The wizard is the self-serve front-end to the config-driven platform. **Security:** it binds
> **127.0.0.1:8090 only** — reach it via `ssh -L 8090:localhost:8090 twbshop` then open `http://localhost:8090`.

## The two views
- **`/` admin** (internal, you) — every knob badged **LIVE / SHADOW / LIVE_FIXED / PLANNED**, raw values
  (secrets masked), the cut-over dashboard, the catalog, and a tool nav + **📊 at-a-glance** (staff · groups ·
  channels · config-health · last change).
- **`/customer`** — the product a tenant sees: their settings in plain English (an explanation + true/false +
  if-conditions next to everything), edited in a **draft** (Apply / Cancel — nothing commits until Apply).
  Only safe (non-live) knobs are editable; live ones show locked; tokens are write-only.

## Onboard a tenant (the happy path)
1. **`/bot`** — guided BotFather: create the bot, paste the token (stored encrypted, never shown), the wizard
   verifies + auto-configures it (commands/privacy).
2. **`/groups`** — the bot lists the groups it's now in; **tag the staff group** (single-occupancy roles).
3. **Staff** — three ways, mix freely:
   - **Discover-confirm** (easiest): the bot stages whoever posts in the staff group → **confirm each 1-by-1**
     into a staff record (`/onboard` in Telegram, or the candidates list).
   - **`/staff`** manual add/edit (name · role · senior · skills · hours incl. overnight + split).
   - **Bulk**: paste `Name, role, HH:MM-HH:MM, skill1;skill2` lines on `/staff`.
   - Silent staff can tap the bot's **`/start`** link → staged + consent Yes/No → confirmed.
4. **`/expertise`** — define skills + the minimum needed at all times (+ day/hour coverage overrides).
5. **`/customer`** — set the rules (attendance · leave · OT · approvals · the 5 domains). `/templates`
   pre-fills bakery/cafe/retail.
6. **`/setup`** — the checklist: **N of 5 done** (bot · staff group · staff · rules · **clear config
   warnings**); a **🎉 Ready to go live!** banner shows only when all five are green.

## The tools (admin nav)
| Page | What it does |
|---|---|
| `/setup` | onboarding checklist + go-live readiness |
| `/customer` | the editable customer view (draft → Apply) |
| `/bot` `/groups` `/staff` `/expertise` | the onboarding screens |
| `/templates` | one-click industry presets |
| `/whatif` | preview how a grace/early change would reclassify recent check-ins (read-only) |
| `/health` | config health-check — likely setup mistakes, read-only |
| `/audit` | who-changed-what-when (config change log) |
| `/export` `/import` | back up / clone a tenant's setup (readable diff + JSON; import is whitelist-safe) |

## Channels (daily use)
- **Telegram** — the staff bot (check-in/out, requests). The live TWB flow.
- **Web** — each staffer has a private `/checkin/<token>` link → one-tap **Check IN / Check OUT** (geolocation)
  + their **recent check-ins**. The "link" button per staffer on `/staff` reveals it. Records to the platform
  (`core`), never TWB's live attendance.

## Going live / cut-over
- The platform runs as a **shadow** beside live; the admin **cut-over dashboard** shows per-vertical agreement.
- Cut-over is **owner-gated** (flip per vertical only after days of real-data agreement). Check-in is READY but
  intentionally kept in shadow for now.

## Before exposing it publicly (W3 — owner-gated)
Set `ORG_SECRET_KEY` (encrypts the secret store) · turn on auth (`WIZARD_AUTH=1` + seed a user) · add CSRF +
HTTPS + login rate-limiting. Until then it stays localhost-only behind the SSH tunnel.
