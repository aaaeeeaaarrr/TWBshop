"""core.leave_ledger — the atomic AL-balance mechanism (S1: deduct-at-approval ↔ refund-on-cancel).

The per-day deduction is FROZEN once (core.leave.al_deduction_map) when the request is created. Approval
deducts that frozen total atomically (status flip pending→approved FIRST, then the balance move); cancel
refunds the SAME frozen total — it reads the request row, never recomputes (so a schedule change after
approval can't change the refund). Deduct-once + refund-once + exact reversal. SHADOW-ONLY (own tables).
"""
import json

from shared.database import _db
from core.leave import al_deduction_map


def set_al_balance(org_id, staff_id, days) -> None:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_al_balance (org_id, staff_id, days_remaining) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id, staff_id) DO UPDATE SET days_remaining=EXCLUDED.days_remaining",
                        (org_id, staff_id, days))


def al_balance(org_id, staff_id) -> float:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT days_remaining FROM core_al_balance WHERE org_id=%s AND staff_id=%s",
                        (org_id, staff_id))
            r = cur.fetchone()
            return float(r["days_remaining"]) if r else 0.0


def create_al_request(org_id, staff_id, days_list, kind="days", frac_per_day=1.0,
                      day_off=None, non_working=None, no_deduct=False):
    """Freeze the per-day deduction map (S1) on a new pending request. Returns (req_id, total)."""
    dmap, total = al_deduction_map(days_list, kind, frac_per_day, day_off, non_working, no_deduct)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_al_requests (org_id, staff_id, days, deduction, total) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING req_id",
                        (org_id, staff_id, json.dumps(days_list), json.dumps(dmap), total))
            return cur.fetchone()["req_id"], total


def al_approve_and_deduct(org_id, req_id) -> dict:
    """Atomic: claim the request (pending→approved, returns the FROZEN total or nothing), then deduct that
    total from the balance. A second call claims nothing → no double-deduct."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_al_requests SET status='approved' "
                        "WHERE req_id=%s AND org_id=%s AND status='pending' RETURNING staff_id, total",
                        (req_id, org_id))
            row = cur.fetchone()
            if not row:
                return {"applied": False, "reason": "not pending"}
            cur.execute("INSERT INTO core_al_balance (org_id, staff_id, days_remaining) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id, staff_id) DO UPDATE SET "
                        "days_remaining = core_al_balance.days_remaining - EXCLUDED.days_remaining, "
                        "updated_at=NOW()", (org_id, row["staff_id"], row["total"]))
            return {"applied": True, "deducted": float(row["total"])}


def al_cancel_and_refund(org_id, req_id) -> dict:
    """Atomic: claim the cancel (approved→cancelled, returns the FROZEN total), then refund EXACTLY that
    total (read from the row — never recomputed). A second call claims nothing → no double-refund."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_al_requests SET status='cancelled' "
                        "WHERE req_id=%s AND org_id=%s AND status='approved' RETURNING staff_id, total",
                        (req_id, org_id))
            row = cur.fetchone()
            if not row:
                return {"refunded": False, "reason": "not approved"}
            cur.execute("UPDATE core_al_balance SET days_remaining = days_remaining + %s, updated_at=NOW() "
                        "WHERE org_id=%s AND staff_id=%s", (row["total"], org_id, row["staff_id"]))
            return {"refunded": True, "refunded_days": float(row["total"])}
