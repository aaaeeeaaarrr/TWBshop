"""D2 — the points cut-over net (gm_bot.checkin_net.points_via_net through core.flip 'points').
FLAG OFF (default) → byte-identical to live's events; FLAG ON → core.points.checkin_points is authoritative
(parity-locked → same result), auto-reverting on divergence. Throwaway orgs; conftest forces staging."""
import pytest

from core import flip
from gm_bot.checkin_net import points_via_net


@pytest.fixture(autouse=True)
def _isolate():
    """Clear the d2pts_* flip authority + divergence log before each test, so divergence rows accumulating
    across suite re-runs can't trip the auto-revert threshold (same lesson as the C2/settle flip tests)."""
    flip.init_flip_db()
    from shared.database import _db
    with _db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core_flip_log WHERE org_id LIKE %s", ("d2pts_%",))
            cur.execute("DELETE FROM core_flip WHERE org_id LIKE %s", ("d2pts_%",))
    yield


def test_flag_off_returns_live_events():
    flip.init_flip_db()
    org = "d2pts_off"
    flip.set_authoritative(org, "points", False)
    live = [("late_uninformed", 30)]
    assert points_via_net("late", 30, 0, None, live, org_id=org) == (live, False)


def test_flag_off_ignores_core_even_if_live_is_empty():
    flip.init_flip_db()
    org = "d2pts_off2"
    flip.set_authoritative(org, "points", False)
    assert points_via_net("late", 60, 0, None, [], org_id=org) == ([], False)   # bogus empty live kept as-is


def test_flag_on_agreeing_returns_core_events():
    flip.init_flip_db()
    org = "d2pts_on"
    flip.set_authoritative(org, "points", True)
    out, rev = points_via_net("early", 0, 10, None, [("early_arrival", 1)], org_id=org)
    assert out == [("early_arrival", 1)] and rev is False


def test_flag_on_core_overrides_a_wrong_live():
    flip.init_flip_db()
    org = "d2pts_override"
    flip.set_authoritative(org, "points", True)
    out, rev = points_via_net("late", 45, 0, None, [], org_id=org)   # live wrongly empty; core says 45 uninformed
    assert out == [("late_uninformed", 45)] and rev is False


def test_late_split_with_declaration_offset():
    flip.init_flip_db()
    org = "d2pts_split"
    flip.set_authoritative(org, "points", True)
    out, _ = points_via_net("late", 60, 0, 20, [], org_id=org)   # declared 20 min in → 20 uninformed + 40 informed
    assert out == [("late_uninformed", 20), ("late_informed", 40)]


def test_ontime_has_no_points():
    flip.init_flip_db()
    org = "d2pts_ontime"
    flip.set_authoritative(org, "points", True)
    assert points_via_net("ontime", 0, 0, None, [], org_id=org) == ([], False)
