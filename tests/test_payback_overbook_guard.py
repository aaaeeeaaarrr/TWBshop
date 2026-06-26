"""Payback over-book guard (owner 'never again', Jun 21).

book_room is the authoritative bookable limit; payback_book enforces it at the single chokepoint so no
path (manual/stale/auto) can over-book. The Heng bug: an 89-min slot booked against a 7-min balance.
"""
import shared.database as db
from gm_bot.payback import book_room


# ── pure invariant (validated against real prod data) ───────────────────────
def test_book_room_real_data_values():
    assert book_room(96, 89, 89) == 0     # Heng: owed96 paid89 open_booked89 → −82 clamped to 0
    assert book_room(10, 9, 1) == 0       # Nak: legit — 1-min slot covers the last min, no more room
    assert book_room(23, 20, 3) == 0      # Chantrea: legit
    assert book_room(540, 0, 0) == 540    # Long: full debt bookable
    assert book_room(60, 0, 0) == 60      # fresh debt


def test_book_room_allows_legit_rebooking_after_partial():
    # late to a come-early slot → 'done' (not open) booking + partial credit in paid → remainder bookable
    # owed 60, paid 50 (worked 50 of a 60 slot), open_booked 0 → 10 still bookable
    assert book_room(60, 50, 0) == 10


def test_book_room_never_negative():
    assert book_room(7, 0, 89) == 0       # already massively over-booked → 0, never negative


# ── chokepoint enforcement (real staging DB, cleaned up) ────────────────────
def _cleanup(sid):
    with db._db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM payback_bookings WHERE staff_id=%s AND is_test=true", (sid,))
            cur.execute("DELETE FROM payback_debts WHERE staff_id=%s AND is_test=true", (sid,))


def _a_staff_id():
    """Self-provision a dedicated test staffer (idempotent; kept ex_staff so it never shows in active sweeps)
    so this money guard can NEVER silently skip on a fresh/empty staging DB (s55 GUARD-SKIP fix)."""
    with db._db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO staff_registry (canonical_name, status) "
                        "VALUES ('__guard_test_staff__','ex_staff') "
                        "ON CONFLICT (canonical_name) DO UPDATE SET status='ex_staff' RETURNING id")
            return cur.fetchone()["id"]


def test_payback_book_refuses_overbook():
    sid = _a_staff_id()   # a dedicated test staffer (FK); only is_test rows are written + cleaned up
    db.set_att_test(True)
    try:
        _cleanup(sid)
        did = db.payback_add_debt(sid, 60, "test", "2026-06-21")
        b1 = db.payback_book(did, sid, "2026-06-22", 0, 60, 60)
        assert b1 > 0, "first 60-min booking fits the 60 debt"
        b2 = db.payback_book(did, sid, "2026-06-23", 0, 30, 30)
        assert b2 == 0, "a 30-min slot on top of a fully-booked 60 debt must be REFUSED"
        # exact-fit edge after a smaller first booking
        _cleanup(sid)
        did = db.payback_add_debt(sid, 60, "test", "2026-06-21")
        assert db.payback_book(did, sid, "2026-06-22", 0, 40, 40) > 0
        assert db.payback_book(did, sid, "2026-06-23", 0, 20, 20) > 0   # 40+20==60 exact, allowed
        assert db.payback_book(did, sid, "2026-06-24", 0, 1, 1) == 0    # 1 over → refused
    finally:
        _cleanup(sid)
        db.set_att_test(False)
