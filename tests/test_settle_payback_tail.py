"""Regression guard — a worked overnight payback TAIL must credit the debt (Bug B, owner Jun 21).

Heng's Jun-20 7-min tail (06:00-06:07, worked) credited 0 on prod. Investigation proved the settle
HAPPY PATH is correct (it was an over-book-tangle symptom, now prevented by the book_room guard); this
test locks the happy path so the tail-credit can never silently regress. Real staging DB, cleaned up.
"""
import datetime

import shared.database as db
from gm_bot import finance
import gm_bot.bot as bot

D = "2026-07-01"
CHECKOUT = datetime.datetime(2026, 7, 2, 6, 7, 35, tzinfo=finance.PP_TZ)   # 06:07:35 next morning
CHECKIN = datetime.datetime(2026, 7, 1, 18, 58, tzinfo=finance.PP_TZ)       # 2 min early


def _staff_id():
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM staff_registry ORDER BY id LIMIT 1")
            r = cur.fetchone()
            return r["id"] if r else None


def _cleanup(sid):
    with db._db() as c:
        with c.cursor() as cur:
            for t in ("payback_bookings", "payback_debts", "shift_changes", "attendance_sessions"):
                cur.execute("DELETE FROM %s WHERE staff_id=%%s AND is_test=true" % t, (sid,))


def test_worked_overnight_tail_credits_the_debt():
    sid = _staff_id()
    if sid is None:
        import pytest
        pytest.skip("no staff_registry rows on staging")
    db.set_att_test(True)
    staff = {"id": sid, "canonical_name": "T", "call_name": "T",
             "work_start": "19:00", "work_end": "06:00", "day_off": "Mon"}
    try:
        _cleanup(sid)
        did = db.payback_add_debt(sid, 96, "test", D)
        with db._db() as c:
            with c.cursor() as cur:
                cur.execute("UPDATE payback_debts SET minutes_paid=89 WHERE id=%s", (did,))
                cur.execute("""INSERT INTO shift_changes (staff_id, when_date, start_min, end_min,
                               normal_len, reason, status, is_test)
                               VALUES (%s,%s,1140,1807,660,'payback slot','approved',true)""", (sid, D))
        db.att_check_in(sid, D, CHECKIN.isoformat(), True, 0, 0)

        before = db.payback_open_debt(sid)["minutes_paid"]
        bot._settle_redefined_shift(staff, D, CHECKOUT)
        after = db.payback_open_debt(sid)
        # debt should now be fully paid (96) and cleared -> open_debt returns None
        assert after is None, "the 7-min worked tail must clear the debt (89+7=96)"
        assert before == 89
    finally:
        _cleanup(sid)
        db.set_att_test(False)
