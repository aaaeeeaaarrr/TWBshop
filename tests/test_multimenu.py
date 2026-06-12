"""Multi-menu state-integrity fixes (gm_bot).

Two shipped pieces of the owner-approved 3-piece design:
  P2 — prompt-supersession honesty: arming a NEW reason prompt edits the OLD one (which it overwrites
       in the single per-uid `att_pending` slot) to "↩ Replaced…", so a typed reason can never vanish
       into the wrong flow invisibly (the cross-wiring today-bug).
  P3 — stash reset on menu open: open_live_menu clears ALL per-flow selection stashes, not just the
       AL day-set, so a fresh menu can't inherit a stale half-done flow from an older menu sharing the
       same user_data.
(P1 — menu singleton — is held for owner go-ahead; not covered here.)
"""
import asyncio
from types import SimpleNamespace

from gm_bot import attendance_ui


class _Bot:
    def __init__(self):
        self.edits = []

    async def edit_message_text(self, text, chat_id=None, message_id=None, **kw):
        self.edits.append({"text": text, "chat_id": chat_id, "message_id": message_id})


class _App:
    """Captures scheduled coroutines and runs them so the best-effort edit is observable."""
    def __init__(self):
        self.coros = []

    def create_task(self, coro):
        self.coros.append(coro)
        return coro

    def run_all(self):
        for c in self.coros:
            asyncio.run(c)
        self.coros = []


def _ctx(user_data=None):
    bot = _Bot()
    app = _App()
    return SimpleNamespace(bot=bot, application=app, user_data=user_data or {}), bot, app


def _update(uid=7, msg_id=None):
    q = None
    if msg_id is not None:
        q = SimpleNamespace(message=SimpleNamespace(message_id=msg_id, chat_id=100))
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid), callback_query=q)


# ── P2: supersession honesty ──
def test_supersede_relabels_old_prompt():
    """An older armed pend (with prompt coords) gets its message edited to the 'Replaced' line when a
    new prompt is armed on a DIFFERENT message."""
    ctx, bot, app = _ctx({"att_test_pending": {"flow": "al", "_prompt_chat": 100, "_prompt_msg": 11}})
    attendance_ui._supersede_prev_pend(ctx, _update(msg_id=22))
    app.run_all()
    assert len(bot.edits) == 1
    e = bot.edits[0]
    assert e["chat_id"] == 100 and e["message_id"] == 11
    assert "Replaced" in e["text"] and "បានជំនួស" in e["text"]


def test_supersede_skips_same_message():
    """Re-arming onto the SAME message (re-entry) must not relabel it as replaced."""
    ctx, bot, app = _ctx({"att_test_pending": {"flow": "al", "_prompt_chat": 100, "_prompt_msg": 11}})
    attendance_ui._supersede_prev_pend(ctx, _update(msg_id=11))
    app.run_all()
    assert bot.edits == []


def test_supersede_noop_without_prev(monkeypatch):
    """No prior pend (and no live flow_state) → nothing scheduled, no crash."""
    import shared.database as db
    monkeypatch.setattr(db, "flow_load", lambda uid: None)
    ctx, bot, app = _ctx({})
    attendance_ui._supersede_prev_pend(ctx, _update(msg_id=22))
    app.run_all()
    assert bot.edits == []


def test_supersede_noop_when_old_has_no_coords():
    """An old pend with no captured prompt coords (e.g. a tap-only flow) can't be relabelled — skip."""
    ctx, bot, app = _ctx({"att_test_pending": {"flow": "sick_me"}})
    attendance_ui._supersede_prev_pend(ctx, _update(msg_id=22))
    app.run_all()
    assert bot.edits == []


def test_arm_pending_supersedes(monkeypatch):
    """The real _arm_pending path: arming flow B while flow A's prompt is live relabels A."""
    monkeypatch.setattr(attendance_ui, "att_test_on", lambda: True)
    monkeypatch.setattr(attendance_ui, "flow_save", lambda *a, **k: None)
    ctx, bot, app = _ctx({"att_test_pending": {"flow": "al", "_prompt_chat": 100, "_prompt_msg": 11}})
    attendance_ui._arm_pending(ctx, _update(msg_id=33), {"flow": "swap"})
    app.run_all()
    assert len(bot.edits) == 1 and bot.edits[0]["message_id"] == 11


# ── P3: stash reset on open ──
def test_open_live_menu_resets_all_stashes(monkeypatch):
    monkeypatch.setattr(attendance_ui, "main_menu", lambda p: ("menu", None))
    monkeypatch.setattr(attendance_ui, "_persona", lambda ctx: {"id": 1})

    ud = {"att_al_picked": {"2026-06-20"}, "att_al_cov": {"x": 1}, "att_do_day": "2026-06-21",
          "att_do_cov": {"y": 2}, "att_al_from": 9, "att_al_page": 3, "att_ci_armed": True}
    sent = {}

    async def _reply(text, reply_markup=None):
        sent["text"] = text

    ctx = SimpleNamespace(user_data=ud)
    update = SimpleNamespace(message=SimpleNamespace(reply_text=_reply))
    asyncio.run(attendance_ui.open_live_menu(update, ctx, {"id": 1}))

    assert ud["att_al_picked"] == set()
    for k in ("att_al_cov", "att_do_day", "att_do_cov", "att_al_from", "att_al_page", "att_ci_armed"):
        assert k not in ud, "%s should be reset on menu open" % k
    assert sent["text"] == "menu"
