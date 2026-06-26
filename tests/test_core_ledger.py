"""core.ledger — the atomic money mechanism. Proves the bug-class CAN'T recur by construction:
settle-once/idempotent (no double-bank), the bank cap, the buyback atomic refusal, and the clean
reversible inverse (S1). Real staging DB; cleaned up."""
from datetime import datetime, timezone, date

import core.db as cdb
from core import ledger
from shared.database import _db

ORG = "test_ledger"
UTC = timezone.utc


def _setup():
    cdb.init_core_db()
    cdb.ensure_org(ORG, "Test")
    _clean()


def _clean():
    with _db() as c:
        with c.cursor() as cur:
            for t in ("attendance_events", "core_payback_debts", "core_ot_bank", "shifts"):
                cur.execute("DELETE FROM %s WHERE org_id=%%s" % t, (ORG,))


def _shift(staff_id) -> int:
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO shifts (org_id, staff_id, start_dt, end_dt, business_day) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING shift_id",
                        (ORG, staff_id, datetime(2026, 6, 20, 23, 0, tzinfo=UTC),
                         datetime(2026, 6, 21, 8, 0, tzinfo=UTC), date(2026, 6, 21)))
            return cur.fetchone()["shift_id"]


def _shift_at(staff_id, start_dt, end_dt) -> int:
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO shifts (org_id, staff_id, start_dt, end_dt, business_day) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING shift_id",
                        (ORG, staff_id, start_dt, end_dt, end_dt.date()))
            return cur.fetchone()["shift_id"]


def _seed_bank(staff_id, bal):
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO core_ot_bank (org_id, staff_id, balance_min) VALUES (%s,%s,%s) "
                        "ON CONFLICT (org_id, staff_id) DO UPDATE SET balance_min=EXCLUDED.balance_min",
                        (ORG, staff_id, bal))


def test_settle_once_no_double_bank():
    _setup()
    try:
        sid = _shift(1)
        ledger.add_debt(ORG, 1, 60)                              # owes 60
        r = ledger.settle_checkout(ORG, 1, sid, 600, 480)        # OT 120 → clear 60 + bank 60
        assert r["claimed"] and r["pb_cleared"] == 60 and r["ot_banked"] == 60
        assert ledger.bank_balance(ORG, 1) == 60 and ledger.open_debt(ORG, 1) is None
        r2 = ledger.settle_checkout(ORG, 1, sid, 600, 480)       # duplicate/auto checkout
        assert r2["claimed"] is False
        assert ledger.bank_balance(ORG, 1) == 60                 # NOT doubled
    finally:
        _clean()


def test_bank_cap_never_exceeded():
    _setup()
    try:
        sid = _shift(2)
        _seed_bank(2, ledger.BANK_CAP_MIN - 1)                   # 1 min of room
        r = ledger.settle_checkout(ORG, 2, sid, 600, 240)        # 360 OT, only 1 fits
        assert r["ot_banked"] == 1 and r["ot_dropped"] == 359
        assert ledger.bank_balance(ORG, 2) == ledger.BANK_CAP_MIN
    finally:
        _clean()


def test_buyback_atomic_refuses_overspend():
    _setup()
    try:
        _seed_bank(3, 120)
        assert ledger.buyback_spend(ORG, 3, 100) == 20           # ok
        assert ledger.buyback_spend(ORG, 3, 100) is None         # only 20 left → refused
        assert ledger.bank_balance(ORG, 3) == 20                 # unchanged by the refusal
    finally:
        _clean()


def test_reverse_settle_clean_inverse_idempotent():
    _setup()
    try:
        sid = _shift(4)
        ledger.add_debt(ORG, 4, 60)
        ledger.settle_checkout(ORG, 4, sid, 600, 480)            # bank 60, clear 60
        rv = ledger.reverse_settle(ORG, sid)
        assert rv["reversed"] and rv["ot_refunded"] == 60 and rv["pb_uncredited"] == 60
        assert ledger.bank_balance(ORG, 4) == 0                  # refunded
        d = ledger.open_debt(ORG, 4)
        assert d and d["paid_min"] == 0                          # debt reopened, credit removed
        assert ledger.reverse_settle(ORG, sid)["reversed"] is False   # idempotent
    finally:
        _clean()


def test_two_shifts_same_staff_bank_accumulates_to_cap_truthfully():
    """LEDGER-CAP (s55): two of one staff's shifts each earning OT accumulate the bank to the cap ONCE —
    never over-bank — and each settle records only the OT it actually banked (so reverse_settle stays
    exact). Sequential here proves the math; the per-staff advisory lock makes the concurrent case behave
    identically (read the OTHER's committed bank, not a stale one)."""
    _setup()
    try:
        cap = ledger.BANK_CAP_MIN
        s1 = _shift_at(5, datetime(2026, 6, 20, 23, 0, tzinfo=UTC), datetime(2026, 6, 21, 8, 0, tzinfo=UTC))
        s2 = _shift_at(5, datetime(2026, 6, 21, 23, 0, tzinfo=UTC), datetime(2026, 6, 22, 8, 0, tzinfo=UTC))
        r1 = ledger.settle_checkout(ORG, 5, s1, 240 + cap, 240)   # earns `cap` OT → banks the full cap
        assert r1["ot_banked"] == cap and ledger.bank_balance(ORG, 5) == cap
        r2 = ledger.settle_checkout(ORG, 5, s2, 240 + cap, 240)   # earns `cap` more, but 0 room left
        assert r2["ot_banked"] == 0 and r2["ot_dropped"] == cap
        assert ledger.bank_balance(ORG, 5) == cap                 # capped, not 2×cap
    finally:
        _clean()


def test_concurrent_same_staff_settles_never_over_bank():
    """Concurrency guard: two of one staff's shifts settling AT ONCE must not both bank from a stale read.
    The per-staff advisory lock serializes them (+ LEAST caps structurally) → final bank == cap and the
    recorded OT sums to exactly the room filled (not 2×, which would make reverse_settle over-refund)."""
    import threading
    _setup()
    try:
        cap = ledger.BANK_CAP_MIN
        s1 = _shift_at(6, datetime(2026, 6, 20, 23, 0, tzinfo=UTC), datetime(2026, 6, 21, 8, 0, tzinfo=UTC))
        s2 = _shift_at(6, datetime(2026, 6, 21, 23, 0, tzinfo=UTC), datetime(2026, 6, 22, 8, 0, tzinfo=UTC))
        start = threading.Barrier(2)
        out = {}
        def go(name, sid):
            start.wait()
            out[name] = ledger.settle_checkout(ORG, 6, sid, 240 + cap, 240)
        ts = [threading.Thread(target=go, args=(n, s)) for n, s in (("a", s1), ("b", s2))]
        for t in ts: t.start()
        for t in ts: t.join()
        assert ledger.bank_balance(ORG, 6) == cap                          # never 2×cap (LEAST belt)
        assert sum(out[k].get("ot_banked", 0) for k in out) == cap         # recorded truthfully (lock)
    finally:
        _clean()
