"""Stock lane — a HEADLESS worker (no chat bot).

Architecture (locked session 43): Postgres is the source of truth; staff use the ONE GM bot's
gateway button -> AppSheet for paperless counts; this lane keeps Postgres <-> AppSheet in sync and
computes the reorder list on a cron. It owns no Telegram surface.

The accountant <-> stock seam is DATA, not code: both lanes import the shared helpers in
`shared.stock_shared` (acc_items catalog + the append-only stock_movements ledger). Neither lane
edits the other's code. See docs/REPORT_SYSTEM_DESIGN.md E6/E7/E11.
"""
