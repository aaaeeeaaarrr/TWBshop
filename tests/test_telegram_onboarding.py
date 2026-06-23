"""adapters.telegram_onboarding — the Telegram discover-confirm adapter, tested with MOCKS (no real bot):
group-message staging is scoped to the staff group; /onboard lists or says none; confirm calls the core
flow then advances. The end-to-end (a real tenant bot) is a separate demo run."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import adapters.telegram_onboarding as ob


def test_candidate_card_buttons():
    text, kb = ob._candidate_card({"tg_user_id": 7, "tg_name": "Sok", "tg_username": "sok_t"})
    assert "Sok" in text and "@sok_t" in text
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "onb:ok:7" in datas and "onb:skip:7" in datas


def test_group_message_stages_only_in_staff_group(monkeypatch):
    staged = []
    monkeypatch.setattr(ob, "record_seen_member", lambda *a, **k: staged.append(a))
    on_msg, _, _ = ob.make_handlers("org1", staff_chat_id=-100)
    upd = MagicMock()
    upd.effective_chat.id = -100
    upd.effective_user.is_bot = False
    upd.effective_user.id = 7
    upd.effective_user.full_name = "Sok"
    upd.effective_user.username = "sok_t"
    asyncio.run(on_msg(upd, None))
    assert staged and staged[0][0] == "org1" and staged[0][1] == 7
    staged.clear()
    upd.effective_chat.id = -999                      # a different group → ignored
    asyncio.run(on_msg(upd, None))
    assert staged == []


def test_onboard_says_none_when_empty(monkeypatch):
    monkeypatch.setattr(ob, "list_candidates", lambda org, status="pending": [])
    _, cmd, _ = ob.make_handlers("org1", -100)
    upd = MagicMock()
    upd.effective_message.reply_text = AsyncMock()
    asyncio.run(cmd(upd, None))
    assert "No new people" in upd.effective_message.reply_text.call_args[0][0]


def test_confirm_callback_confirms_then_advances(monkeypatch):
    confirmed, calls = [], {"n": 0}

    def _list(org, status="pending"):
        calls["n"] += 1
        return [{"tg_user_id": 7, "tg_name": "Sok"}] if calls["n"] == 1 else []

    monkeypatch.setattr(ob, "list_candidates", _list)
    monkeypatch.setattr(ob, "confirm_candidate", lambda org, uid, name, **k: confirmed.append((uid, name)))
    _, _, cb = ob.make_handlers("org1", -100)
    upd = MagicMock()
    upd.callback_query.data = "onb:ok:7"
    upd.callback_query.answer = AsyncMock()
    upd.callback_query.edit_message_text = AsyncMock()
    upd.callback_query.message.reply_text = AsyncMock()
    asyncio.run(cb(upd, None))
    assert confirmed == [(7, "Sok")]
    assert "All done" in upd.callback_query.message.reply_text.call_args[0][0]


def test_skip_callback(monkeypatch):
    skipped = []
    monkeypatch.setattr(ob, "list_candidates", lambda org, status="pending": [])
    monkeypatch.setattr(ob, "skip_candidate", lambda org, uid: skipped.append(uid))
    _, _, cb = ob.make_handlers("org1", -100)
    upd = MagicMock()
    upd.callback_query.data = "onb:skip:9"
    upd.callback_query.answer = AsyncMock()
    upd.callback_query.edit_message_text = AsyncMock()
    upd.callback_query.message.reply_text = AsyncMock()
    asyncio.run(cb(upd, None))
    assert skipped == [9]
