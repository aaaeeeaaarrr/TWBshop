"""core.ledger — the platform's atomic money mechanism (the over-book/double-bank bug-class, cured by
construction). Every balance move is ATOMIC-CLAIM-AT-THE-WRITE:

  • the settle is CLAIMED once — a status flip on the shift (`settled_at`) that RETURNs the row or nothing,
    so exactly one checkout settles it (a concurrent/auto/duplicate checkout claims nothing);
  • each balance change is ONE conditional SQL statement the DB applies whole or refuses — the CHECK
    constraints (paid≤owed, balance≥0) make an over-credit / over-debit impossible at the storage layer,
    not in the caller (which is exactly where live's bugs lived);
  • fully reversible (S1): settle ↔ reverse_settle, idempotent both ways.

SHADOW-ONLY — its own org-scoped core tables; live's money path is untouched. Uses the parity-proven
core.settle math for the amounts.
"""
import json

from shared.database import _db
from core.settle import settle_shift, BANK_CAP_MIN


def bank_balance(org_id, staff_id) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance_min FROM core_ot_bank WHERE org_id=%s AND staff_id=%s",
                        (org_id, staff_id))
            r = cur.fetchone()
            return r["balance_min"] if r else 0


def open_debt(org_id, staff_id):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT debt_id, owed_min, paid_min FROM core_payback_debts "
                        "WHERE org_id=%s AND staff_id=%s AND status='open' ORDER BY debt_id LIMIT 1",
                        (org_id, staff_id))
            return cur.fetchone()


def add_debt(org_id, staff_id, owed_min) -> int:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_payback_debts (org_id, staff_id, owed_min) VALUES (%s,%s,%s) "
                        "RETURNING debt_id", (org_id, staff_id, int(owed_min)))
            return cur.fetchone()["debt_id"]


def settle_checkout(org_id, staff_id, shift_id, worked_min, normal_len_min,
                    bank_cap_min: int = BANK_CAP_MIN) -> dict:
    """Claim the shift (settle-once), compute OT/payback (core.settle), apply atomically. Idempotent:
    a second call — or a crash-redelivered duplicate — claims nothing and moves no money. A per-STAFF
    advisory lock serializes the read→compute→apply, so two of one staff's shifts (split/overnight)
    settling at once can't both read a stale bank/debt and over-bank or double-credit (LEDGER-CAP /
    LEDGER-PHANTOM, s55 audit)."""
    with _db() as conn:
        with conn.cursor() as cur:
            # 1) ATOMIC CLAIM — exactly one settle per shift; a loser gets nothing (no double-bank).
            cur.execute("UPDATE shifts SET settled_at=NOW() WHERE shift_id=%s AND settled_at IS NULL "
                        "RETURNING shift_id", (shift_id,))
            if not cur.fetchone():
                return {"claimed": False, "reason": "already settled"}
            # Serialize THIS staff's money moves for the txn — concurrent settles (different shifts, same
            # person) now run one-at-a-time, so each reads the other's COMMITTED bank/debt, not a stale one
            # (same proven lock-key the live system uses). FOR UPDATE row-locks the read rows too.
            cur.execute("SELECT pg_advisory_xact_lock(911, %s)", (staff_id,))
            cur.execute("SELECT debt_id, owed_min, paid_min FROM core_payback_debts "
                        "WHERE org_id=%s AND staff_id=%s AND status='open' ORDER BY debt_id LIMIT 1 "
                        "FOR UPDATE", (org_id, staff_id))
            debt = cur.fetchone()
            pb_balance = (debt["owed_min"] - debt["paid_min"]) if debt else 0
            cur.execute("SELECT balance_min FROM core_ot_bank WHERE org_id=%s AND staff_id=%s FOR UPDATE",
                        (org_id, staff_id))
            br = cur.fetchone()
            bank = br["balance_min"] if br else 0
            # 2) compute (parity-proven math) — caps pb_cleared at the debt and ot_banked at bank room
            s = settle_shift(worked_min, normal_len_min, pb_balance, bank, bank_cap_min)
            # 3) apply atomically; the CHECK constraints refuse any over-move structurally.
            pb_applied = 0
            if s["pb_cleared"] > 0 and debt:
                cur.execute("UPDATE core_payback_debts SET paid_min = paid_min + %s, "
                            "status = CASE WHEN paid_min + %s >= owed_min THEN 'cleared' ELSE 'open' END "
                            "WHERE debt_id=%s AND status='open' RETURNING debt_id",
                            (s["pb_cleared"], s["pb_cleared"], debt["debt_id"]))
                pb_applied = s["pb_cleared"] if cur.fetchone() else 0   # record ONLY what actually applied
            if s["ot_banked"] > 0:
                # LEAST(cap, …) is a structural belt: the bank can never exceed the cap even if a future
                # caller skips the lock. Under the lock the value is already within cap (this is a no-op).
                cur.execute("INSERT INTO core_ot_bank (org_id, staff_id, balance_min) VALUES (%s,%s,%s) "
                            "ON CONFLICT (org_id, staff_id) DO UPDATE SET "
                            "balance_min = LEAST(%s, core_ot_bank.balance_min + EXCLUDED.balance_min), "
                            "updated_at=NOW()", (org_id, staff_id, s["ot_banked"], bank_cap_min))
            # the event records the TRUE applied pb_cleared (not the pre-computed value) so reverse_settle
            # can never un-credit a payment a concurrent settle had already cleared (S4 + S1).
            s = {**s, "pb_cleared": pb_applied}
            detail = {"worked": worked_min, "debt_id": (debt["debt_id"] if debt else None), **s}
            cur.execute("INSERT INTO attendance_events (org_id, shift_id, staff_id, type, at, detail) "
                        "VALUES (%s,%s,%s,'settled',NOW(),%s)",
                        (org_id, shift_id, staff_id, json.dumps(detail)))
            return {"claimed": True, **detail}


