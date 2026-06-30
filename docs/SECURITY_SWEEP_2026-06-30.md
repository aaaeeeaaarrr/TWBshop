# Exhaustive Security & Structural Sweep — 2026-06-30

**Why:** a shallow audit. Asked to stop the client GM bot sending BUILDER/system messages, I fixed the one
file I was shown and missed a whole class (3 cron/service leaks). The owner (rightly) demanded a real sweep
and a systemic fix so this can't recur. This is that sweep: **4 parallel read-only audits**, one per
structural law, then fixes for the leak-class + guard tests + this enumerated record. The new standing rule
that should have prevented it: the **DRASTIC / STRUCTURAL-CHANGE PROTOCOL** in CLAUDE.md (sweep the CLASS,
leave a guard, never fix the one instance).

**Headline verdict:** the **live production core is sound** — `core/*` is org-scoped (173 query sites
verified), the live bots don't leak internals to users (errors go to the Monitor), no committed/hardcoded
secrets, no active secret-in-log leak. **Every serious finding is a pre-public ("W3") or multi-client
structural gap, mitigated TODAY** by: the wizard binding `127.0.0.1` only (SSH-tunnel = the auth) +
single-tenant-per-process + the live bots being the only internet-reachable surface (and they're clean).
None is exploitable by a real client right now. They become live the moment the wizard/web surface is
exposed publicly or serves multiple tenants — which is the explicit roadmap, so they must be closed first.

---

## FIXED in this sweep (the leak-class + additive hardening — all shipped)
- **Sep-F1 — `_test_watchdog_job` (gm) DM'd the owner via the client GM bot** + skipped the durable sink
  (its live sibling correctly used `_alarm`→Monitor). Same class as the already-fixed leaks; the raw-POST
  guard couldn't see it (in-process PTB send). **Fixed → `_alarm` (Monitor + sink).**
- **Sep-F4 — hire `assessment_pipeline.py` DM'd a pipeline-failure error via the client hire bot.**
  **Fixed → `shared.monitor_notify.notify_monitor`.**
- **Sec-1 — `run_automations.py` (handles live bot tokens) lacked log redaction.** **Fixed →
  `install_log_hygiene()`.**
- **Guard extended:** `tests/test_client_builder_separation.py` now also fails on a builder-keyword owner-DM
  via a client bot (the in-process PTB class), and locks Sep-F1/F4. (The raw-POST class was already guarded.)

**UPDATE 2026-06-30 — W3 #1 DONE:** the wizard **builder-vs-customer auth role** (the security core of Sep-F3
+ DL-F1) is now BUILT + tested — deny-by-default `_guard` (a customer is 403'd from the builder/cut-over
console), role-aware login, `'owner'`-alias anti-lockout, and the `← admin`/`admin` nav links hidden from
customer pages. Wizard-only, INERT until `WIZARD_AUTH=1`; `tests/test_wizard_roles.py` (8). Owner-gated
activation: seed a builder + flip `WIZARD_AUTH=1`. ⚠ a client user MUST be created `role='customer'`. The
items below are the REMAINING W3 work (each still localhost-mitigated).

**UPDATE 2026-06-30 — W3 #2 DONE (auth FAIL-CLOSED + PII behind authz):** three invariants now hold in the
single HTTP chokepoint (`wizard/app.py::_guard`), all INERT for the owner's localhost/tunnel workflow:
- **TI-F1 fixed** — `_is_loopback_request()` (real TCP peer, never a spoofable `X-Forwarded-For`); with auth
  OFF a NON-loopback request is `403`'d, so an accidental public / `0.0.0.0` bind without `WIZARD_AUTH=1`
  can't expose the console. Today's bind (127.0.0.1 + tunnel → every peer is loopback) is unchanged.
- **TI-F2 fixed** — the no-user bootstrap window is now DENY-CLOSED (auth ON + 0 users → everything → `/login`,
  not wide-open). No lockout: the first builder is seeded server-side via `core.db.create_user(...)` (CLI), and
  `/login` shows a bootstrap hint.
