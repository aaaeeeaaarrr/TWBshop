"""AppSheet <-> Postgres sync (stock lane worker).

ARCH RULE 2 (interface-first): the AppSheet HTTP client is a STUB. C2's first unknown to prove is
**AppSheet <-> DO-Postgres connectivity**, which is owner-side (AppSheet binding directly to the DO
Postgres vs syncing via the AppSheet API + key). The approach decides what `AppSheetClient` does, so
it stays a contract for now and fails LOUDLY rather than silently no-op'ing.

The Postgres SIDE is built + tested today and is needed under EITHER approach:
  - `apply_count` turns a staff count into a `stock_movements` row (on-hand reconciliation);
  - `pull_overview` is the data AppSheet consumes (= `catalog.overview`).

State-integrity (S5): on-hand is an append-only ledger with ONE resolver. A count never mutates a
running total — it appends the delta (counted - current). Re-applying the SAME count appends nothing
(delta 0), so the sync is safe to re-run.
"""
from __future__ import annotations

from shared import stock_shared as ss
from stock import catalog


class AppSheetClient:
    """Contract for the AppSheet side. Unwired until connectivity is confirmed (C2, owner).

    Construct with credentials from secrets once the approach is chosen; `configured` lets the worker
    skip the sync (and just compute reorder) until then, instead of crashing the cron."""

    def __init__(self, app_id: str | None = None, api_key: str | None = None):
        self.app_id = app_id
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.api_key)

    def fetch_counts(self) -> list[dict]:
        """Pull new count rows from AppSheet -> [{item_id, counted_qty, ref_id?, note?}]."""
        raise NotImplementedError(
            "AppSheet client not wired — confirm AppSheet<->DO-Postgres connectivity (C2).")

    def push_overview(self, rows: list[dict]) -> None:
        """Push the catalog overview (catalog.overview()) to AppSheet."""
        raise NotImplementedError(
            "AppSheet client not wired — confirm AppSheet<->DO-Postgres connectivity (C2).")


def apply_count(item_id: int, counted_qty, *, is_test: bool = False,
                source: str = "count", ref_id: int | None = None,
                note: str | None = None) -> dict:
    """Reconcile on-hand to a physical count by APPENDING the delta as a 'counted' movement.
    The count is truth at count time; delta = counted - current on-hand. A matching count appends
    nothing (delta 0). Returns {item_id, before, counted, delta, movement_id}."""
    before = ss.on_hand(item_id, is_test=is_test)
    delta = float(counted_qty) - before
    movement_id = None
    if delta != 0:
        item = ss.get_item(item_id)
        movement_id = ss.add_movement(
            item_id, delta, reason="counted", unit=(item or {}).get("unit"),
            source=source, ref_id=ref_id, note=note, is_test=is_test)
    return {"item_id": item_id, "before": before, "counted": float(counted_qty),
            "delta": delta, "movement_id": movement_id}


def apply_counts(rows: list[dict], *, is_test: bool = False, source: str = "count") -> list[dict]:
    """Apply many counts. rows: [{item_id, counted_qty, ref_id?, note?}]."""
    return [apply_count(r["item_id"], r["counted_qty"], is_test=is_test, source=source,
                        ref_id=r.get("ref_id"), note=r.get("note")) for r in rows]


def pull_overview(is_test: bool = False) -> list[dict]:
    """The data AppSheet consumes (catalog + on-hand + low flag)."""
    return catalog.overview(is_test=is_test)


def run_sync(client: AppSheetClient, *, is_test: bool = False) -> dict:
    """One sync pass. No-op (skipped) until the client is configured. Returns a small summary."""
    if not client.configured:
        return {"synced": False, "reason": "AppSheet client not configured"}
    incoming = client.fetch_counts()
    results = apply_counts(incoming, is_test=is_test)
    client.push_overview(pull_overview(is_test=is_test))
    return {"synced": True, "counts_applied": len(results),
            "changed": sum(1 for r in results if r["delta"] != 0)}