def buyback_spend(org_id, staff_id, minutes) -> int | None:
    """Take REST back from the bank — atomic conditional debit. Refuses an over-spend or a double-tap
    (returns None, banks nothing). The platform form of the F1 OT-buyback fix."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_ot_bank SET balance_min = balance_min - %s, updated_at=NOW() "
                        "WHERE org_id=%s AND staff_id=%s AND balance_min >= %s RETURNING balance_min",
                        (int(minutes), org_id, staff_id, int(minutes)))
            r = cur.fetchone()
            return r["balance_min"] if r else None


def reverse_settle(org_id, shift_id) -> dict:
    """The clean inverse (S1) — undo exactly what THIS settle did, idempotently: clear the claim, refund
    the bank (never below 0), un-credit the exact debt. A second call reverses nothing."""
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE shifts SET settled_at=NULL WHERE shift_id=%s AND settled_at IS NOT NULL "
                        "RETURNING staff_id", (shift_id,))
            row = cur.fetchone()
            if not row:
                return {"reversed": False, "reason": "not settled"}
            staff_id = row["staff_id"]
            cur.execute("SELECT detail FROM attendance_events WHERE shift_id=%s AND type='settled' "
                        "ORDER BY event_id DESC LIMIT 1", (shift_id,))
            ev = cur.fetchone()
            d = (ev["detail"] if ev else {}) or {}
            ot, pb, debt_id = int(d.get("ot_banked", 0)), int(d.get("pb_cleared", 0)), d.get("debt_id")
            if ot > 0:
                cur.execute("UPDATE core_ot_bank SET balance_min = GREATEST(0, balance_min - %s), "
                            "updated_at=NOW() WHERE org_id=%s AND staff_id=%s", (ot, org_id, staff_id))
            if pb > 0 and debt_id:
                cur.execute("UPDATE core_payback_debts SET paid_min = GREATEST(0, paid_min - %s), "
                            "status='open' WHERE debt_id=%s", (pb, debt_id))
            cur.execute("INSERT INTO attendance_events (org_id, shift_id, staff_id, type, at, detail) "
                        "VALUES (%s,%s,%s,'settle_reversed',NOW(),%s)",
                        (org_id, shift_id, staff_id, json.dumps({"ot_refunded": ot, "pb_uncredited": pb})))
            return {"reversed": True, "ot_refunded": ot, "pb_uncredited": pb}
