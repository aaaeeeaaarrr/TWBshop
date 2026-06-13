"""Step-3 guards: deduct-at-approval consistency across the hand-offs.

v_al map-awareness is pure. The daily-job partition and the no_deduct bridge seed a
uniquely-named throwaway staff row and tear it down in finally (self-contained, any DB).
"""
import json
import threading
from datetime import date

import psycopg2.extras
import pytest

import shared.database as db
from gm_bot import audit
from gm_bot import al as alm

TODAY = date(2026, 6, 13)


# ───────────────── al_deduction_map invariant (pure) ─────────────────

def test_deduction_map_full_days_keys_equal_days_and_sum_is_total():
    days = ["2026-06-22", "2026-06-23"]   # Mon, Tue — both working (day off Sun)
    dmap, total = alm.al_deduction_map(days, "days", day_off="Sun")
    assert set(dmap) == set(days) and total == 2.0
    assert total == alm.al_day_count(days, "days", day_off="Sun")


def test_deduction_map_excludes_day_off_as_zero():
    days = ["2026-06-21", "2026-06-22"]   # Sun (day off) + Mon
    dmap, total = alm.al_deduction_map(days, "days", day_off="Sun")
    assert dmap == {"2026-06-21": 0, "2026-06-22": 1} and total == 1.0
    assert set(dmap) == set(days)         # day-off day still a key (value 0)


def test_deduction_map_hours_uses_fraction():
    dmap, total = alm.al_deduction_map(["2026-06-22"], "hours", frac_per_day=0.3, day_off="Sun")
    assert dmap == {"2026-06-22": 0.3} and total == 0.3


def test_deduction_map_no_deduct_is_all_zero():
    days = ["2026-06-22", "2026-06-23"]
    dmap, total = alm.al_deduction_map(days, "days", day_off="Sun", no_deduct=True)
    assert set(dmap) == set(days) and total == 0.0 and all(v == 0 for v in dmap.values())
STAFF = {7: {"call_name": "T", "canonical_name": "Tester"}}


# ───────────────── v_al map-awareness (pure) ─────────────────

def _req(**kw):
    base = {"id": 1, "staff_id": 7, "status": "approved", "kind": "days",
            "days": json.dumps(["2026-06-21"]), "reason": "r", "created_at": None}
    base.update(kw)
    return base


def test_v_al_map_row_clean_when_keys_match_days():
    r = _req(deducted_map={"2026-06-21": 1})
    assert audit.v_al([r], STAFF, TODAY) == []


def test_v_al_map_row_flags_keys_not_equal_days():
    r = _req(days=json.dumps(["2026-06-21", "2026-06-22"]), deducted_map={"2026-06-21": 1})
    assert any("keys" in m for m in audit.v_al([r], STAFF, TODAY))


def test_v_al_flags_cancelled_with_leftover_map():
    r = _req(status="cancelled", deducted_map={"2026-06-21": 1})
    assert any("refund missing" in m for m in audit.v_al([r], STAFF, TODAY))


def test_v_al_cancelled_empty_map_is_clean():
    r = _req(status="cancelled", deducted_map={})
    assert audit.v_al([r], STAFF, TODAY) == []


def test_v_al_legacy_row_still_flags_passed_undeducted():
    # no deducted_map → legacy model: a passed approved day not in deducted_days is flagged
    r = _req(days=json.dumps(["2020-01-01"]), deducted_days="[]", deducted_map=None)
    assert any("NOT deducted" in m for m in audit.v_al([r], STAFF, TODAY))


def test_v_al_map_row_with_zero_is_clean():
    # a day-off / PH-comp day sits in the map as 0 — keys still == days, no flag
    r = _req(deducted_map={"2026-06-21": 0})
    assert audit.v_al([r], STAFF, TODAY) == []


# ───────────────── daily-job partition + no_deduct bridge (DB) ─────────────────

def _seed(name, bal):
    with db._db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM staff_registry WHERE canonical_name=%s", (name,))
        cur.execute("INSERT INTO staff_registry (canonical_name, al_left, status) "
                    "VALUES (%s,%s,'active') RETURNING id", (name, bal))
        return cur.fetchone()["id"]


