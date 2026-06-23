"""al_pings persistence — the approval-ladder's delete-prior-across-restarts layer + orphan detection.
Real staging DB; creates an isolated test staff + request and cleans up."""
from shared.database import (_db, init_attendance_db, al_create_request, al_ping_set, al_pings_for,
                             al_ping_count, al_pings_clear, al_pings_orphaned, al_set_status)

init_attendance_db()   # ensure al_pings + escalated_at exist on the staging DB (additive, IF NOT EXISTS)


def _purge_pingtest():
    """Cascade-clean any leftover PingTest staff + their AL data (FK-safe order)."""
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT id FROM staff_registry WHERE canonical_name='PingTest'")
            for r in cur.fetchall():
                sid = r["id"]
                cur.execute("DELETE FROM al_pings WHERE request_id IN (SELECT id FROM al_requests WHERE staff_id=%s)", (sid,))
                cur.execute("DELETE FROM al_approvals WHERE request_id IN (SELECT id FROM al_requests WHERE staff_id=%s)", (sid,))
                cur.execute("DELETE FROM al_requests WHERE staff_id=%s", (sid,))
                cur.execute("DELETE FROM staff_registry WHERE id=%s", (sid,))


def _setup():
    _purge_pingtest()
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO staff_registry (canonical_name, status, is_senior) "
                        "VALUES ('PingTest','active',false) RETURNING id")
            sid = cur.fetchone()["id"]
    req = al_create_request(sid, "days", ["2026-07-01"], None, None, "test", 999001)
    return sid, req


def _clean(sid, req):
    _purge_pingtest()


def test_ping_set_count_clear():
    sid, req = _setup()
    try:
        for uid in (1001, 1002, 1003):              # 3 initial cards (ping_no 0)
            al_ping_set(req, uid, uid, 5000 + uid, 0)
        assert al_ping_count(req) == 0 and len(al_pings_for(req)) == 3
        al_ping_set(req, 1001, 1001, 6001, 1)       # re-ping #1 to two non-responders (upsert, not insert)
        al_ping_set(req, 1002, 1002, 6002, 1)
        assert al_ping_count(req) == 1              # max ping_no = the re-ping round
        assert len(al_pings_for(req)) == 3          # still 3 rows (1003 stayed at 0) — no duplicates
        cleared = al_pings_clear(req)               # clear returns the rows so the job can delete the messages
        assert len(cleared) == 3 and al_ping_count(req) == 0 and al_pings_for(req) == []
    finally:
        _clean(sid, req)


def test_orphaned_only_after_decision():
    sid, req = _setup()
    try:
        al_ping_set(req, 1001, 1001, 7001, 0)
        assert all(p["request_id"] != req for p in al_pings_orphaned())   # pending → not orphaned
        al_set_status(req, "approved")                                    # decided
        assert [p for p in al_pings_orphaned() if p["request_id"] == req]  # now its dangling card is orphaned
    finally:
        _clean(sid, req)
