"""s58: the no-show payback-slot reaper. A slot booked but never checked-in is reaped (booking->missed,
redefine->cancelled, NO balance change) so it stops dangling + frees the debt to re-book. A WORKED slot
(a check-in exists) is left alone. Idempotent + test-isolated. Staging DB (this is THYDA's #81/#287 class)."""
from shared import database as db


def _staff(name):
    """Self-provision a dedicated ex_staff test staffer (idempotent) so the FK to staff_registry holds."""
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO staff_registry (canonical_name, status) VALUES (%s,'ex_staff') "
                        "ON CONFLICT (canonical_name) DO UPDATE SET status='ex_staff' RETURNING id", (name,))
            return cur.fetchone()["id"]


def _row(table, _id):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM %s WHERE id=%%s" % table, (_id,))
            r = cur.fetchone()
            return dict(r) if r else None


def test_noshow_slot_is_reaped_no_balance_change():
    sid, slot = _staff("__reaper_noshow_test__"), "2026-01-02"
    debt = db.payback_add_debt(sid, 360, "test sick", slot)
    bk = db.payback_book(debt, sid, slot, 360, 720, 360)
    rd = db.shift_change_autoapprove(sid, slot, 360, 1440, 720, "payback slot")
    assert bk and rd
    # no session for sid on slot → a genuine no-show
    assert db.reap_noshow_payback_bookings("2026-01-03") >= 1
    assert _row("payback_bookings", bk)["status"] == "missed"
    assert _row("shift_changes", rd)["status"] == "cancelled"
    assert _row("payback_debts", debt)["minutes_paid"] == 0          # NO balance change
    # idempotent — re-running leaves it missed, no error
    db.reap_noshow_payback_bookings("2026-01-03")
    assert _row("payback_bookings", bk)["status"] == "missed"


def test_worked_slot_is_not_reaped():
    sid, slot = _staff("__reaper_worked_test__"), "2026-01-02"
    debt = db.payback_add_debt(sid, 360, "test sick", slot)
    bk = db.payback_book(debt, sid, slot, 360, 720, 360)
    rd = db.shift_change_autoapprove(sid, slot, 360, 1440, 720, "payback slot")
    db.att_check_in(sid, slot, "2026-01-02T06:05:00+07:00", True)    # she DID check in / work it
    db.reap_noshow_payback_bookings("2026-01-03")
    assert _row("payback_bookings", bk)["status"] == "booked"        # left alone (worked, not a no-show)
    assert _row("shift_changes", rd)["status"] == "approved"