def _teardown(sid):
    with db._db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM al_requests WHERE staff_id=%s", (sid,))
        cur.execute("DELETE FROM staff_registry WHERE id=%s", (sid,))


def _al_left(sid):
    with db._db() as c, c.cursor() as cur:
        cur.execute("SELECT al_left FROM staff_registry WHERE id=%s", (sid,))
        return float(cur.fetchone()["al_left"])


def test_daily_job_skips_map_rows_charges_legacy():
    sid = _seed("ZZ_AL_STEP3_PART", 5.0)
    try:
        with db._db() as c, c.cursor() as cur:
            # legacy row: no map, a past day, not yet deducted → the daily job should charge it
            cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, deducted_days, is_test) "
                        "VALUES (%s,'days',%s,'approved','[]',FALSE)",
                        (sid, json.dumps(["2020-01-01"])))
            # deduct-at-approval row: carries a map for a past day → the daily job must NEVER touch it
            cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, deducted_map, is_test) "
                        "VALUES (%s,'days',%s,'approved',%s,FALSE)",
                        (sid, json.dumps(["2020-01-02"]), psycopg2.extras.Json({"2020-01-02": 1})))
        out = db.al_apply_due_deductions("2026-06-13")
        # only the legacy day was charged (5.0 - 1)
        assert _al_left(sid) == 4.0
        assert sum(len(r["days"]) for r in out) == 1
    finally:
        _teardown(sid)


def test_special_leave_freezes_amount_and_refunds_idempotently():
    sid = _seed("ZZ_AL_STEP3_SPECIAL", 10.0)
    try:
        lid = db.special_leave_create(sid, "death", "parent", "2099-07-01", 3)
        with db._db() as c, c.cursor() as cur:
            cur.execute("SELECT deducted_amount FROM special_leaves WHERE id=%s", (lid,))
            assert float(cur.fetchone()["deducted_amount"]) == 3.0   # frozen == days
        db.al_deduct(sid, 3)                       # simulate the grant-time deduction (10 -> 7)
        assert _al_left(sid) == 7.0
        assert db.special_leave_refund(lid) == 3.0  # S1 inverse: refund the frozen amount (7 -> 10)
        assert _al_left(sid) == 10.0
        assert db.special_leave_refund(lid) is None  # idempotent: second refund mints nothing
        assert _al_left(sid) == 10.0
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM special_leaves WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_v_special_checks_status_and_frozen_amount():
    staff = {7: {"call_name": "T", "canonical_name": "Tester"}}
    ok = {"id": 1, "staff_id": 7, "status": "booked", "deducted_amount": 3}
    assert audit.v_special([ok], staff) == []
    bad_status = {"id": 2, "staff_id": 7, "status": "weird", "deducted_amount": 3}
    assert any("unknown status" in m for m in audit.v_special([bad_status], staff))
    no_amt = {"id": 3, "staff_id": 7, "status": "booked", "deducted_amount": None}
    assert any("frozen deducted_amount" in m for m in audit.v_special([no_amt], staff))


def _pending(sid, days):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, is_test) "
                    "VALUES (%s,'days',%s,'pending',FALSE) RETURNING id", (sid, json.dumps(days)))
        return cur.fetchone()["id"]


def test_f14_sequential_same_date_conflict():
    sid = _seed("ZZ_F14_SEQ", 5.0)
    try:
        r1 = _pending(sid, ["2099-09-01"])
        assert db.al_approve_and_deduct(r1, 1.0, {"2099-09-01": 1}, {}) == 4.0
        # a SECOND AL for the same day must NOT approve or deduct — it stays pending
        r2 = _pending(sid, ["2099-09-01"])
        assert db.al_approve_and_deduct(r2, 1.0, {"2099-09-01": 1}, {}) == "conflict"
        assert _al_left(sid) == 4.0
        assert db.al_get_request(r2)["status"] == "pending"
        # a DIFFERENT day still approves fine
        r3 = _pending(sid, ["2099-09-02"])
        assert db.al_approve_and_deduct(r3, 1.0, {"2099-09-02": 1}, {}) == 3.0
    finally:
        _teardown(sid)


