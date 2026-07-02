"""Observability-law runtime pieces (2026-07-02): job heartbeats, the send ledger, and the four
sentinel detectors that turn them into alarms. Staging DB; isolated org per test where the table is
org-scoped (gm_alarms is global — that test does its own hygiene)."""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core import heartbeat, sends, sentinel
from shared.database import _db

heartbeat.init_heartbeats_db()
sends.init_send_ledger_db()
TZ = ZoneInfo("Asia/Phnom_Penh")


def _org():
    return "obs_" + uuid.uuid4().hex[:10]


# ── heartbeats ────────────────────────────────────────────────────────────────
def test_beat_ok_then_silent_alarm():
    org = _org()
    heartbeat.beat(org, "cron:x", 10, phase="ok")
    now = datetime.now(TZ)
    assert heartbeat.stale(org, now) == []                                  # fresh → healthy
    st = heartbeat.stale(org, now + timedelta(minutes=25))
    assert len(st) == 1 and st[0]["kind"] == "silent" and st[0]["job"] == "cron:x"


def test_start_without_ok_is_not_failing_until_the_hang_floor():
    org = _org()
    heartbeat.beat(org, "job_y", 60, phase="start")
    now = datetime.now(TZ)
    assert heartbeat.stale(org, now + timedelta(minutes=2)) == []           # just started → healthy
    st = heartbeat.stale(org, now + timedelta(minutes=30))                  # hung >10min, within gap
    assert len(st) == 1 and st[0]["kind"] == "failing"


def test_err_loop_flags_failing_while_runs_continue():
    org = _org()
    heartbeat.beat(org, "job_z", 10, phase="ok")
    heartbeat.beat(org, "job_z", 10, phase="err", err="boom")
    now = datetime.now(TZ)
    with _db() as conn:                                                     # simulate: ok long stale, runs fresh
        with conn.cursor() as cur:
            cur.execute("UPDATE core_job_heartbeats SET last_ok=%s, last_run=%s WHERE org_id=%s AND job='job_z'",
                        (now - timedelta(minutes=45), now - timedelta(minutes=1), org))
    st = heartbeat.stale(org, now)
    assert len(st) == 1 and st[0]["kind"] == "failing" and "boom" in st[0]["detail"]


def test_beat_never_raises_on_db_failure(monkeypatch):
    def _explode():
        raise RuntimeError("db down")
    monkeypatch.setattr(heartbeat, "_db", _explode)
    heartbeat.beat("any", "job", 10, phase="ok")                            # must swallow, not raise


# ── send ledger ───────────────────────────────────────────────────────────────
def test_ledger_lifecycle_and_stuck_windows():
    org = _org()
    now = datetime.now(TZ)
    ok_id = sends.record(org, "gm", "Supervisors", 123, ref=9)
    sends.mark(ok_id, ok=True, message_id=555)
    dead_id = sends.record(org, "gm", "Senior", 456)                        # intent that never completes
    fail_id = sends.record(org, "monitor", "builder_notify", 789)
    sends.mark(fail_id, ok=False, err="timeout")
    test_id = sends.record(org, "gm", "Owner", 1, is_test=True)             # test rows never alarm
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_send_ledger SET at=%s WHERE id IN (%s,%s)",
                        (now - timedelta(minutes=30), dead_id, test_id))
    stuck = sends.stuck(org, now)
    ids = {s["id"] for s in stuck}
    assert dead_id in ids and fail_id in ids                                # died mid-send + failed
    assert ok_id not in ids and test_id not in ids                          # sent + is_test excluded
    with _db() as conn:                                                     # a failed row ages out after 24h
        with conn.cursor() as cur:
            cur.execute("UPDATE core_send_ledger SET updated=%s WHERE id=%s",
                        (now - timedelta(days=2), fail_id))
    assert fail_id not in {s["id"] for s in sends.stuck(org, now)}


# ── detectors ─────────────────────────────────────────────────────────────────
def test_detect_stale_heartbeats_severity_split():
    org = _org()
    heartbeat.beat(org, "cron:watchdog", 10, phase="ok")
    heartbeat.beat(org, "gm_sweep", 10, phase="ok")
    late = datetime.now(TZ) + timedelta(minutes=25)
    al = sentinel.detect_stale_heartbeats(org, late)
    sev = {a["key"].split(":", 1)[1]: a["severity"] for a in al}
    assert sev["cron:watchdog"] == sentinel.CRITICAL                        # cron daemon class
    assert sev["gm_sweep"] == sentinel.WARN


def test_detect_stuck_sends_fires_then_clears():
    org = _org()
    sid = sends.record(org, "gm", "Senior", 456)
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE core_send_ledger SET at=%s WHERE id=%s",
                        (datetime.now(TZ) - timedelta(minutes=30), sid))
    now = datetime.now(TZ)
    assert any(str(sid) in a["key"] for a in sentinel.detect_stuck_sends(org, now))
    sends.mark(sid, ok=True, message_id=1)
    assert not any(str(sid) in a["key"] for a in sentinel.detect_stuck_sends(org, now))


def test_detect_undelivered_alarms_fires_and_money_escalates():
    from gm_bot import alarms
    alarms.init_alarms_db()
    now = datetime.now(TZ)
    with _db() as conn:                                                     # staging hygiene: neutralize leftovers
        with conn.cursor() as cur:
            cur.execute("UPDATE gm_alarms SET delivered=TRUE WHERE delivered=FALSE AND acked=FALSE")
    assert sentinel.detect_undelivered_alarms("twb", now) == []
    aid = alarms.log_alarm("no_report", "books missing", severity="money")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE gm_alarms SET at=%s WHERE id=%s", (now - timedelta(minutes=30), aid))
    al = sentinel.detect_undelivered_alarms("twb", now)
    assert len(al) == 1 and al[0]["severity"] == sentinel.CRITICAL          # a money alarm shouting into a void
    alarms.mark_delivered(aid)
    assert sentinel.detect_undelivered_alarms("twb", now) == []
    alarms.ack_alarm(aid)


def test_detect_silent_flip_revert():
    from core import flip
    flip.init_flip_db()
    org = _org()
    flip.set_authoritative(org, "checkin", False, "auto-revert: divergence 6/50")
    al = sentinel.detect_silent_flip_revert(org, datetime.now(TZ))
    assert len(al) == 1 and al[0]["severity"] == sentinel.CRITICAL and "checkin" in al[0]["key"]
    flip.set_authoritative(org, "checkin", False, "cut-over prep")          # a manual flip-off never alarms
    assert sentinel.detect_silent_flip_revert(org, datetime.now(TZ)) == []
