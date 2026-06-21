# Bot Architecture — domain map + the GM→Accountant report restructuring

> **Approved 2026-06-21.** Target: **one bot per DOMAIN.** Move the daily REPORT (+ food money + the stock
> chat gateway) from the **GM** bot to the **Accountant** bot, so all MONEY/GOODS lives on one bot and GM
> becomes the People bot. It's a **live-money migration** → sequenced carefully, no gaps, no double-processing.

## Domain map (target)
| Bot | Domain it owns | Groups |
|---|---|---|
| **Accountant** | **Money & Goods** — receipts/expenses · vendors · the **daily REPORT** (sales/cash/ABA/drawer) · **food money** · **stock** (goods-in, counts, 3-way reconciliation) · payments (Bakong later) | Expenses TWB · **TWB REPORT** · Stock Checks |
| **GM** | **People** — attendance (check-in/out/location) · AL/sick/OT · points · lateness · schedule · supervisor/management tagging | Supervisors · Management · COMMS · staff group |
| **Retail** | **Customers** — orders (DM), production, customer comms | customer DMs |
| **B2B** | **Wholesale customers** (when re-enabled) | B2B groups |
| **Listener** | **Eyes** — streams all → `ops_messages`, price/account watch (silent) | all groups |
| **Hire** | **Hiring** | applicant DMs |
| **Stock worker** | headless AppSheet⇄Postgres sync (no chat) | — |

## Why this cut
- The report logic (`gm_bot/finance.py`, `reconcile.py`, `clarify.py`) is **pure + uncoupled** (no Telegram/DB
  in it) — so re-homing it is **re-wiring handlers, not a rewrite**.
- The stock tables (`acc_items`, `stock_movements`) are **already shared with the accountant** (goods-in flows
  from receipts), so stock's chat home belongs with the bot that owns the goods data.
- It **unifies food money**: with the report on the accountant, the food close-hook fires on the SAME bot →
  auto "post the list when the report is done," and the cross-bot/manual-finalize workaround is dropped.
- **Deploy isolation preserved/improved:** the whole reason the accountant is separate was to keep finance
  churn off **live attendance**. This strengthens it — all churny money/report/stock work sits on the
  accountant; GM is the stable People bot.

## What MOVES vs STAYS
- **MOVES → Accountant:** daily REPORT processing (parse · store `gm_daily_reports` · math-check · correct ·
  clarify ladder · AI fallback) · the **17:30 / 06:30 report watchdogs** · `reconcile` (photos vs report) ·
  receipt-checks in TWB REPORT · food-money close+post · the stock chat gateway.
- **STAYS on GM (do NOT touch — live HIGH-RISK staff path):** attendance · AL/sick/OT · points · lateness ·
  schedule · supervisor/management tagging.
- **Unchanged:** Retail = customers (DM, no customer *group*) · Listener = eyes · Hire = hiring · Stock
  worker = headless sync.

## Migration sequence (live money — NO gaps, careful order)
0. **(prereq, owner)** Walk the accountant on staging (V3/V3.5 + food) → it's deploy-ready.
1. **Deploy the accountant** as a live service (`twbshop-accountant`). It goes live for receipts/vendors/food
   (food gated). **The report is still on GM** at this point — nothing changes for reports yet.
2. **Build the report handling on the accountant** — import the pure `finance`/`reconcile`/`clarify` modules +
   `save_daily_report`; the watchdogs; the food close-hook. Prove it in the accountant's `is_test` mode.
3. **HAND-OFF (the careful swap, ONE deploy window):**
   a. Add the accountant to **TWB REPORT**.
   b. Deploy: **accountant report-handling ON, GM report-handling OFF — in the same window** (never both
      processing the same report).
   c. Verify: the accountant stores + math-checks a real report (`gm_daily_reports` written by the accountant).
   d. Remove the GM bot from TWB REPORT (or leave it silent there).
4. **Food money** close-hook now lives on the accountant (auto on report-store) — drop the manual-finalize.
5. **Stock chat gateway** GM→accountant (the worker stays headless).
6. **GM** is left = People.

## ⛔ Hand-off rule — the group swap is step 3, the LAST piece
Only ONE bot may process a report at a time. The swap **flips the code** (GM report-handling off / accountant
on) in the **same deploy window**; the group-membership change is cosmetic after that. **Removing GM / adding
the accountant to TWB REPORT BEFORE the accountant can process reports (and is deployed) leaves the live daily
report unprocessed — money tracking breaks.** So: do the group change only at step 3, on my go.

## Critical path right now
Everything is gated on the **accountant going live**, which is gated on the **owner's staging walk**. So the
immediate real-world step is the **accountant walk → deploy**; the report-handler build + the group swap follow.
