"""B2B money-path safety (the F2/F3/F4 fixes) — prove no double-credit before re-enable. Staging; a throwaway
test group; cleaned up. B2B is DISABLED in prod; this locks the fix in for the joint re-enable session."""
from shared.database import (_db, init_db, save_markpaid_request, claim_markpaid_request,
                             save_b2b_payment, apply_b2b_payment_writes, get_b2b_customer_credit)

init_db()
GRP = -999777            # a throwaway test group id (no collision with real groups)


def _clean():
    with _db() as conn:
        with conn.cursor() as cur:
            for t in ("b2b_payments", "b2b_orders", "b2b_markpaid_requests", "b2b_customers"):
                cur.execute(f"DELETE FROM {t} WHERE group_chat_id = %s", (GRP,))


def test_f4_claim_once_blocks_double_credit():
    # The double-tap vector: two confirm taps on one request. claim is a CAS → exactly one wins → apply runs once.
    _clean()
    try:
        rid = save_markpaid_request(GRP, "TestCo", 12345)            # status 'draft'
        first = claim_markpaid_request(rid)
        second = claim_markpaid_request(rid)
        assert first is not None and first["status"] == "approved"   # the first tap claims it
        assert second is None                                        # the second tap gets nothing → no 2nd apply
    finally:
        _clean()


def test_f3_redelivery_dedups():
    # A redelivered/duplicate payment photo (same group + file id) must record ONCE (the save is the claim).
    _clean()
    try:
        id1 = save_b2b_payment(GRP, "TestCo", 50.0, None, group_message_id=None, tg_file_unique_id="FILE_X")
        id2 = save_b2b_payment(GRP, "TestCo", 50.0, None, group_message_id=None, tg_file_unique_id="FILE_X")
        assert id1 is not None and id2 is None                       # 2nd no-ops → caller skips apply_payment
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) n FROM b2b_payments WHERE group_chat_id=%s AND tg_file_unique_id=%s",
                            (GRP, "FILE_X"))
                assert cur.fetchone()["n"] == 1                      # exactly one payment row
    finally:
        _clean()


def test_f2_writes_are_atomic_together():
    # The three money writes (orders paid + credit) commit as one — an order isn't paid without the credit move.
    _clean()
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO b2b_customers (group_chat_id, business_name, updated_at, credit) "
                            "VALUES (%s,'TestCo','now',0)", (GRP,))
                cur.execute("INSERT INTO b2b_orders (group_chat_id, business_name, item, created_at, payment_status) "
                            "VALUES (%s,'TestCo','bread','now','unpaid') RETURNING id", (GRP,))
                oid = cur.fetchone()["id"]
        apply_b2b_payment_writes([oid], [], GRP, 5.0)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payment_status FROM b2b_orders WHERE id=%s", (oid,))
                assert cur.fetchone()["payment_status"] == "paid"
        assert get_b2b_customer_credit(GRP) == 5.0                   # order paid AND credit set, one txn
    finally:
        _clean()
