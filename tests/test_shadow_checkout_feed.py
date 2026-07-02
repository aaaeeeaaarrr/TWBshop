"""The checkout feed (observability flow tier, 2026-07-03): shared.database.att_check_out — the ONE
live checkout write — feeds the same instant into the platform core so its session loop completes.
Staging; proves: event lands + idempotent · gated off = no-op · test mode = no-op · never raises."""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core.db as cdb
from core import shadow_hook
from core.attendance import check_in
from shared.database import _db

cdb.init_core_db()
cdb.ensure_org("twb", "TWBshop", "Asia/Phnom_Penh")
TZ = ZoneInfo("Asia/Phnom_Penh")


def _staff(sid):
    return {"id": sid, "call_name": "T%s" % sid, "work_start": "08:00", "work_end": "17:00"}


def _events(sid):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT type, count(*) n FROM attendance_events "
                        "WHERE org_id='twb' AND staff_id=%s GROUP BY type", (sid,))
            return {r["type"]: r["n"] for r in cur.fetchall()}


def _on(monkeypatch, test_mode="false"):
    monkeypatch.setattr("shared.database.gm_get_state",
                        lambda k: {"shadow_run": "on", "attendance_test_mode": test_mode}.get(k))


def test_checkout_feeds_core_and_is_idempotent(monkeypatch):
    _on(monkeypatch)
    sid = int(uuid.uuid4().int % 10**6) + 10**6           # unique staff id → isolated events
    st = _staff(sid)
    when_in = datetime.now(TZ).replace(hour=8, minute=1, second=0, microsecond=0)
    assert check_in("twb", sid, when_in, st["work_start"], st["work_end"])["bound"]
    out_iso = when_in.replace(hour=17, minute=2).isoformat()
    shadow_hook.shadow_checkout(sid, out_iso, staff=st)
    shadow_hook.shadow_checkout(sid, out_iso, staff=st)   # duplicate call → one event (UNIQUE claim)
    ev = _events(sid)
    assert ev.get("checked_in") == 1 and ev.get("checked_out") == 1


def test_gated_off_and_test_mode_are_no_ops(monkeypatch):
    sid = int(uuid.uuid4().int % 10**6) + 10**6
    st = _staff(sid)
    monkeypatch.setattr("shared.database.gm_get_state", lambda k: None)          # shadow OFF
    shadow_hook.shadow_checkout(sid, datetime.now(TZ).isoformat(), staff=st)
    assert _events(sid) == {}
    _on(monkeypatch, test_mode="true")                                            # role-play → skip
    shadow_hook.shadow_checkout(sid, datetime.now(TZ).isoformat(), staff=st)
    assert _events(sid) == {}


def test_hook_never_raises_into_live(monkeypatch):
    _on(monkeypatch)
    shadow_hook.shadow_checkout(999999999, "not-a-timestamp", staff=_staff(999999999))   # must swallow


def test_att_check_out_carries_the_hook():
    """Structural: the ONE live checkout write must keep feeding core (the law's flow tier)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "shared" / "database.py").read_text(
        encoding="utf-8", errors="replace")
    body = src.split("def att_check_out(", 1)[1].split("\ndef ", 1)[0]
    assert "shadow_checkout" in body


def test_backfill_matcher_feeds_from_live_truth(monkeypatch):
    """The one-off backfill: a core check-in missing its checkout gets fed from the LIVE session's
    recorded instant; a session live never closed is left alone (flowcheck's job to flag)."""
    _on(monkeypatch)
    import importlib
    bf = importlib.import_module("scripts.backfill_core_checkouts")
    sid = int(uuid.uuid4().int % 10**6) + 10**6
    st = _staff(sid)
    when_in = (datetime.now(TZ) - timedelta(days=2)).replace(hour=8, minute=0, second=0, microsecond=0)
    r = check_in("twb", sid, when_in, st["work_start"], st["work_end"])
    day = r["business_day"]
    with _db() as conn:                                    # the LIVE truth: a closed session that day
        with conn.cursor() as cur:
            # attendance_sessions FKs staff_registry → seed a throwaway registry row with this id
            cur.execute("INSERT INTO staff_registry (id, canonical_name, status) "
                        "VALUES (%s, %s, 'active') ON CONFLICT DO NOTHING",
                        (sid, "OBS TEST %s" % sid))
            cur.execute("INSERT INTO attendance_sessions (staff_id, shift_date, checked_in_at, "
                        "checked_out_at, status, is_test) VALUES (%s,%s,%s,%s,'closed',FALSE)",
                        (sid, day, when_in.isoformat(), when_in.replace(hour=17).isoformat()))
    assert any(m["staff_id"] == sid for m in bf.missing_checkouts())
    got = bf.live_checkout_for(sid, day)
    assert got is not None
    res = __import__("core.attendance", fromlist=["check_out"]).check_out(
        "twb", sid, got if isinstance(got, datetime) else datetime.fromisoformat(str(got)),
        st["work_start"], st["work_end"])
    assert res["bound"] and res["worked_min"] > 0
    assert not any(m["staff_id"] == sid for m in bf.missing_checkouts())
    with _db() as conn:                                    # cleanup the live-table test rows
        with conn.cursor() as cur:
            cur.execute("DELETE FROM attendance_sessions WHERE staff_id=%s", (sid,))
            cur.execute("DELETE FROM staff_registry WHERE id=%s AND canonical_name LIKE 'OBS TEST %%'", (sid,))