def test_f14_rejects_al_on_an_approved_shift_change_day():
    sid = _seed("ZZ_F14_SCDAY", 5.0)
    try:
        with db._db() as c, c.cursor() as cur:
            cur.execute("INSERT INTO shift_changes (staff_id, when_date, start_min, end_min, "
                        "normal_len, status, is_test) VALUES (%s,%s,480,1020,540,'approved',FALSE)",
                        (sid, "2099-09-10"))
        r = _pending(sid, ["2099-09-10"])
        # scheduled to WORK that day (approved shift-change) → AL must not approve/deduct
        assert db.al_approve_and_deduct(r, 1.0, {"2099-09-10": 1}, {}) == "conflict"
        assert _al_left(sid) == 5.0
        assert db.al_get_request(r)["status"] == "pending"
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM shift_changes WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_f14_shift_change_rejected_when_al_that_day():
    sid = _seed("ZZ_F14_SCSIDE", 5.0)
    try:
        r = _pending(sid, ["2099-09-20"])
        db.al_approve_and_deduct(r, 1.0, {"2099-09-20": 1}, {})   # approved AL that day
        with db._db() as c, c.cursor() as cur:
            cur.execute("INSERT INTO shift_changes (staff_id, when_date, start_min, end_min, "
                        "normal_len, status, is_test) VALUES (%s,%s,480,1020,540,'proposed',FALSE) "
                        "RETURNING id", (sid, "2099-09-20"))
            cid = cur.fetchone()["id"]
        assert db.shift_change_approve_claim(cid) == "conflict"   # can't schedule work on a leave day
        with db._db() as c, c.cursor() as cur:
            cur.execute("SELECT status FROM shift_changes WHERE id=%s", (cid,))
            assert cur.fetchone()["status"] == "proposed"          # stays proposed
            cur.execute("INSERT INTO shift_changes (staff_id, when_date, start_min, end_min, "
                        "normal_len, status, is_test) VALUES (%s,%s,480,1020,540,'proposed',FALSE) "
                        "RETURNING id", (sid, "2099-09-21"))
            cid2 = cur.fetchone()["id"]
        assert db.shift_change_approve_claim(cid2) is True         # a free day approves
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM shift_changes WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_f14_rejects_al_on_a_swap_work_day():
    # a day-off swap can schedule a staffer to WORK a normally-off day (dayoff_override kind='work');
    # AL must not land on it (scheduled to cover vs on leave). AL-side coverage of the swap collision.
    sid = _seed("ZZ_F14_SWAPWORK", 5.0)
    try:
        db.dayoff_set_override(sid, "2099-12-20", "work", "swap")
        r = _pending(sid, ["2099-12-20"])
        assert db.al_approve_and_deduct(r, 1.0, {"2099-12-20": 1}, {}) == "conflict"
        assert _al_left(sid) == 5.0
        assert db.al_date_conflict(sid, ["2099-12-20"]) == ["2099-12-20"]   # request-side sees it too
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM dayoff_overrides WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_f14_concurrent_same_date_exactly_one_wins():
    """Real two-thread race on staging: two pending AL for the same day approved at once → the
    advisory xact-lock serializes them so exactly ONE wins and AL is deducted exactly once."""
    sid = _seed("ZZ_F14_RACE", 5.0)
    try:
        r1 = _pending(sid, ["2099-09-03"])
        r2 = _pending(sid, ["2099-09-03"])
        barrier = threading.Barrier(2)
        results = {}

        def go(name, rid):
            barrier.wait()
            results[name] = db.al_approve_and_deduct(rid, 1.0, {"2099-09-03": 1}, {})

        t1 = threading.Thread(target=go, args=("a", r1))
        t2 = threading.Thread(target=go, args=("b", r2))
        t1.start(); t2.start(); t1.join(); t2.join()
        assert sorted([str(results["a"]), str(results["b"])]) == ["4.0", "conflict"]
        assert _al_left(sid) == 4.0   # deducted exactly once despite the race
    finally:
        _teardown(sid)


