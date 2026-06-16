"""/trynow (owner, Jun 16): nudge on-shift staff who HAVEN'T checked in to try the live-location
check-in. Preview lists only on-shift + not-yet-checked-in; confirm sends _TRY_IT_NOW to exactly them
(never someone who already checked in)."""
import asyncio
import types
import config
from gm_bot import bot


class _Msg:
    def __init__(self):
        self.replies = []

    async def reply_text(self, t, **k):
        self.replies.append(t)


class _Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, uid, text, **k):
        self.sent.append((uid, text))


def _upd_ctx(args):
    upd = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
        message=_Msg())
    ctx = types.SimpleNamespace(args=args, bot=_Bot())
    return upd, ctx


def _setup(monkeypatch):
    # 3 on shift: A (not in), B (checked in), C (not in) — only A & C should be nudged
    on = [({"id": 1, "telegram_ids": [101], "call_name": "A", "canonical_name": "A"}, "2026-06-16", 0, 600),
          ({"id": 2, "telegram_ids": [102], "call_name": "B", "canonical_name": "B"}, "2026-06-16", 0, 600),
          ({"id": 3, "telegram_ids": [103], "call_name": "C", "canonical_name": "C"}, "2026-06-16", 0, 600)]
    monkeypatch.setattr(bot, "_attendance_live", lambda: True)
    monkeypatch.setattr(bot, "_on_shift_now", lambda: on)
    monkeypatch.setattr(bot, "att_get_session",
                        lambda sid, sd: {"checked_in_at": "x"} if sid == 2 else None)


def test_trynow_preview_lists_only_unchecked_onshift(monkeypatch):
    _setup(monkeypatch)
    upd, ctx = _upd_ctx([])                      # no 'confirm' → preview only
    asyncio.run(bot.cmd_trynow(upd, ctx))
    msg = upd.message.replies[-1]
    assert "Will nudge 2 on-shift" in msg and "A, C" in msg
    assert ctx.bot.sent == []                    # preview sends nothing


def test_trynow_confirm_sends_only_to_pending(monkeypatch):
    _setup(monkeypatch)
    upd, ctx = _upd_ctx(["confirm"])
    asyncio.run(bot.cmd_trynow(upd, ctx))
    uids = sorted(u for u, _ in ctx.bot.sent)
    assert uids == [101, 103]                    # A and C only — never B (already checked in)
    assert all(t == bot._TRY_IT_NOW for _, t in ctx.bot.sent)


def test_trynow_refuses_when_not_live(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setattr(bot, "_attendance_live", lambda: False)
    upd, ctx = _upd_ctx(["confirm"])
    asyncio.run(bot.cmd_trynow(upd, ctx))
    assert "Not live" in upd.message.replies[-1] and ctx.bot.sent == []
