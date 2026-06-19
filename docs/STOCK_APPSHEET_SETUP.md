# Stock ↔ AppSheet — setup runbook (C2 deliverable)

This is the stock lane's hand-off to the owner: how to stand up the AppSheet staff stock-count app
over the Postgres source-of-truth, and the one config that lights up the whole feature. Everything
on the Postgres side is built + staging-proven; the steps below are the owner-side clicks that only
you can do (your AppSheet/Google account + the DO database).

> **Status:** Postgres side DONE (catalog · count events · reconcile worker · GM gateway button all
> built, behind the switch). The AppSheet app itself does NOT exist yet — that's the C2 "first
> unknown to prove: AppSheet ↔ DO-Postgres connectivity." This runbook resolves it.

---

## 0. SECURITY FIRST — read before connecting anything (auto-bedrock: this touches payroll)

The DigitalOcean Postgres holds **payroll, staff records, attendance, and payments** alongside stock.
Connecting AppSheet (a third-party Google SaaS) to that database is a real exposure. The rule, no
exceptions:

- **AppSheet gets a DEDICATED least-privilege role**, granted ONLY:
  - `SELECT` on `acc_items` (read the catalog),
  - `SELECT, INSERT, UPDATE` on `stock_count_events` (staff write counts).
  - **Nothing else.** No access to `staff_registry`, `slips`, `pays`, `acc_payments`, attendance,
    `stock_movements`, or any other table.
- So even if the AppSheet credentials leak, the blast radius is "read the item list, write counts" —
  never payroll. The reconcile worker (server-side, full creds) is what turns counts into ledger
  movements; AppSheet never touches `stock_movements` or money.
- Prefer the **API path (Option B)** if you want the database endpoint to stay fully private — it
  keeps AppSheet off the DB entirely. Choose direct-bind (Option A) only with the scoped role above.

Least-privilege role (run as the DB admin, on **staging first**, then prod at go-live — destructive-
SQL-guarded, so you run it manually):

```sql
CREATE ROLE appsheet_stock LOGIN PASSWORD '<a-strong-unique-password>';
GRANT CONNECT ON DATABASE <dbname> TO appsheet_stock;
GRANT USAGE ON SCHEMA public TO appsheet_stock;
GRANT SELECT ON acc_items TO appsheet_stock;
GRANT SELECT, INSERT, UPDATE ON stock_count_events TO appsheet_stock;
GRANT USAGE, SELECT ON SEQUENCE stock_count_events_id_seq TO appsheet_stock;
-- explicitly NOTHING on staff_registry / pays / slips / acc_payments / stock_movements / etc.
```
Put that password in the secrets repo (`bootstrap.py --push-secrets`), never in a tracked file.

---

## 1. The architecture (recap)

```
 Staff phone ──tap──> GM bot gateway button ──link──> AppSheet stock app
                         (gm_bot/stock_gateway.py)        │
                                                          │ writes a count row
                                                          ▼
                                              Postgres: stock_count_events  (reconciled=false)
                                                          │
                              run_stock.py (cron) ── reconcile_counts() ──> stock_movements (on-hand)
                                                          │
                              acc_items (catalog)  ◀── seeded; AppSheet reads it
```
- **Postgres = source of truth.** AppSheet is a throwaway front-end (decision: keep our Postgres).
- **GM owns no stock data** — it only shows the link button (hidden until the URL is set).
- **The stock worker** seeds the catalog, reconciles counts into on-hand, and computes reorder.

---

## 2. The two connectivity options

| | **A. Direct DB bind** | **B. AppSheet API** |
|---|---|---|
| AppSheet reads/writes | the DO Postgres directly (scoped role) | its own storage; our worker syncs via the AppSheet API |
| DB exposure | endpoint reachable by AppSheet (mitigate with the scoped role + trusted sources) | **none — DB stays private** |
| Our code to wire | none (worker reconcile already handles it) | `AppSheetClient.fetch_counts/push_overview` + an API key in secrets |
| Moving parts | fewest | more (API polling, key management) |
| Recommendation | OK **only** with the least-privilege role | best if you want zero DB exposure |