def test_f14_concurrent_cross_flow_al_vs_shift_change_one_wins():
    """The shared advisory-lock namespace must make an AL-approval and a shift-change-approval for the
    same staff+date mutually exclusive under a real race — exactly one commits."""
    sid = _seed("ZZ_F14_XFLOW", 5.0)
    try:
        al = _pending(sid, ["2099-09-30"])
        with db._db() as c, c.cursor() as cur:
            cur.execute("INSERT INTO shift_changes (staff_id, when_date, start_min, end_min, "
                        "normal_len, status, is_test) VALUES (%s,%s,480,1020,540,'proposed',FALSE) "
                        "RETURNING id", (sid, "2099-09-30"))
            cid = cur.fetchone()["id"]
        barrier = threading.Barrier(2)
        res = {}

        def do_al():
            barrier.wait()
            res["al"] = db.al_approve_and_deduct(al, 1.0, {"2099-09-30": 1}, {})

        def do_sc():
            barrier.wait()
            res["sc"] = db.shift_change_approve_claim(cid)

        ta, ts = threading.Thread(target=do_al), threading.Thread(target=do_sc)
        ta.start(); ts.start(); ta.join(); ts.join()
        # exactly one side won; the other saw the conflict
        al_won = (res["al"] == 4.0)
        sc_won = (res["sc"] is True)
        assert al_won != sc_won                      # exactly one
        assert (res["al"] == "conflict") or (res["sc"] == "conflict")
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM shift_changes WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_al_end_to_end_multiday_with_dayoff():
    """All the pieces together on a realistic multi-day AL spanning a day-off: the frozen map zeros the
    day-off, the deduction is exact, a partial cancel refunds exactly, the audit stays clean, and the
    daily job never touches the map row."""
    from gm_bot import al as alm
    from gm_bot import audit
    sid = _seed("ZZ_AL_E2E", 10.0)
    try:
        with db._db() as c, c.cursor() as cur:
            cur.execute("UPDATE staff_registry SET day_off='Sun', work_start='08:00', work_end='17:00' "
                        "WHERE id=%s", (sid,))
        days = ["2099-12-04", "2099-12-05", "2099-12-06", "2099-12-07"]
        # set day_off to whichever weekday days[2] falls on, so days[2] is the excluded (0-cost) day
        off = date.fromisoformat(days[2]).strftime("%a")
        with db._db() as c, c.cursor() as cur:
            cur.execute("UPDATE staff_registry SET day_off=%s WHERE id=%s", (off, sid))
        dmap, total = alm.al_deduction_map(days, "days", day_off=off, non_working=set())
        assert dmap == {days[0]: 1, days[1]: 1, days[2]: 0, days[3]: 1} and total == 3.0
        r = _pending(sid, days)
        assert db.al_approve_and_deduct(r, total, dmap, {}) == 7.0      # 10 - 3 charged days
        # partial cancel: a charged day refunds 1, the day-off day refunds 0
        assert db.al_cancel_and_refund(r, sid, days[0], today_iso="2026-06-13") == (1.0, 3)
        assert _al_left(sid) == 8.0
        assert db.al_cancel_and_refund(r, sid, days[2], today_iso="2026-06-13") == (0.0, 2)
        assert _al_left(sid) == 8.0                                     # day-off cancel moves nothing
        # audit clean on the still-approved (partially-cancelled) row: keys still == remaining days
        staff = {sid: {"call_name": "E2E", "canonical_name": "E2E"}}
        with db._db() as c, c.cursor() as cur:
            cur.execute("SELECT * FROM al_requests WHERE id=%s", (r,))
            row = dict(cur.fetchone())
        assert audit.v_al([row], staff, date(2026, 6, 13)) == []
        # daily job must NOT touch this map row (no extra deduction)
        db.al_apply_due_deductions("2099-12-31")
        assert _al_left(sid) == 8.0
    finally:
        _teardown(sid)


