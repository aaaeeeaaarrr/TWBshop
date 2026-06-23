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


def test_group_message_records_group_and_stages_in_staff_group(monkeypatch):
    recorded, staged = [], []
    monkeypatch.setattr(ob, "record_group", lambda org, cid, title=None: recorded.append((org, cid)))
    monkeypatch.setattr(ob, "group_id_for_role", lambda org, role: -100)   # the staff group is -100
    monkeypatch.setattr(ob, "record_seen_member", lambda *a, **k: staged.append(a))
    on_msg = ob.make_handlers("org1")[0]
    upd = MagicMock()
    upd.effective_chat.id = -100
    upd.effective_chat.type = "group"
    upd.effective_chat.title = "Staff"
    upd.effective_user.is_bot = False
    upd.effective_user.id = 7
    upd.effective_user.full_name = "Sok"
    upd.effective_user.username = "sok_t"
    asyncio.run(on_msg(upd, None))
    assert recorded == [("org1", -100)] and staged and staged[0][1] == 7
    recorded.clear()
    staged.clear()
    upd.effective_chat.id = -999                       # a different group → recorded but NOT staged
    asyncio.run(on_msg(upd, None))
    assert recorded == [("org1", -999)] and staged == []


def test_onboard_says_none_when_empty(monkeypatch):
    monkeypatch.setattr(ob, "list_candidates", lambda org, status="pending": [])
    cmd = ob.make_handlers("org1")[1]
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
    cb = ob.make_handlers("org1")[2]
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
    cb = ob.make_handlers("org1")[2]
    upd = MagicMock()
    upd.callback_query.data = "onb:skip:9"
    upd.callback_query.answer = AsyncMock()
    upd.callback_query.edit_message_text = AsyncMock()
    upd.callback_query.message.reply_text = AsyncMock()
    asyncio.run(cb(upd, None))
    assert skipped == [9]


def test_start_stages_silent_staffer_and_asks_consent(monkeypatch):
    staged = []
    monkeypatch.setattr(ob, "record_seen_member", lambda *a, **k: staged.append(a))
    monkeypatch.setattr(ob, "_consent_required", lambda org: True)
    start = ob.make_handlers("org1")[3]
    upd = MagicMock()
    upd.effective_user.is_bot = False
    upd.effective_user.id = 9
    upd.effective_user.full_name = "Lin"
    upd.effective_user.first_name = "Lin"
    upd.effective_user.username = "lin"
    upd.effective_message.reply_text = AsyncMock()
    asyncio.run(start(upd, None))
    assert staged and staged[0][1] == 9                                   # silent staffer staged via the link
    assert "consent" in upd.effective_message.reply_text.call_args[0][0].lower()


def test_consent_callback_records(monkeypatch):
    recorded = []
    monkeypatch.setattr(ob, "record_seen_member", lambda *a, **k: None)
    monkeypatch.setattr(ob, "record_consent", lambda org, uid, yes: recorded.append((uid, yes)))
    consent = ob.make_handlers("org1")[4]
    upd = MagicMock()
    upd.callback_query.data = "cns:yes"
    upd.callback_query.answer = AsyncMock()
    upd.callback_query.edit_message_text = AsyncMock()
    upd.effective_user.is_bot = False
    upd.effective_user.id = 9
    upd.effective_user.full_name = "Lin"
    upd.effective_user.username = "lin"
    asyncio.run(consent(upd, None))
    assert recorded == [(9, True)]