- **TI-F5 fixed** — `_pii_authorized()` gates the 6 PII fields (national_id · passport · tax_id · SSN · address
  · bank): an unauthorized session sees a masked, name-less field (raw value never emitted) AND a server-side
  belt in `/staff/update` strips `_SENSITIVE_PII` from a non-authorized POST (can't overwrite). Encryption-at-rest
  is already built — the owner just sets `ORG_SECRET_KEY`. Guard: `tests/test_wizard_auth_failclosed.py` (11).

## PARKED — pre-public ("W3") / multi-client structural (mitigated now by localhost + single-tenant)
Tracked here + in `docs/PENDING_WORK.md`. Each is owner-gated (some need a role system / public hardening).

### Tenant isolation (wizard) — the real cross-tenant gate, all behind the localhost bind today
- **TI-F1 ✅ FIXED 2026-06-30** — loopback fail-closed in `_guard` (auth OFF → a non-loopback peer is 403'd).
- **TI-F5 ✅ FIXED 2026-06-30** — PII behind `_pii_authorized()` (masked render + server-side write belt); set `ORG_SECRET_KEY` to encrypt at rest (already built).
- **TI-F3 (HIGH@multi-tenant)** session has no org binding (`app.py:2145`); at multi-tenant, store + re-check `org_id` per request, never trust host/path. **← NEXT W3 pass.**
- **TI-F2 ✅ FIXED 2026-06-30** — the no-user bootstrap window is deny-closed (→ `/login`), only a CLI-seeded builder gets in.
- **TI-F4 (MED)** no CSRF on state-changing POSTs (apply/staff-del/payroll-run/till-close…).
- **TI-F6 (LOW/MED)** public token check-in routes un-rate-limited (isolation itself is correct: org is token-derived).
- **TI-F7 (LOW)** 2 latent cross-org queries not route-reachable (`core/shadow.py:68,168`) — scope before exposing.

### Client data-leakage (wizard / inert web adapter)
- **DL-F1 (MED→HIGH@public)** the `/customer` view links into the internal admin/`/shadow` console (badges,
  cut-over %, engine live-vs-new diffs); customer pages hard-link `← admin`. Needs a builder-vs-customer role.
- **DL-F2 (MED)** raw exception text shown on the staff web check-in (`app.py:1902/1916`) — return a generic msg.
- **DL-F3 (MED, inert)** the web adapter lets the client override the verdict via the request body
  (`adapters/web.py:33` → `core/channel.py:23`) — ignore client config on any served path.
- **DL-F4/F5 (LOW)** `shift_id`/internal ids in the inert web-adapter JSON + owner-only pages.

### Client/builder separation — completeness (structural, multi-client)
- **Sep-F3 (HIGH@public)** the wizard has NO builder-vs-customer auth ROLE (`app.py:2150`); a logged-in client
  would VIEW `/shadow` cut-over internals. (Read-only — no flip is operable from the wizard; flips are CLI.)
- **Sep-F2 / Cat-2 (MED→HIGH@multi-client)** the monitoring JOBS (watchdog/sentinel/shadow-digest/auto-audit)
  + the flip/shadow/transition engine run INSIDE the client gm bot process. Output is now Monitor-routed; the
  JOBS themselves move to a builder monitor service at multi-client (CLAUDE.md backlog #1/#4).

### Secrets — LOW / defense-in-depth
- `run_wizard.py` / `run_stock.py` lack `install_log_hygiene` (no tokens there today → low) — add for consistency.
- The redaction regex scrubs bot-tokens only, not `DATABASE_URL` / `sk-ant-` (latent — nothing logs those today).
- `secrets.py` shadows the stdlib `secrets` module (known, worked around with `os.urandom`).

---

## Guard tests now enforcing these laws (so they can't silently regress)
- `tests/test_client_builder_separation.py` — raw-POST class + in-process PTB builder-keyword class + the 5+2 fixes.
- `tests/test_web_adapter.py` — the web adapter rejects a body `org_id` (the correct tenant pattern).
- `tests/test_wizard_viewer.py` — `/customer/config` leaks no internal badges + never shows a secret value.
- **Recommended next guards (when the parked items are fixed):** every long-running entrypoint installs
  redaction; no route reads tenant identity from the request; with `WIZARD_AUTH=1` a non-builder session is
  403'd from `/` and `/shadow`; the `/customer` dashboard contains no admin/`/shadow` links or badges; a
  two-org integration test proving every `core` read/write is org-scoped.

## Prioritized order before any public / multi-client exposure (W3)
1. Wizard **builder-vs-customer role** (Sep-F3 + DL-F1) — gate `/`, `/shadow`, `/whatif`, badges, cut-over;
   strip `← admin` from customer pages. *The one place a client could see builder machinery.*
2. ✅ **DONE — Auth fail-closed + PII behind authz** (TI-F1, TI-F2, TI-F5); `ORG_SECRET_KEY` is owner-gated.
3. **Session↔org binding** (TI-F3) — the actual cross-tenant gate at multi-tenant. **← NEXT.**
4. **CSRF + rate-limit + HTTPS** (TI-F4, TI-F6); generic web-checkin errors (DL-F2); strip web-adapter
   client-config override + `shift_id` (DL-F3/F4).
5. **Move the monitoring jobs to a builder service** (Sep-F2) at multi-client.
6. Secrets LOW consistency (wizard/stock redaction, regex extension).
