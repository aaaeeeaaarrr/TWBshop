"""F1 payback_to_al — the HIGH-RISK balance proof on a REAL staging staff_registry row. A payback_to_al
staffer's owed pay-back is deducted from AL (÷ their own shift), stored on the sick case, and EXACTLY
refunded when papers are accepted (idempotent — no double-refund / no mint). A normal staffer is unchanged
(a pay-back DEBT, AL untouched). The exemption LOOKUP is monkeypatched (it's covered by test_exceptions_live);
this isolates the money path. Forces LIVE mode so al_deduct really writes."""
import pytest

from shared import database as db
from gm_bot import bot
import gm_bot.exceptions_live as el


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.init_attendance_db()   # ensure the al_deducted column exists on staging (idempotent CREATE + ALTER)


def _staff(name, al_left=5.0, ws="09:00", we="18:00"):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO staff_registry (canonical_name, status, work_start, work_end, al_left) "
                        "VALUES (%s,'active',%s,%s,%s) "
                        "ON CONFLICT (canonical_name) DO UPDATE SET status='active', "
                        "work_start=EXCLUDED.work_start, work_end=EXCLUDED.work_end, al_left=EXCLUDED.al_left "
                        "RETURNING id", (name, ws, we, al_left))
            return cur.fetchone()["id"]


def _al(sid):
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT COALESCE(al_left,0) a FROM staff_registry WHERE id=%s", (sid,))
            return float(cur.fetchone()["a"])


@pytest.fixture
def live(monkeypatch):
    """Force LIVE (not att-test) so al_deduct really writes + al_deducted is stored."""
    monkeypatch.setattr(db, "_ATT_TEST", False)
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)


def _reroute(monkeypatch):
    monkeypatch.setattr(el, "exempt", lambda s, k: k == "payback_to_al")


def test_paperless_full_shift_deducts_one_al_and_refunds_exactly(monkeypatch, live):
    sid = _staff("__p2al_full__", al_left=5.0, ws="09:00", we="18:00")   # 540-min shift
    _reroute(monkeypatch)
    staff = {"id": sid, "work_start": "09:00", "work_end": "18:00"}
    d = "2026-02-01"
    cid = db.sick_create(sid, "me", d, "provisional")
    assert bot._payback_or_al(staff, 540, "paperless sick", d, case_id=cid) is True
    assert _al(sid) == 4.0                                    # 5.0 − 1.0 (540/540)
    assert float(db.sick_get(cid)["al_deducted"]) == 1.0      # stored for the exact reversal
    # papers accepted → refund EXACTLY + clear
    assert bot._wipe_sick_payback(sid, d) is True
    assert _al(sid) == 5.0
    assert float(db.sick_get(cid)["al_deducted"]) == 0.0
    # idempotent — a second wipe refunds nothing (no mint)
    bot._wipe_sick_payback(sid, d)
    assert _al(sid) == 5.0


def test_leave_early_partial_is_proportional(monkeypatch, live):
    sid = _staff("__p2al_partial__", al_left=3.0, ws="09:00", we="18:00")
    _reroute(monkeypatch)
    staff = {"id": sid, "work_start": "09:00", "work_end": "18:00"}
    d = "2026-02-02"
    cid = db.sick_create(sid, "me", d, "provisional")
    assert bot._payback_or_al(staff, 270, "leave-early sick", d, case_id=cid) is True
    assert _al(sid) == 2.5                                    # 3.0 − 0.5 (270/540)
    assert bot._wipe_sick_payback(sid, d) is True
    assert _al(sid) == 3.0                                    # restored exactly


def test_late_arrival_deducts_al_no_case(monkeypatch, live):
    sid = _staff("__p2al_late__", al_left=2.0, ws="09:00", we="18:00")
    _reroute(monkeypatch)
    staff = {"id": sid, "work_start": "09:00", "work_end": "18:00"}
    assert bot._payback_or_al(staff, 54, "late arrival", "2026-02-04") is True   # no case_id → no reversal
    assert _al(sid) == 1.9                                    # 2.0 − 0.1 (54/540); a late stands (no wipe)


def test_normal_staffer_gets_a_debt_not_an_al_deduction(monkeypatch, live):
    sid = _staff("__p2al_normal__", al_left=4.0)
    monkeypatch.setattr(el, "exempt", lambda s, k: False)    # no exception → today's behaviour
    staff = {"id": sid, "work_start": "09:00", "work_end": "18:00"}
    d = "2026-02-03"
    assert bot._payback_or_al(staff, 120, "late arrival", d) is False   # created a debt, returned False
    assert _al(sid) == 4.0                                    # AL untouched
    assert any(x["staff_id"] == sid and x["balance"] > 0 for x in db.payback_all_open())


def test_atomic_failure_falls_back_to_debt_no_double_charge(monkeypatch, live):
    """Red-team: if the ATOMIC deduct raises, NOTHING is deducted AND a normal debt is created — never both
    (the old non-atomic deduct-then-store could leave an AL deduction AND a fall-back debt = double-charge)."""
    def _boom(*a, **k):
        raise RuntimeError("boom")
    sid = _staff("__p2al_atomicfail__", al_left=4.0)
    _reroute(monkeypatch)
    import shared.database as dbmod
    monkeypatch.setattr(dbmod, "al_deduct_for_sick", _boom)
    staff = {"id": sid, "work_start": "09:00", "work_end": "18:00"}
    d = "2026-02-05"
    cid = db.sick_create(sid, "me", d, "provisional")
    assert bot._payback_or_al(staff, 540, "paperless sick", d, case_id=cid) is False
    assert _al(sid) == 4.0                                    # AL UNTOUCHED — no double-charge
    assert any(x["staff_id"] == sid and x["balance"] > 0 for x in db.payback_all_open())
