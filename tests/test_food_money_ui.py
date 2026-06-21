"""Food Allowance UI — the gate, the access rule, and the give-flow glue (mocked Telegram; no live bot).
The DB/calc core is covered in test_food_money.py; here we prove the handler wires them correctly."""
import asyncio
import types

import config
from gm_bot import food_money_ui as ui


def _update(uid, chat_type="private", data=None):
    calls = {"answer": [], "edit": []}

    async def _answer(*a, **k):
        calls["answer"].append((a, k))

    async def _edit(text, **k):
        calls["edit"].append((text, k))

    q = types.SimpleNamespace(answer=_answer, edit_message_text=_edit, data=data,
                              from_user=types.SimpleNamespace(id=uid))
    upd = types.SimpleNamespace(callback_query=q,
                                effective_chat=types.SimpleNamespace(type=chat_type),
                                effective_user=types.SimpleNamespace(id=uid))
    return upd, calls


def test_gate_off_by_default(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    monkeypatch.setattr(ui, "gm_get_state", lambda k: None)
    assert ui._food_gate_on() is False                       # safe even when deployed


def test_gate_on_in_test_mode_or_when_flag_set(monkeypatch):
    monkeypatch.setattr(ui, "gm_get_state", lambda k: None)
    monkeypatch.setattr(ui, "att_test_on", lambda: True)
    assert ui._food_gate_on() is True                        # the owner's walk
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    monkeypatch.setattr(ui, "gm_get_state", lambda k: "on")
    assert ui._food_gate_on() is True                        # gone live


def test_may_use_only_listener_or_owner_in_private():
    assert ui._may_use(_update(config.DISPATCH_REMINDER_TELEGRAM_ID, "private")[0]) is True
    assert ui._may_use(_update(config.OWNER_TELEGRAM_ID, "private")[0]) is True
    assert ui._may_use(_update(999999, "private")[0]) is False          # a stranger
    assert ui._may_use(_update(config.DISPATCH_REMINDER_TELEGRAM_ID, "group")[0]) is False  # not in a group


def test_give_records_server_recomputed_amount(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: True)        # gate on + is_test
    monkeypatch.setattr(ui, "gm_get_state", lambda k: None)
    monkeypatch.setattr(ui, "food_arrived_staff",
                        lambda dates, is_test=False: [{"staff_id": 5, "name": "Heng",
                                                       "work_start": "21:00", "work_end": "06:00"}])
    monkeypatch.setattr(ui, "food_money_open_ids", lambda is_test=False: set())
    recorded = {}

    def _rec(sid, name, cents, given_by=None, is_test=False):
        recorded.update(sid=sid, name=name, cents=cents, is_test=is_test)
        return True
    monkeypatch.setattr(ui, "record_food_money_give", _rec)

    upd, calls = _update(config.DISPATCH_REMINDER_TELEGRAM_ID, "private", data="food:give:5")
    asyncio.run(ui.on_food_callback(upd, None))
    # 9h shift → $1.13, recomputed server-side from the schedule (not trusting the button)
    assert recorded == {"sid": 5, "name": "Heng", "cents": 113, "is_test": True}
    assert calls["edit"] and "Heng" in calls["edit"][0][0] and "$1.13" in calls["edit"][0][0]


def test_give_blocked_when_gate_off(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    monkeypatch.setattr(ui, "gm_get_state", lambda k: None)    # gate OFF
    called = {"rec": False}
    monkeypatch.setattr(ui, "record_food_money_give",
                        lambda *a, **k: called.update(rec=True) or True)
    upd, calls = _update(config.DISPATCH_REMINDER_TELEGRAM_ID, "private", data="food:give:5")
    asyncio.run(ui.on_food_callback(upd, None))
    assert called["rec"] is False and calls["edit"] == []      # nothing happens when off
