"""gm_events instrumentation — _gm_log wrapper + the central click logger (owner Jun 21: 'log every click')."""
import asyncio

import gm_bot.bot as bot
import gm_bot.events as ev


def test_gm_log_writes_a_row(monkeypatch):
    captured = []
    monkeypatch.setattr(ev, "log_event",
                        lambda kind, **k: captured.append((kind, k)))
    # _gm_log imports log_event from gm_bot.events at call time
    bot._gm_log("checkin", staff_id=42, detail={"x": 1})
    assert captured and captured[0][0] == "checkin"
    assert captured[0][1]["staff_id"] == 42


def test_gm_log_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(ev, "log_event", boom)
    bot._gm_log("checkout", staff_id=1)   # must be swallowed — logging can't break a live flow


def test_click_logger_records_data(monkeypatch):
    captured = []
    monkeypatch.setattr(ev, "log_event", lambda kind, **k: captured.append((kind, k)))
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: {"id": 7})
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)

    class _Q:
        data = "att:pb:book:2026-06-21:1051:1140:89"

    class _U:
        id = 555

    class _Upd:
        callback_query = _Q()
        effective_user = _U()

    asyncio.new_event_loop().run_until_complete(bot._log_every_click(_Upd(), None))
    assert captured and captured[0][0] == "click"
    assert captured[0][1]["detail"]["data"].startswith("att:pb:book")
    assert captured[0][1]["staff_id"] == 7
