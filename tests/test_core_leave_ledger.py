"""core.leave_ledger — the atomic AL-balance mechanism. Proves S1 deduct↔refund: deduct-once,
refund-once, exact reversal (deduct+refund nets to zero), and the refund reads the FROZEN total even if
the schedule changes after approval. Real staging DB; cleaned up."""
import core.db as cdb
from core import leave_ledger as ll
from shared.database import _db

ORG = "test_alledger"


def _setup():
    cdb.init_core_db()
    cdb.ensure_org(ORG, "Test")
    _clean()


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_al_requests WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM core_al_balance WHERE org_id=%s", (ORG,))


def test_deduct_once_and_refund_once_exact_reversal():
    _setup()
    try:
        ll.set_al_balance(ORG, 1, 10.0)
        # 3 selected days, Sunday off → 2 charged (the frozen map excludes the day-off)
        req, total = ll.create_al_request(ORG, 1, ["2026-06-26", "2026-06-27", "2026-06-28"],
                                           day_off="Sunday")
        assert total == 2.0
        assert ll.al_approve_and_deduct(ORG, req)["deducted"] == 2.0
        assert ll.al_balance(ORG, 1) == 8.0
        # idempotent approve — no double-deduct
        assert ll.al_approve_and_deduct(ORG, req)["applied"] is False
        assert ll.al_balance(ORG, 1) == 8.0
        # cancel refunds EXACTLY the frozen total → balance restored
        assert ll.al_cancel_and_refund(ORG, req)["refunded_days"] == 2.0
        assert ll.al_balance(ORG, 1) == 10.0
        # idempotent cancel — no double-refund
        assert ll.al_cancel_and_refund(ORG, req)["refunded"] is False
        assert ll.al_balance(ORG, 1) == 10.0
    finally:
        _clean()


def test_refund_reads_frozen_total_not_recomputed():
    _setup()
    try:
        ll.set_al_balance(ORG, 2, 5.0)
        # half-day hours AL: frozen at 0.5/day × 2 charged days = 1.0
        req, total = ll.create_al_request(ORG, 2, ["2026-06-23", "2026-06-24"], kind="hours",
                                          frac_per_day=0.5)
        assert total == 1.0
        ll.al_approve_and_deduct(ORG, req)
        assert ll.al_balance(ORG, 2) == 4.0
        # even if we corrupt what a re-computation WOULD give, the refund uses the frozen row total (1.0)
        with _db() as c:
            with c.cursor() as cur:
                cur.execute("UPDATE core_al_requests SET days=%s WHERE req_id=%s",
                            ('["2026-06-23"]', req))   # pretend the selection shrank
        assert ll.al_cancel_and_refund(ORG, req)["refunded_days"] == 1.0   # frozen, not 0.5
        assert ll.al_balance(ORG, 2) == 5.0
    finally:
        _clean()
