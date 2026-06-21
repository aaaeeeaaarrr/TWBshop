"""v_shift_changes: an approved redefine for an OVERNIGHT shift still being worked must NOT be flagged
'never settled' (owner Jun 22 — the 2am watchdog false alarm for Nak/Chantrea)."""
from datetime import date, timedelta

from gm_bot.audit import v_shift_changes

STAFF = {8: {"id": 8, "call_name": "Nak"}}
TODAY = date(2026, 6, 22)
YESTERDAY = date(2026, 6, 21)


def _row(when, status="approved"):
    return {"id": 273, "staff_id": 8, "when_date": when, "status": status,
            "start_min": 1259, "end_min": 1800, "normal_len": 540}


def test_open_overnight_session_not_flagged():
    # yesterday's overnight redefine, session still OPEN → not stale (will settle at ~06:00 checkout)
    out = v_shift_changes([_row(YESTERDAY)], STAFF, TODAY, open_sessions={(8, "2026-06-21")})
    assert not any("never settled" in m for m in out)


def test_closed_unsettled_still_flags():
    # session NOT open (checked out) but redefine still approved → a real settle failure → flag
    out = v_shift_changes([_row(YESTERDAY)], STAFF, TODAY, open_sessions=set())
    assert any("never settled" in m for m in out)


def test_old_dangling_still_flags_even_if_open():
    # an open session from 3 days ago is itself stale — don't let it hide an old dangling redefine
    out = v_shift_changes([_row(date(2026, 6, 19))], STAFF, TODAY, open_sessions={(8, "2026-06-19")})
    assert any("never settled" in m for m in out)


def test_today_not_flagged():
    out = v_shift_changes([_row(TODAY)], STAFF, TODAY, open_sessions=set())
    assert not any("never settled" in m for m in out)
