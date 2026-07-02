"""A2 (2026-07-03): redefine/split-aware shift MATERIALIZATION — flowcheck's 2nd prod catch.
The mispair class: the check-in hook fed live's RESOLVED start (Nak's 20:56 come-early slots,
Thyda's 06:00 ones) while the checkout hook bound the BASE window → the pair landed on two
orphan half-shifts. Cure: both sides materialize from the SAME resolved window list; split
shifts bind by nearest window; the repair script merges the historical orphans."""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import core.db as cdb
from core import shadow_hook
from core.attendance import check_in, check_out
from shared.database import _db

cdb.init_core_db()
cdb.ensure_org("twb", "TWBshop", "Asia/Phnom_Penh")
TZ = ZoneInfo("Asia/Phnom_Penh")


def _sid():
    return int(uuid.uuid4().int % 10**6) + 2 * 10**6


def _shifts_and_events(sid):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT s.shift_id, s.start_dt,
                                  count(*) FILTER (WHERE e.type='checked_in')  ins,
                                  count(*) FILTER (WHERE e.type='checked_out') outs
                           FROM shifts s LEFT JOIN attendance_events e ON e.shift_id=s.shift_id
                           WHERE s.org_id='twb' AND s.staff_id=%s
                           GROUP BY s.shift_id, s.start_dt ORDER BY s.start_dt""", (sid,))
            return [dict(r) for r in cur.fetchall()]


def _on(monkeypatch, test_mode="false"):
    monkeypatch.setattr("shared.database.gm_get_state",
                        lambda k: {"shadow_run": "on", "attendance_test_mode": test_mode}.get(k))


def test_redefined_day_pairs_on_one_instance():
    """The Thyda shape: base 12:00→24:00, come-early redefine 06:00→24:00. Both sides resolve
    → ONE instance holds the pair, worked from the real (early) start."""
    sid = _sid()
    day = datetime.now(TZ).replace(hour=5, minute=58, second=0, microsecond=0)
    wins = [("06:00", "00:00")]                     # the resolved day (end 24:00 → 00:00 next day)
    r_in = check_in("twb", sid, day, "12:00", "00:00", windows=wins)
    assert r_in["bound"] and r_in["state"] == "on_time"    # 2 min before the resolved start
    r_out = check_out("twb", sid, day.replace(hour=23, minute=55), "12:00", "00:00", windows=wins)
    assert r_out["bound"]
    rows = _shifts_and_events(sid)
    assert len(rows) == 1, "the pair must land on ONE instance (no base-window orphan): %s" % rows
    assert rows[0]["ins"] == 1 and rows[0]["outs"] == 1
    assert r_out["worked_min"] == 17 * 60 + 55      # 06:00 → 23:55 (floored at the resolved start)


def test_split_shift_binds_the_nearest_window():
    sid = _sid()
    wins = [("06:00", "12:00"), ("14:00", "22:00")]
    at = datetime.now(TZ).replace(hour=14, minute=3, second=0, microsecond=0)
    r = check_in("twb", sid, at, "06:00", "12:00", windows=wins)
    assert r["bound"] and r["state"] == "on_time" and r["minutes_late"] == 0, \
        "a 14:03 check-in must bind the 14:00 window (grace), not read as hours-late on the morning one"
    r2 = check_out("twb", sid, at.replace(hour=21, minute=58), "06:00", "12:00", windows=wins)
    assert r2["bound"]
    rows = _shifts_and_events(sid)
    paired = [x for x in rows if x["ins"] == 1 and x["outs"] == 1]
    assert len(paired) == 1, "check-in and checkout must share the afternoon instance: %s" % rows


def test_no_windows_is_the_old_single_window_behaviour():
    sid = _sid()
    at = datetime.now(TZ).replace(hour=8, minute=2, second=0, microsecond=0)
    r = check_in("twb", sid, at, "08:00", "17:00")
    assert r["bound"] and r["state"] == "on_time"
    rows = _shifts_and_events(sid)
    assert len(rows) >= 1 and rows[0]["ins"] == 1


def test_overnight_with_windows_binds_the_prior_day():
    sid = _sid()
    wins = [("21:00", "06:00")]
    two_am = (datetime.now(TZ) + timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
    r = check_in("twb", sid, two_am, "21:00", "06:00", windows=wins)
    assert r["bound"], "a 2am instant must land inside the prior day's 21:00→06:00 interval"


def test_shadow_checkout_resolves_the_same_window_as_the_checkin_feed(monkeypatch):
    """The actual prod mispair, end-to-end through the hook: check-in fed at the resolved start,
    checkout arrives with shift_date → the hook resolves the SAME window → one instance."""
    _on(monkeypatch)
    sid = _sid()
    st = {"id": sid, "call_name": "A2T", "work_start": "12:00", "work_end": "00:00"}
    day_dt = datetime.now(TZ).replace(hour=6, minute=1, second=0, microsecond=0)
    day = day_dt.date().isoformat()
    # live fed the resolved start (come-early 06:00), exactly like bot.py's shadow_checkin call
    assert check_in("twb", sid, day_dt, "06:00", st["work_end"])["bound"]
    import gm_bot.attendance_ui as ui
    monkeypatch.setattr(ui, "resolve_day",
                        lambda p, d, ctx=None: {"working": True, "start_min": 360, "end_min": 1440})
    shadow_hook.shadow_checkout(sid, day_dt.replace(hour=23, minute=50).isoformat(),
                                staff=st, shift_date=day)
    rows = _shifts_and_events(sid)
    assert len(rows) == 1 and rows[0]["ins"] == 1 and rows[0]["outs"] == 1, \
        "resolved checkout must join the check-in's instance, not spawn a base-window orphan: %s" % rows


def test_shadow_checkout_falls_back_to_base_without_shift_date(monkeypatch):
    _on(monkeypatch)
    sid = _sid()
    st = {"id": sid, "call_name": "A2F", "work_start": "08:00", "work_end": "17:00"}
    at = datetime.now(TZ).replace(hour=8, minute=0, second=0, microsecond=0)
    assert check_in("twb", sid, at, st["work_start"], st["work_end"])["bound"]
    shadow_hook.shadow_checkout(sid, at.replace(hour=17, minute=1).isoformat(), staff=st)
    rows = _shifts_and_events(sid)
    assert len(rows) == 1 and rows[0]["outs"] == 1


def test_resolved_windows_native_derive():
    from core.derive import clear_overrides, resolved_windows, set_override
    sid = _sid()
    day = "2026-07-01"
    base = [{"start": "06:00", "end": "12:00"}, {"start": "14:00", "end": "22:00"}]
    try:
        assert resolved_windows("twb", sid, day, base) == [("06:00", "12:00"), ("14:00", "22:00")]
        assert resolved_windows("twb", sid, day, [("08:00", "17:00")]) == [("08:00", "17:00")], \
            "tuples accepted too"
        set_override("twb", sid, day, "redefine", start_min=360, end_min=1440)
        assert resolved_windows("twb", sid, day, base) == [("06:00", "00:00")], \
            "a redefine DEFINES the day (live's model)"
        set_override("twb", sid, day, "al")
        assert resolved_windows("twb", sid, day, base) is None, "an away day binds nothing"
        clear_overrides("twb", sid, day)
        # 2026-07-01 is a Wednesday (weekday 2): weekly day off → None; swap_work restores it
        assert resolved_windows("twb", sid, day, base, day_off_weekday=2) is None
        set_override("twb", sid, day, "swap_work")
        assert resolved_windows("twb", sid, day, base, day_off_weekday=2) == \
            [("06:00", "12:00"), ("14:00", "22:00")]
    finally:
        clear_overrides("twb", sid, day)


def test_repair_script_merges_the_orphan_pair():
    import importlib
    rep = importlib.import_module("scripts.repair_core_mispairs")
    sid = _sid()
    at = datetime.now(TZ).replace(hour=6, minute=1, second=0, microsecond=0)
    # the mispair: check-in on the resolved 06:00 instance, checkout bound to the 08:00 base one
    assert check_in("twb", sid, at, "06:00", "18:00")["bound"]
    assert check_out("twb", sid, at.replace(hour=17, minute=55), "08:00", "18:00")["bound"]
    assert len(_shifts_and_events(sid)) == 2, "precondition: the orphan pair exists"
    assert any(p["staff_id"] == sid for p in rep.find_pairs("twb"))
    rep.repair("twb", apply=True)
    rows = _shifts_and_events(sid)
    assert len(rows) == 1 and rows[0]["ins"] == 1 and rows[0]["outs"] == 1
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT detail->>'worked_min' w FROM attendance_events "
                        "WHERE shift_id=%s AND type='checked_out'", (rows[0]["shift_id"],))
            assert int(cur.fetchone()["w"]) == 11 * 60 + 54    # 06:01 → 17:55
    assert not any(p["staff_id"] == sid for p in rep.find_pairs("twb")), "idempotent"