Pick one and tell me; both are supported by the code already shipped. **A** is less code; **B** is
more isolated. Either way the staff experience and the GM button are identical.

---

## 3. Owner steps — Option A (direct bind)

1. **Create the scoped DB role** (§0) on staging.
2. In AppSheet: **Create app → start with data → Database (PostgreSQL)**. Enter the DO host, port,
   database, and the `appsheet_stock` user/password. Enable SSL. (If the DO database firewall uses
   "trusted sources," add AppSheet's connection — see AppSheet's PostgreSQL docs for current IPs, or
   confirm whether your DO plan allows it; flag me if this is the blocker.)
3. Add the two tables: `acc_items` (read-only) and `stock_count_events`.
4. Build the count view: a list grouped by `acc_items.category`; tapping an item runs an action that
   **adds a `stock_count_events` row** with: `item_id` = the item, `counted_qty` = the typed number,
   `count_date` = `TODAY()`, `unit` = the item's unit, `source` = `appsheet`, `is_test` = `false`,
   `reconciled` = `false`. (Leave `movement_id` empty — the worker fills it.)
5. **Share / get the app link** (the web or install URL).
6. Set it where the GM bot reads it and restart gm (no code change, no redeploy):
   - server: add `STOCK_APPSHEET_URL=https://...` to the `twbshop-gm` systemd drop-in (next to
     `TWBSHOP_ENV`), then `systemctl restart twbshop-gm`.
   - staging/local: `export STOCK_APPSHEET_URL=https://...` (or set it in `config.py`).
7. **Schedule the worker** (cron): `TWBSHOP_ENV=… python run_stock.py` every ~10–15 min (reconcile +
   reorder), and once `python run_stock.py --seed` to seed the catalog on the target DB.

## 3b. Owner steps — Option B (API), the deltas
Steps 1–2 become: create the AppSheet app on its own storage; generate an **API key + app id**, put
them in secrets (`bootstrap.py --push-secrets`). Then tell me — I wire `AppSheetClient.fetch_counts`
(pull counts → `apply_count`) and `push_overview` (catalog → AppSheet). Steps 4–7 are the same; the
worker uses the API instead of the reconcile-from-DB pass.

---

## 4. Verify it works (real-path)

1. **Gateway lights up:** after step 6, a staffer opens the GM menu → the "📦 Stock count" button is
   now visible (it was hidden while `STOCK_APPSHEET_URL` was empty). Tapping it opens the app.
2. **A count flows to on-hand:** enter a count for one item in AppSheet → within one worker tick the
   log shows `Reconciled N direct count(s)` and `on_hand` for that item equals the counted figure
   (`from shared import stock_shared as ss; ss.on_hand(item_id)`), with a `counted` row in
   `stock_movements`. Do this on **staging** first.
3. **Reorder:** `python run_stock.py` logs the reorder list for anything below `min_qty`.

---

## 5. Data contract (what AppSheet binds to)

- **`acc_items`** (read): `id, name, category, unit, min_qty, reorder_qty, active`. Catalog; seeded
  from the 50-item list (`stock/catalog_data.py`), idempotent (`run_stock.py --seed`). The owner's
  full ~143-item sheet supersedes it later.
- **`stock_count_events`** (read/write): `item_id → acc_items, counted_qty, unit, count_date,
  source, ref_id, note, reconciled, is_test`. One row per item per day (a re-count updates it).
  AppSheet sets `reconciled=false`; the worker sets it true after creating the ledger movement.
- AppSheet must **never** see `stock_movements`, `acc_payments`, or any payroll/staff table.

When the accountant lane's 3-way reconciliation (Phase D2) needs counted figures, `stock_count_events`
is promoted to the shared seam via an integrator step — not by reaching across lanes.
