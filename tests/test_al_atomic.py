"""Regression guard for the atomic AL approve/cancel functions (state-integrity S1/S2/S3).

Each test seeds ONE uniquely-named throwaway staff row and its AL request, exercises the
function, and tears everything down in a finally block — so it is self-contained and safe
against any database. Live path (real al_left moves) on a synthetic row.
"""
import json
import psycopg2.extras
import pytest

import shared.database as db

FUT = ["2099-03-01", "2099-03-02", "2099-03-03"]
TODAY = "2026-06-13"


def _al_left(sid):
    with db._db() as c, c.cursor() as cur:
        cur.execute("SELECT al_left FROM staff_registry WHERE id=%s", (sid,))
        return float(cur.fetchone()["al_left"])


def _seed(name, bal):
    with db._db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM staff_registry WHERE canonical_name=%s", (name,))
        cur.execute("INSERT INTO staff_registry (canonical_name, al_left, status) "
                    "VALUES (%s,%s,'active') RETURNING id", (name, bal))
        return cur.fetchone()["id"]


def _pending(sid, days):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, is_test) "
                    "VALUES (%s,'days',%s,'pending',FALSE) RETURNING id", (sid, json.dumps(days)))
        return cur.fetchone()["id"]


def _approved(sid, dmap, pmap):
    with db._db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO al_requests (staff_id, kind, days, status, deducted_map, points_map, "
                    "is_test) VALUES (%s,'days',%s,'approved',%s,%s,FALSE) RETURNING id",
                    (sid, json.dumps(list(dmap)), psycopg2.extras.Json(dmap), psycopg2.extras.Json(pmap)))
        return cur.fetchone()["id"]


def _teardown(sid):
    with db._db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM al_requests WHERE staff_id=%s", (sid,))
        cur.execute("DELETE FROM points_events WHERE staff_id=%s", (sid,))
        cur.execute("DELETE FROM staff_registry WHERE id=%s", (sid,))


def test_approve_deducts_once_and_is_idempotent():
    sid = _seed("ZZ_AL_ATOMIC_1", 5.0)
    try:
        req = _pending(sid, FUT)
        assert db.al_approve_and_deduct(req, 3.0, {d: 1 for d in FUT}, {}) == 2.0
        assert _al_left(sid) == 2.0
        # S2: a second finalize wins nothing — no double-charge
        assert db.al_approve_and_deduct(req, 3.0, {d: 1 for d in FUT}, {}) is None
        assert _al_left(sid) == 2.0
    finally:
        _teardown(sid)


def test_cancel_refunds_exactly_and_double_tap_mints_nothing():
    sid = _seed("ZZ_AL_ATOMIC_2", 5.0)
    try:
        req = _pending(sid, FUT)
        db.al_approve_and_deduct(req, 3.0, {d: 1 for d in FUT}, {})
        # S1: one clean inverse — refund the exact frozen amount
        assert db.al_cancel_and_refund(req, sid, FUT[0], today_iso=TODAY) == (1.0, 2)
        assert _al_left(sid) == 3.0
        # S2: double-tap the same day refunds nothing
        assert db.al_cancel_and_refund(req, sid, FUT[0], today_iso=TODAY) is None
        assert _al_left(sid) == 3.0
        # cancelling the rest restores the balance and cancels the request
        db.al_cancel_and_refund(req, sid, FUT[1], today_iso=TODAY)
        assert db.al_cancel_and_refund(req, sid, FUT[2], today_iso=TODAY) == (1.0, 0)
        assert _al_left(sid) == 5.0
        assert db.al_get_request(req)["status"] == "cancelled"
    finally:
        _teardown(sid)


def test_cancel_reverses_points_and_guards_past_days():
    sid = _seed("ZZ_AL_ATOMIC_3", 5.0)
    try:
        req = _approved(sid, {FUT[0]: 1}, {FUT[0]: 120})
        db.al_cancel_and_refund(req, sid, FUT[0], today_iso=TODAY)
        with db._db() as c, c.cursor() as cur:
            cur.execute("SELECT quantity FROM points_events WHERE staff_id=%s AND cause='short_notice_al'",
                        (sid,))
            assert [r["quantity"] for r in cur.fetchall()] == [-120]
        # defense in depth: a day already past is never refunded
        past = _approved(sid, {"2000-01-01": 1}, {})
        assert db.al_cancel_and_refund(past, sid, "2000-01-01", today_iso=TODAY) is None
    finally:
        _teardown(sid)


def test_cancel_rejects_wrong_owner_and_unapproved():
    sid = _seed("ZZ_AL_ATOMIC_4", 5.0)
    try:
        req = _approved(sid, {FUT[0]: 1}, {})
        # wrong owner cannot refund
        assert db.al_cancel_and_refund(req, sid + 999999, FUT[0], today_iso=TODAY) is None
        assert _al_left(sid) == 5.0
        # a pending (not approved) request cannot be cancel-refunded
        pend = _pending(sid, [FUT[1]])
        assert db.al_cancel_and_refund(pend, sid, FUT[1], today_iso=TODAY) is None
    finally:
        _teardown(sid)
