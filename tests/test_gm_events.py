"""gm_events audit-log foundation — roundtrip + best-effort guarantee (must never raise into a live flow)."""
import json

import gm_bot.events as ev


def test_gm_events_roundtrip():
    ev.init_events_db()
    ev.log_event("checkin", staff_id=999999, uid=12345, detail={"note": "unit-test"}, is_test=True)
    rows = ev.recent_events(kind="checkin", staff_id=999999, is_test=True, limit=5)
    assert rows, "expected at least one logged event"
    assert rows[0]["kind"] == "checkin"
    assert rows[0]["staff_id"] == 999999
    assert json.loads(rows[0]["detail"]).get("note") == "unit-test"


def test_log_event_is_best_effort_never_raises():
    ev.init_events_db()
    # kind=None violates NOT NULL; an un-JSONable value in detail — neither may raise into the caller.
    ev.log_event(None, detail={"x": object()})        # must be swallowed
    ev.log_event("click", detail={"obj": object()})   # default=str handles object(); must not raise
