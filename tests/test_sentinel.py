"""core.sentinel — the universal liveness monitor (alarm for anything stuck at a step). Staging; a test org."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core.db as cdb
from shared.database import _db
from core import sentinel

cdb.init_core_db()
ORG = "test_sentinel"
TZ = ZoneInfo("Asia/Phnom_Penh")


def _clean():
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM attendance_events WHERE org_id=%s", (ORG,))
            cur.execute("DELETE FROM shadow_comparisons WHERE org_id=%s", (ORG,))


def _checkin_event(cur, at, state="ontime"):
    cur.execute("INSERT INTO attendance_events (org_id, staff_id, type, at, detail) "
                "VALUES (%s,1,'checked_in',%s,%s)", (ORG, at, json.dumps({"state": state} if state else {})))


def test_shadow_stalled_alarms_when_net_dark(monkeypatch):
    monkeypatch.setattr("shared.database.gm_get_state", lambda k: "on" if k == "shadow_run" else None)
    _clean()
    now = datetime.now(TZ)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                _checkin_event(cur, now - timedelta(hours=1))     # a recent check-in, but NO comparison recorded
        alarms = sentinel.sweep(ORG, now)
        assert any(a["flow"] == "shadow" and a["severity"] == sentinel.CRITICAL for a in alarms)
    finally:
        _clean()


def test_shadow_ok_when_comparison_recent(monkeypatch):
    monkeypatch.setattr("shared.database.gm_get_state", lambda k: "on" if k == "shadow_run" else None)
    _clean()
    now = datetime.now(TZ)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                _checkin_event(cur, now - timedelta(hours=1))
                cur.execute("INSERT INTO shadow_comparisons (org_id, staff_id, kind, agree, live, new, at) "
                            "VALUES (%s,1,'checkin',true,'{}','{}',%s)", (ORG, now - timedelta(hours=1)))
        assert not any(a["flow"] == "shadow" for a in sentinel.sweep(ORG, now))   # net healthy → no alarm
    finally:
        _clean()


def test_shadow_off_means_no_alarm(monkeypatch):
    monkeypatch.setattr("shared.database.gm_get_state", lambda k: None)           # shadow OFF
    _clean()
    now = datetime.now(TZ)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                _checkin_event(cur, now - timedelta(hours=1))
        assert not any(a["flow"] == "shadow" for a in sentinel.sweep(ORG, now))
    finally:
        _clean()


def test_malformed_checkin_warns(monkeypatch):
    monkeypatch.setattr("shared.database.gm_get_state", lambda k: None)
    _clean()
    now = datetime.now(TZ)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                _checkin_event(cur, now - timedelta(hours=1), state=None)         # no verdict state
        alarms = sentinel.sweep(ORG, now)
        assert any(a["flow"] == "attendance" and a["severity"] == sentinel.WARN for a in alarms)
    finally:
        _clean()


def test_sweep_orders_criticals_first_and_summarises(monkeypatch):
    monkeypatch.setattr("shared.database.gm_get_state", lambda k: "on" if k == "shadow_run" else None)
    _clean()
    now = datetime.now(TZ)
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                _checkin_event(cur, now - timedelta(hours=1))                     # stalled shadow → critical
                _checkin_event(cur, now - timedelta(hours=2), state=None)         # malformed → warn
        alarms = sentinel.sweep(ORG, now)
        assert alarms[0]["severity"] == sentinel.CRITICAL                         # criticals sort first
        assert "critical" in sentinel.summary_line(alarms)
        assert sentinel.summary_line([]) == "✅ all clear"
    finally:
        _clean()
