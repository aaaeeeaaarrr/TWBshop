"""OT-rest buyback over-book guard (owner 'never again', Jun 22 — the twin of the payback over-book).

ot_bank_claim_spend is an ATOMIC conditional debit: it spends ONLY if the bank covers it, defeating both
over-spend and a double-tap (the 2nd claim finds the bank already debited). Real staging DB, cleaned up.
"""
import shared.database as db


def _staff_id():
    """Self-provision a dedicated test staffer (idempotent; ex_staff) so this money guard can NEVER silently
    skip on a fresh/empty staging DB (s55 GUARD-SKIP fix)."""
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO staff_registry (canonical_name, status) "
                        "VALUES ('__guard_test_staff__','ex_staff') "
                        "ON CONFLICT (canonical_name) DO UPDATE SET status='ex_staff' RETURNING id")
            return cur.fetchone()["id"]


def _set_bank(sid, bal):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO ot_bank (staff_id, balance_min) VALUES (%s,%s) "
                        "ON CONFLICT (staff_id) DO UPDATE SET balance_min=%s", (sid, bal, bal))


def _bank(sid):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT balance_min FROM ot_bank WHERE staff_id=%s", (sid,))
            r = cur.fetchone()
            return int(r["balance_min"]) if r else None


def _cleanup(sid):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM ot_bank WHERE staff_id=%s", (sid,))


def test_claim_spend_atomic_refuses_overspend_and_double_tap():
    sid = _staff_id()
    db.set_att_test(False)   # exercise the REAL atomic-debit path (staging DB)
    try:
        _set_bank(sid, 100)
        assert db.ot_bank_claim_spend(sid, 60) == 40        # claimed → 40 left
        assert _bank(sid) == 40
        assert db.ot_bank_claim_spend(sid, 60) is None      # over-spend (only 40) → REFUSED
        assert _bank(sid) == 40                              # bank untouched by the refused claim
        assert db.ot_bank_claim_spend(sid, 40) == 0         # exact-fit → claimed → 0
        assert db.ot_bank_claim_spend(sid, 1) is None       # empty → refused
        # double-tap: a 60 bank, two identical claims → first wins, second refused
        _set_bank(sid, 60)
        assert db.ot_bank_claim_spend(sid, 60) == 0
        assert db.ot_bank_claim_spend(sid, 60) is None      # the double-tap can't double-book
    finally:
        _cleanup(sid)
        db.set_att_test(False)


def test_test_mode_never_mutates_real_bank():
    sid = _staff_id()
    db.set_att_test(False)
    try:
        _set_bank(sid, 100)
        db.set_att_test(True)                               # TEST mode: compute, never mutate
        assert db.ot_bank_claim_spend(sid, 60) == 40        # affordable → computed remainder
        assert db.ot_bank_claim_spend(sid, 999) is None     # unaffordable → None
        db.set_att_test(False)
        assert _bank(sid) == 100                            # real bank UNTOUCHED by test-mode claims
    finally:
        _cleanup(sid)
        db.set_att_test(False)
