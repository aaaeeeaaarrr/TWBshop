"""Reason-FIRST sick flow (owner Jun 21): the reason is asked right after the who-pick, captured by
the text router, stashed, and used at filing. Tests the router capture (mocked) + the dispatch reuse.
"""
import asyncio

import gm_bot.bot as bot
import gm_bot.attendance_ui as aui
import shared.database as db
import config


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _Msg:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, t, reply_markup=None):
        self.replies.append((t, reply_markup))


class _User:
    def __init__(self, uid):
        self.id = uid


class _Upd:
    def __init__(self, uid, text):
        self.effective_user = _User(uid)
        self.message = _Msg(text)
        self.effective_chat = _User(uid)


def test_router_captures_reason_and_shows_me_screen(monkeypatch):
    LIVE_UID = 222001
    stored = {}
    monkeypatch.setattr(db, "flow_load", lambda uid: {"flow": "sick_reason", "data": {"who": "me", "persona_id": 5}})
    monkeypatch.setattr(db, "flow_clear", lambda uid: None)
    monkeypatch.setattr(db, "gm_set_state", lambda k, v: stored.__setitem__(k, v))
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: {"id": 5, "call_name": "X",
                                                              "work_start": "19:00", "work_end": "06:00"})
    monkeypatch.setattr(aui, "sick_me_screen", lambda p: ("ME-SCREEN", "KB"))
    monkeypatch.setattr(bot, "_attendance_live", lambda: True)

    upd = _Upd(LIVE_UID, "fever and sore throat")
    _run(bot._private_text_router(upd, _Ctx()))

    assert stored.get("sick_reason_val:%d" % LIVE_UID) == "fever and sore throat"
    assert upd.message.replies and upd.message.replies[0][0] == "ME-SCREEN"


def test_router_family_shows_dates(monkeypatch):
    UID = 222002
    stored = {}
    monkeypatch.setattr(db, "flow_load", lambda uid: {"flow": "sick_reason", "data": {"who": "child", "persona_id": 9}})
    monkeypatch.setattr(db, "flow_clear", lambda uid: None)
    monkeypatch.setattr(db, "gm_set_state", lambda k, v: stored.__setitem__(k, v))
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: {"id": 9, "call_name": "Y"})
    monkeypatch.setattr(aui, "sick_family_dates", lambda p, who: ("DATES-%s" % who, "KB"))
    monkeypatch.setattr(bot, "_attendance_live", lambda: True)

    upd = _Upd(UID, "son has a cough")
    _run(bot._private_text_router(upd, _Ctx()))
    assert stored.get("sick_reason_val:%d" % UID) == "son has a cough"
    assert upd.message.replies[0][0] == "DATES-child"


def test_empty_reason_reasks(monkeypatch):
    UID = 222003
    cleared = {"v": False}
    monkeypatch.setattr(db, "flow_load", lambda uid: {"flow": "sick_reason", "data": {"who": "me", "persona_id": 1}})
    monkeypatch.setattr(db, "flow_clear", lambda uid: cleared.__setitem__("v", True))
    monkeypatch.setattr(db, "gm_set_state", lambda k, v: None)
    monkeypatch.setattr(bot, "_attendance_live", lambda: True)
    upd = _Upd(UID, "   ")   # whitespace only
    _run(bot._private_text_router(upd, _Ctx()))
    assert "What's wrong" in upd.message.replies[0][0]   # re-asked
    assert cleared["v"] is False                          # flow NOT cleared (still waiting)


class _Ctx:
    def __init__(self):
        self.user_data = {}
