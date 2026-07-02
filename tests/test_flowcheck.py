"""core.flowcheck — the declarative "did it reach its NEXT step?" engine (owner's flow-tier law,
2026-07-03). Staging; isolated org per test; every rule proven to fire on a stuck instance and stay
silent once the step arrives at its destination/terminal."""
import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core.db as cdb
from core import flowcheck, sentinel
from shared.database import _db

cdb.init_core_db()
TZ = ZoneInfo("Asia/Phnom_Penh")


def _org():
    org = "flw_" + uuid.uuid4().hex[:10]
    cdb.ensure_org(org, org, "Asia/Phnom_Penh")
    return org


def _mk_shift(cur, org, start_h_ago=40):
    # UNIQUE(org_id, staff_id, start_dt) + NOW() is transaction-stable → each shift needs its own start
    cur.execute("INSERT INTO shifts (org_id, staff_id, start_dt, end_dt, business_day) "
                "VALUES (%s,1,NOW() - %s * interval '1 hour', NOW() - %s * interval '1 hour', '2026-07-01') "
                "RETURNING shift_id", (org, start_h_ago, start_h_ago - 9))
    return cur.fetchone()["shift_id"]


def _event(cur, org, shift_id, typ, at):
    cur.execute("INSERT INTO attendance_events (org_id, shift_id, staff_id, type, at, detail) "
                "VALUES (%s,%s,1,%s,%s,%s)", (org, shift_id, typ, at, json.dumps({})))


def test_checkin_only_feed_yields_one_info_finding_not_per_session_noise():
    """The 2026-07-03 first-prod-run lesson: TWB's shadow feed is check-in-only → 20 per-session warns
    about ONE upstream gap. The probe collapses that to a single info 'feed gap' finding."""
    org = _org()
    now = datetime.now(TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            for i in range(3):
                sid = _mk_shift(cur, org, start_h_ago=40 + i)
                _event(cur, org, sid, "checked_in", now - timedelta(hours=30))
    found = [f for f in flowcheck.check(org, now) if f["flow"] == "core_session"]
    assert len(found) == 1 and found[0]["severity"] == "info" and "feed_gap" in found[0]["key"]


def test_stuck_session_fires_then_clears_when_the_feed_carries_checkouts():
    org = _org()
    now = datetime.now(TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            done = _mk_shift(cur, org, start_h_ago=64)     # a completed session proves the feed
            _event(cur, org, done, "checked_in", now - timedelta(hours=64))
            _event(cur, org, done, "checked_out", now - timedelta(hours=55))
            sid = _mk_shift(cur, org, start_h_ago=31)
            _event(cur, org, sid, "checked_in", now - timedelta(hours=30))  # the stuck one
    stuck = flowcheck.check(org, now)
    assert any(f["flow"] == "core_session" and str(sid) in f["key"] for f in stuck)
    with _db() as conn:
        with conn.cursor() as cur:
            _event(cur, org, sid, "checked_out", now - timedelta(hours=21))
    assert not any(f["flow"] == "core_session" for f in flowcheck.check(org, now))


def test_fresh_checkin_and_empty_org_are_silent():
    org = _org()
    now = datetime.now(TZ)
    assert not any(f["flow"] == "core_session" for f in flowcheck.check(org, now))   # no feed at all
    with _db() as conn:
        with conn.cursor() as cur:
            done = _mk_shift(cur, org, start_h_ago=64)
            _event(cur, org, done, "checked_in", now - timedelta(hours=64))
            _event(cur, org, done, "checked_out", now - timedelta(hours=55))
            sid = _mk_shift(cur, org, start_h_ago=4)
            _event(cur, org, sid, "checked_in", now - timedelta(hours=3))   # mid-shift → healthy
    assert not any(f["flow"] == "core_session" for f in flowcheck.check(org, now))


def test_unreconciled_live_mismatch_fires_then_terminal_clears():
    org = _org()
    now = datetime.now(TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO shadow_comparisons (org_id, staff_id, kind, agree, live, new, source, at) "
                        "VALUES (%s,1,'checkin',FALSE,'{}','{}','live',%s) RETURNING id",
                        (org, now - timedelta(days=3)))
            cid = cur.fetchone()["id"]
    stuck = flowcheck.check(org, now)
    assert any(f["flow"] == "shadow_mismatch" and str(cid) in f["key"] for f in stuck)
    with _db() as conn:                                       # reaching the terminal = reconciled
        with conn.cursor() as cur:
            cur.execute("UPDATE shadow_comparisons SET reconciled=TRUE WHERE id=%s", (cid,))
    assert not any(f["flow"] == "shadow_mismatch" for f in flowcheck.check(org, now))


def test_agree_and_replay_rows_never_flag():
    org = _org()
    now = datetime.now(TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO shadow_comparisons (org_id, staff_id, kind, agree, live, new, source, at) "
                        "VALUES (%s,1,'checkin',TRUE,'{}','{}','live',%s)", (org, now - timedelta(days=3)))
            cur.execute("INSERT INTO shadow_comparisons (org_id, staff_id, kind, agree, live, new, source, at) "
                        "VALUES (%s,1,'checkin',FALSE,'{}','{}','replay',%s)", (org, now - timedelta(days=3)))
    assert not any(f["flow"] == "shadow_mismatch" for f in flowcheck.check(org, now))


def test_stalled_onboarding_candidate_fires_then_confirm_clears():
    org = _org()
    now = datetime.now(TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_onboarding_candidates (org_id, tg_user_id, tg_name, status, seen_at) "
                        "VALUES (%s, 777, 'Sok', 'pending', %s)", (org, now - timedelta(days=9)))
    assert any(f["flow"] == "onboarding_candidate" for f in flowcheck.check(org, now))
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_onboarding_candidates SET status='confirmed' WHERE org_id=%s", (org,))
    assert not any(f["flow"] == "onboarding_candidate" for f in flowcheck.check(org, now))


def test_detector_bridges_rules_into_the_sweep():
    org = _org()
    now = datetime.now(TZ)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO core_onboarding_candidates (org_id, tg_user_id, tg_name, status, seen_at) "
                        "VALUES (%s, 778, 'Dara', 'pending', %s)", (org, now - timedelta(days=9)))
    al = sentinel.detect_broken_flows(org, now)
    assert any(a["flow"] == "flow:onboarding_candidate" and a["severity"] == sentinel.WARN for a in al)


def test_a_broken_rule_reports_itself(monkeypatch):
    def _boom(org_id, now):
        raise RuntimeError("rule bug")
    monkeypatch.setattr(flowcheck, "RULES", [("exploding", _boom)])
    out = flowcheck.check("any", datetime.now(TZ))
    assert out and out[0]["flow"] == "flowcheck" and "exploding" in out[0]["key"]
