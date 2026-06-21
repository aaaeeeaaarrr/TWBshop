"""The own-sick −15 self-cancellation fix (owner caught via Long, Jun 21).

Bug: _sickme_book computed _sick_late_mins AFTER sick_create, but once the sick case exists
resolve_day marks the day not-working (start_min=None) → _sick_late_mins returns None → the −15
silently never fired. Fix: capture the lateness BEFORE sick_create. This test reproduces the exact
ordering (the mock returns a real value before create, None after) and asserts the −15 still fires.
"""
import asyncio

import gm_bot.bot as bot

PERSONA = {"id": 1, "canonical_name": "Lim Kimlong", "call_name": "Long",
           "work_start": "21:00", "work_end": "06:00", "day_off": "Mon",
           "telegram_ids": [5961683250]}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _ctx():
    class _C:  # noqa
        pass
    return _C()


def _patch(monkeypatch, mins_before_create):
    """Wire mocks. _sick_late_mins returns `mins_before_create` until sick_create runs, then None —
    exactly the prod resolve_day flip. Returns the captured state dict."""
    state = {"created": False, "points": [], "set": {}}
    monkeypatch.setattr(bot, "sick_create", lambda *a, **k: state.__setitem__("created", True))
    monkeypatch.setattr("gm_bot.attendance_ui._sick_late_mins",
                        lambda p: None if state["created"] else mins_before_create)
    monkeypatch.setattr(bot, "payback_add_debt", lambda *a, **k: None)
    monkeypatch.setattr(bot, "points_record",
                        lambda sid, cause, qty, ref: state["points"].append((sid, cause, qty, ref)))
    monkeypatch.setattr(bot, "gm_get_state", lambda k: state["set"].get(k))
    monkeypatch.setattr(bot, "gm_set_state", lambda k, v: state["set"].__setitem__(k, v))

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(bot, "_att_send", _noop)
    monkeypatch.setattr(bot, "_sick_supersede", _noop)
    return state


def test_minus15_fires_despite_post_create_none(monkeypatch):
    # 5 min before shift at filing; would read None after sick_create (the bug) — must still fire.
    state = _patch(monkeypatch, 5)
    _run(bot._sickme_book(_ctx(), PERSONA, "2026-06-19", "fever"))
    causes = [c for (_s, c, _q, _r) in state["points"]]
    assert "late_sick_inform" in causes, "the −15 must fire from the pre-create captured value"
    assert state["set"].get("late_inform_done:1:2026-06-19") == "true"


def test_no_minus15_when_informed_early(monkeypatch):
    # Declared 200 min before shift → not late → no −15.
    state = _patch(monkeypatch, 200)
    _run(bot._sickme_book(_ctx(), PERSONA, "2026-06-19", "fever"))
    causes = [c for (_s, c, _q, _r) in state["points"]]
    assert "late_sick_inform" not in causes


def test_no_minus15_when_not_working(monkeypatch):
    # Not working at filing (None even before create) → no shift to be late to → no −15.
    state = _patch(monkeypatch, None)
    _run(bot._sickme_book(_ctx(), PERSONA, "2026-06-19", "fever"))
    causes = [c for (_s, c, _q, _r) in state["points"]]
    assert "late_sick_inform" not in causes
