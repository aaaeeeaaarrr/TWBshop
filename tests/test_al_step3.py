"""Step-3 guards: deduct-at-approval consistency across the hand-offs.

v_al map-awareness is pure. The daily-job partition and the no_deduct bridge seed a
uniquely-named throwaway staff row and tear it down in finally (self-contained, any DB).
"""
import json
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