def test_al_date_conflict_detects_approved_al_and_shift_change():
    sid = _seed("ZZ_AL_CONFLICT", 5.0)
    try:
        r = _pending(sid, ["2099-11-01"])
        db.al_approve_and_deduct(r, 1.0, {"2099-11-01": 1}, {})       # approved AL on day A
        with db._db() as c, c.cursor() as cur:                        # approved shift-change on day B
            cur.execute("INSERT INTO shift_changes (staff_id, when_date, start_min, end_min, "
                        "normal_len, status, is_test) VALUES (%s,%s,480,1020,540,'approved',FALSE)",
                        (sid, "2099-11-02"))
        assert db.al_date_conflict(sid, ["2099-11-01", "2099-11-02", "2099-11-03"]) == \
            ["2099-11-01", "2099-11-02"]
        assert db.al_date_conflict(sid, ["2099-11-03"]) == []          # a free day is clear
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM shift_changes WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_approve_writes_forward_points_in_same_txn():
    # red-team #2: the forward short-notice points must be written by al_approve_and_deduct itself
    # (atomic with the deduct), not by a separate call that a crash could skip.
    sid = _seed("ZZ_AL_FWDPTS", 5.0)
    try:
        r = _pending(sid, ["2099-10-05"])
        db.al_approve_and_deduct(r, 1.0, {"2099-10-05": 1}, {"2099-10-05": 120})
        with db._db() as c, c.cursor() as cur:
            cur.execute("SELECT quantity FROM points_events WHERE staff_id=%s AND cause='short_notice_al'",
                        (sid,))
            assert [row["quantity"] for row in cur.fetchall()] == [120]
    finally:
        with db._db() as c, c.cursor() as cur:
            cur.execute("DELETE FROM points_events WHERE staff_id=%s", (sid,))
        _teardown(sid)


def test_cancel_list_excludes_legacy_no_map_rows(monkeypatch):
    # red-team #1: a legacy (no deducted_map) approved row can't be refunded by al_cancel_and_refund,
    # so it must NOT be offered a silently-no-op cancel button.
    from gm_bot import attendance_ui as ui
    sid = _seed("ZZ_AL_CANCELLIST", 5.0)
    try:
        with db._db() as c, c.cursor() as cur:
            cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, deducted_map, is_test) "
                        "VALUES (%s,'days',%s,'approved',%s,FALSE)",
                        (sid, json.dumps(["2099-10-01"]), psycopg2.extras.Json({"2099-10-01": 1})))
            cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, is_test) "
                        "VALUES (%s,'days',%s,'approved',FALSE)", (sid, json.dumps(["2099-10-02"])))
        monkeypatch.setattr(ui, "att_test_on", lambda: False)
        monkeypatch.setattr(ui, "_shift_running", lambda p: False)
        p = {"id": sid, "canonical_name": "T", "call_name": "T"}
        _txt, kb = ui.al_cancel_list(p)
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert any("2099-10-01" in c for c in cbs)       # map row IS offered
        assert not any("2099-10-02" in c for c in cbs)   # legacy row is hidden
    finally:
        _teardown(sid)


def test_create_request_bridges_ph_into_no_deduct():
    sid = _seed("ZZ_AL_STEP3_PH", 5.0)
    try:
        rid_ph = db.al_create_request(sid, "days", ["2099-05-01"], None, None,
                                      "PH comp for holiday", 999)
        rid_norm = db.al_create_request(sid, "days", ["2099-05-02"], None, None, "sick", 999)
        with db._db() as c, c.cursor() as cur:
            cur.execute("SELECT id, no_deduct FROM al_requests WHERE id IN (%s,%s)", (rid_ph, rid_norm))
            flags = {r["id"]: r["no_deduct"] for r in cur.fetchall()}
        assert flags[rid_ph] is True
        assert flags[rid_norm] is False
    finally:
        _teardown(sid)
