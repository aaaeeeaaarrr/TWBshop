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


# ── Stage 1: F1 voice-refuse + F5 Back→Cancel ──
def test_voice_reason_refused_keeps_pend(monkeypatch):
    """A voice note on an armed reason prompt is REFUSED and the pend is KEPT (not the old silent
    thank-you-and-drop). Returns True so the photo router doesn't treat it as a sick-paper."""
    from gm_bot import bot
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    replies = []

    async def _reply(t):
        replies.append(t)

    msg = SimpleNamespace(voice=True, photo=None, sticker=None, reply_text=_reply,
                          chat_id=1, message_id=2)
    update = SimpleNamespace(message=msg, effective_user=SimpleNamespace(id=9))
    ctx = SimpleNamespace(user_data={"att_test_pending": {"flow": "al"}})
    handled = asyncio.run(bot._capture_voice_reason(update, ctx))
    assert handled is True
    assert ctx.user_data.get("att_test_pending") == {"flow": "al"}   # pend NOT cleared
    assert "type your reason" in replies[0]
    assert "buttons below" not in replies[0]   # the refuse msg is standalone — no buttons under it


def test_voice_reason_passes_through_when_no_pend(monkeypatch):
    """No armed reason pend → returns False so the photo router falls through to sick-paper handling."""
    from gm_bot import bot
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    monkeypatch.setattr(bot, "_attendance_live", lambda: False)

    async def _reply(t):
        pass

    msg = SimpleNamespace(voice=True, photo=None, sticker=None, reply_text=_reply,
                          chat_id=1, message_id=2)
    update = SimpleNamespace(message=msg, effective_user=SimpleNamespace(id=9))
    ctx = SimpleNamespace(user_data={})
    assert asyncio.run(bot._capture_voice_reason(update, ctx)) is False


def test_att_cancel_disarms_pend(monkeypatch):
    """att:cancel clears the armed pend (both stores) + resets stashes + shows a clean menu — the safe
    exit from an armed prompt (F5/Law 6), so no later stray message becomes a ghost submission."""
    from gm_bot import attendance_ui as ui
    import config
    import shared.database as db
    monkeypatch.setattr(db, "flow_clear", lambda uid: None)
    monkeypatch.setattr(ui, "_persona", lambda ctx: {"id": 1, "canonical_name": "X"})
    monkeypatch.setattr(ui, "main_menu", lambda p: ("MENU", None))
    edits = []

    async def _ans(*a, **k):
        pass

    async def _edit(text, reply_markup=None):
        edits.append(text)

    q = SimpleNamespace(data="att:cancel", answer=_ans, edit_message_text=_edit,
                        message=SimpleNamespace(message_id=5, chat_id=1))
    update = SimpleNamespace(callback_query=q,
                             effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID))
    ud = {"att_test_pending": {"flow": "al"}, "att_al_picked": {"d"}, "att_do_day": "x",
          "att_al_page": 3, "att_live_self": False}
    asyncio.run(ui.callback(update, SimpleNamespace(user_data=ud)))
    assert "att_test_pending" not in ud
    assert ud["att_al_picked"] == set()
    assert "att_do_day" not in ud and "att_al_page" not in ud
    assert edits and edits[0] == "MENU"


def test_armed_prompts_use_cancel_not_back():
    """The two armed-prompt builders must render ✕ Cancel (att:cancel), never a plain Back."""
    from gm_bot import attendance_ui as ui
    row = ui._cancel_row()
    assert row[0].callback_data == "att:cancel" and "Cancel" in row[0].text


# ── Stage 2: F2/F3 expiry push-nudge ──
def test_expiry_nudge_pushes_fresh_and_deletes_old():
    """The nudge deletes the stale card and pushes a FRESH 'NOT CONFIRMED' message carrying detail."""
    from gm_bot import bot
    sends, deletes = [], []

    async def _send(chat_id, text, reply_markup=None, parse_mode=None):
        sends.append((chat_id, text))

    async def _del(chat_id, message_id):
        deletes.append((chat_id, message_id))

    ctx = SimpleNamespace(bot=SimpleNamespace(delete_message=_del, send_message=_send))
    asyncio.run(bot._expiry_nudge(ctx, 7, "Death leave · 12–14 Jun", old_chat=7, old_msg=9))
    assert deletes == [(7, 9)]
    assert sends and sends[0][0] == 7
    assert "NOT CONFIRMED" in sends[0][1] and "Death leave" in sends[0][1]


def test_expired_tap_confirm_pushes_nudge(monkeypatch):
    """F2: tapping an expired '✅ I confirm' (no pend) pushes the nudge with the card's details +
    removes the stale card — instead of the old silent return."""
    from gm_bot import bot
    import config
    sends, deletes = [], []

    async def _send(chat_id, text, reply_markup=None, parse_mode=None):
        sends.append(text)

    async def _del(chat_id, message_id):
        deletes.append((chat_id, message_id))

    async def _ans(*a, **k):
        pass

    q = SimpleNamespace(data="att:go", answer=_ans,
                        message=SimpleNamespace(text="Death leave 12-14 Jun", chat_id=7, message_id=9))
    update = SimpleNamespace(callback_query=q,
                             effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
                             effective_chat=SimpleNamespace(id=7))
    ctx = SimpleNamespace(bot=SimpleNamespace(delete_message=_del, send_message=_send),
                          user_data={})   # no att_test_pending → expired path
    asyncio.run(bot._att_go_callback(update, ctx))
    assert deletes == [(7, 9)]
    assert sends and "NOT CONFIRMED" in sends[0] and "Death leave" in sends[0]


# ── Stage 3: F4/F8/F10/F12 guards ──
def _owner_cb(monkeypatch, data, user_data):
    """Drive attendance_ui.callback as the owner; return the list of edited texts."""
    from gm_bot import attendance_ui as ui
    import config
    monkeypatch.setattr(ui, "_persona", lambda ctx: {"id": 1, "canonical_name": "X", "call_name": "X"})
    edits = []

    async def _ans(*a, **k):
        pass

    async def _edit(text, reply_markup=None):
        edits.append(text)

    q = SimpleNamespace(data=data, answer=_ans, edit_message_text=_edit,
                        message=SimpleNamespace(message_id=5, chat_id=1))
    update = SimpleNamespace(callback_query=q,
                             effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID))
    user_data.setdefault("att_live_self", False)
    asyncio.run(ui.callback(update, SimpleNamespace(user_data=user_data)))
    return edits


def test_al_done_empty_picked_shows_stale(monkeypatch):
    """F4: tapping Done on a stale AL grid (empty picked) shows the stale screen, never a 0-day ghost."""
    edits = _owner_cb(monkeypatch, "att:al:done", {"att_al_picked": set()})
    assert edits and "old" in edits[0].lower()


def test_al_time_to_without_from_shows_stale(monkeypatch):
    """F4: the 'Until' tap with att_al_from popped used to crash — now shows the stale screen."""
    edits = _owner_cb(monkeypatch, "att:al:t:600", {"att_al_picked": {"2026-06-20"}})
    assert edits and "old" in edits[0].lower()


def test_swap_partner_without_day_shows_stale(monkeypatch):
    """F4: the partner tap with att_do_day missing used to fabricate a swap for TODAY — now stale."""
    from gm_bot import attendance_ui as ui
    monkeypatch.setattr(ui, "_armed", lambda ctx: True)
    edits = _owner_cb(monkeypatch, "att:do:p:2", {})
    assert edits and "old" in edits[0].lower()


def test_al_cov_empty_stash_shows_stale(monkeypatch):
    """F10: the 👁 toggle after a reset (empty att_al_cov) shows stale, not a blanked summary."""
    edits = _owner_cb(monkeypatch, "att:al:cov:1", {})
    assert edits and "old" in edits[0].lower()


def test_maintenance_toast_when_paused(monkeypatch):
    """F12: any staff tap while attendance_live is OFF gets a maintenance toast, not a dead button."""
    from gm_bot import attendance_ui as ui
    from gm_bot import bot
    monkeypatch.setattr(bot, "_attendance_live", lambda: False)
    answers = []

    async def _ans(text=None, show_alert=False, **k):
        answers.append((text, show_alert))

    q = SimpleNamespace(data="att:menu", answer=_ans,
                        message=SimpleNamespace(message_id=1, chat_id=1))
    update = SimpleNamespace(callback_query=q, effective_user=SimpleNamespace(id=424242))
    asyncio.run(ui.callback(update, SimpleNamespace(user_data={})))
    assert answers and answers[0][1] is True and "paused" in (answers[0][0] or "")


# ── Stage 4: photos try sick-papers FIRST ──
def _photo_router_calls(monkeypatch, paper_ret, voice_ret):
    from gm_bot import bot
    calls = []

    async def _paper(u, c):
        calls.append("paper")
        return paper_ret

    async def _voice(u, c):
        calls.append("voice")
        return voice_ret

    monkeypatch.setattr(bot, "_handle_sick_paper", _paper)
    monkeypatch.setattr(bot, "_capture_voice_reason", _voice)
    asyncio.run(bot._private_photo_router(SimpleNamespace(), SimpleNamespace()))
    return calls


def test_photo_papers_first_captured(monkeypatch):
    """An open sick case captures the photo as papers → the refuse path is never reached."""
    assert _photo_router_calls(monkeypatch, paper_ret=True, voice_ret=False) == ["paper"]


def test_photo_not_papers_falls_to_refuse(monkeypatch):
    """No open case → fall through to the voice/photo-on-a-reason-prompt refusal."""
    assert _photo_router_calls(monkeypatch, paper_ret=False, voice_ret=True) == ["paper", "voice"]


def test_photo_neither_passes_through(monkeypatch):
    """No case, no armed reason → both decline, nothing happens (no crash)."""
    assert _photo_router_calls(monkeypatch, paper_ret=False, voice_ret=False) == ["paper", "voice"]


# ── Stage 4: declare-Late-first ──
def test_late_declares_and_notifies_at_pick(monkeypatch):
    """Picking the minutes RECORDS the declaration (empty reason) + pushes the Supervisors heads-up
    immediately, and arms the pend with _declared — so points credit even if no reason follows."""
    from gm_bot import attendance_ui as ui
    from gm_bot import bot
    import shared.database as db
    import config
    declares, sends = [], []
    monkeypatch.setattr(db, "late_declare", lambda sid, fs, em, r: declares.append((sid, r)) or 1)
    monkeypatch.setattr(db, "flow_load", lambda uid: None)
    monkeypatch.setattr(ui, "att_test_on", lambda: True)
    monkeypatch.setattr(ui, "flow_save", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_persona", lambda ctx: {"id": 1, "canonical_name": "X", "call_name": "X",
                                                     "work_start": "07:00"})

    async def _send(context, suid, role, name, text, group=False, **k):
        sends.append(text)

    monkeypatch.setattr(bot, "_att_send", _send)
    edits = []

    async def _ans(*a, **k):
        pass

    async def _edit(text, reply_markup=None):
        edits.append(text)

    q = SimpleNamespace(data="att:late:o:30", answer=_ans, edit_message_text=_edit,
                        message=SimpleNamespace(message_id=5, chat_id=1))
    update = SimpleNamespace(callback_query=q, effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
                             effective_chat=SimpleNamespace(id=1))
    ud = {"att_persona": 1, "att_live_self": False}
    asyncio.run(ui.callback(update, SimpleNamespace(user_data=ud)))
    assert declares and declares[0][1] == ""              # declared at pick, reason empty
    assert sends and "late" in sends[0].lower()           # heads-up pushed now
    assert ud.get("att_test_pending", {}).get("_declared") is True
    assert edits and "notified" in edits[0].lower()


def _dispatch_late(monkeypatch, pend):
    from gm_bot import bot
    import shared.database as db
    import config
    sends, setr, declared = [], [], []
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [
        {"id": 1, "canonical_name": "X", "call_name": "X", "work_start": "07:00"}])

    async def _send(context, suid, role, name, text, group=False, **k):
        sends.append(text)

    monkeypatch.setattr(bot, "_att_send", _send)
    monkeypatch.setattr(db, "late_set_reason", lambda sid, fs, r: setr.append(r))
    monkeypatch.setattr(bot, "late_declare", lambda *a, **k: declared.append(1) or 1)
    replies = []

    async def _reply(t, reply_markup=None):
        replies.append(t)

    deletes = []

    async def _del(chat, msg):
        deletes.append((chat, msg))

    update = SimpleNamespace(message=SimpleNamespace(text="traffic jam", reply_text=_reply),
                             effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
                             effective_chat=SimpleNamespace(id=1))
    ctx = SimpleNamespace(bot=SimpleNamespace(delete_message=_del), user_data={})
    asyncio.run(bot._att_dispatch(update, ctx, pend, live=False))
    return sends, setr, declared, deletes


def test_late_dispatch_declared_attaches_reason(monkeypatch):
    """With _declared, the reason is ATTACHED (late_set_reason) — no duplicate late_declare — and sent
    as an addendum."""
    sends, setr, declared, _ = _dispatch_late(
        monkeypatch, {"flow": "late", "persona_id": 1, "mins": 30, "_declared": True})
    assert setr == ["traffic jam"] and not declared
    assert any("Reason from" in s for s in sends)


def test_late_dispatch_legacy_full_headsup(monkeypatch):
    """Without _declared (legacy), the full heads-up with reason goes out via late_declare."""
    sends, setr, declared, _ = _dispatch_late(
        monkeypatch, {"flow": "late", "persona_id": 1, "mins": 30})
    assert declared and not setr
    assert any("late for today's shift" in s for s in sends)


def test_late_dispatch_deletes_stale_prompt(monkeypatch):
    """Law 8 (Stage 4d): the consumed late reason-prompt is deleted so it doesn't sit stale."""
    sends, setr, declared, deletes = _dispatch_late(
        monkeypatch, {"flow": "late", "persona_id": 1, "mins": 30, "_declared": True,
                      "_prompt_chat": 7, "_prompt_msg": 9})
    assert deletes == [(7, 9)]


# ── Stage 4d: terminal Main-menu opens a NEW message ──
def test_menunew_opens_new_message(monkeypatch):
    """att:menunew posts a fresh menu message and does NOT edit over the terminal's details."""
    from gm_bot import attendance_ui as ui
    import config
    monkeypatch.setattr(ui, "_persona", lambda ctx: {"id": 1, "canonical_name": "X", "call_name": "X"})
    monkeypatch.setattr(ui, "main_menu", lambda p: ("MENU", None))
    replies, edits = [], []

    async def _ans(*a, **k):
        pass

    async def _edit(text, reply_markup=None):
        edits.append(text)

    async def _reply(text, reply_markup=None):
        replies.append(text)

    q = SimpleNamespace(data="att:menunew", answer=_ans, edit_message_text=_edit,
                        message=SimpleNamespace(message_id=5, chat_id=1, reply_text=_reply))
    update = SimpleNamespace(callback_query=q,
                             effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID))
    ud = {"att_al_picked": {"d"}, "att_live_self": False}
    asyncio.run(ui.callback(update, SimpleNamespace(user_data=ud)))
    assert replies == ["MENU"]          # NEW message
    assert edits == []                  # terminal NOT dissolved
    assert ud["att_al_picked"] == set()


# ── Stage 6: P1 menu singleton ──
def _claim_ctx(att_menu_msg=None):
    edits = []

    async def _edit(text, chat_id=None, message_id=None):
        edits.append((chat_id, message_id, text))

    ud = {}
    if att_menu_msg is not None:
        ud["att_menu_msg"] = att_menu_msg
    return SimpleNamespace(bot=SimpleNamespace(edit_message_text=_edit), user_data=ud), edits


def test_menu_claim_collapses_previous():
    """A new menu (different message) collapses the previously-registered one and becomes current."""
    from gm_bot import attendance_ui as ui
    ctx, edits = _claim_ctx(att_menu_msg=(1, 10))
    asyncio.run(ui._menu_claim(ctx, SimpleNamespace(chat_id=1, message_id=20)))
    assert len(edits) == 1 and edits[0][0] == 1 and edits[0][1] == 10
    assert "continues below" in edits[0][2]
    assert ctx.user_data["att_menu_msg"] == (1, 20)


def test_menu_claim_same_message_no_collapse():
    """Re-claiming the SAME message (in-place nav) must not collapse it."""
    from gm_bot import attendance_ui as ui
    ctx, edits = _claim_ctx(att_menu_msg=(1, 20))
    asyncio.run(ui._menu_claim(ctx, SimpleNamespace(chat_id=1, message_id=20)))
    assert edits == [] and ctx.user_data["att_menu_msg"] == (1, 20)


def test_menu_claim_no_previous_just_registers():
    """First menu — nothing to collapse, just register it."""
    from gm_bot import attendance_ui as ui
    ctx, edits = _claim_ctx()
    asyncio.run(ui._menu_claim(ctx, SimpleNamespace(chat_id=1, message_id=5)))
    assert edits == [] and ctx.user_data["att_menu_msg"] == (1, 5)


def test_menu_release_unregisters():
    """When a menu becomes a prompt, release so the singleton never collapses an awaiting message."""
    from gm_bot import attendance_ui as ui
    ctx = SimpleNamespace(user_data={"att_menu_msg": (1, 7)})
    ui._menu_release(ctx)
    assert "att_menu_msg" not in ctx.user_data


# ── A1 regression (Fable): the F8 typed-text trap ──
def test_reset_selection_clears_all_stashes():
    """reset_selection wipes EVERY per-flow stash, not just att_al_picked — so a completed/cancelled
    flow can't leave one behind that makes the F8 mid-pick guard fire forever."""
    from gm_bot import attendance_ui as ui
    ud = {"att_al_picked": {"d"}, "att_al_cov": {"x": 1}, "att_do_day": "z", "att_do_cov": {},
          "att_al_from": 5, "att_al_page": 2, "att_ci_armed": True}
    ui.reset_selection(SimpleNamespace(user_data=ud))
    assert ud["att_al_picked"] == set()
    for k in ("att_al_cov", "att_do_day", "att_do_cov", "att_al_from", "att_al_page", "att_ci_armed"):
        assert k not in ud, "%s should be cleared" % k


def test_dispatch_clears_selection_stashes(monkeypatch):
    """Submitting a flow clears the stale selection stashes (so later typed text isn't trapped by F8)."""
    from gm_bot import bot
    import shared.database as db
    import config
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [
        {"id": 1, "canonical_name": "X", "call_name": "X", "work_start": "07:00"}])

    async def _send(context, suid, role, name, text, group=False, **k):
        pass

    monkeypatch.setattr(bot, "_att_send", _send)
    monkeypatch.setattr(db, "late_set_reason", lambda *a, **k: None)

    async def _reply(t, reply_markup=None):
        pass

    async def _del(c, m):
        pass

    update = SimpleNamespace(message=SimpleNamespace(text="traffic", reply_text=_reply),
                             effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
                             effective_chat=SimpleNamespace(id=1))
    ud = {"att_al_picked": {"2026-06-20"}, "att_do_day": "x", "att_al_from": 5}
    ctx = SimpleNamespace(bot=SimpleNamespace(delete_message=_del), user_data=ud)
    asyncio.run(bot._att_dispatch(update, ctx, {"flow": "late", "persona_id": 1, "mins": 30,
                                                "_declared": True}, live=False))
    assert ud["att_al_picked"] == set() and "att_do_day" not in ud and "att_al_from" not in ud


# ── A2/A3: att:go nonce (double-tap + stale card) ──
def test_att_go_double_tap_says_already_confirmed(monkeypatch):
    """A2: a 2nd tap on an already-confirmed card (no pend, text shows ✅ Confirmed) gets a calm
    'already confirmed' toast — NOT the scary NOT-CONFIRMED nudge that invited a duplicate request."""
    from gm_bot import bot
    import config
    answers, sends, deletes = [], [], []

    async def _ans(text=None, show_alert=False, **k):
        answers.append(text)

    async def _send(*a, **k):
        sends.append(a)

    async def _del(*a, **k):
        deletes.append(a)

    q = SimpleNamespace(data="att:go:5", answer=_ans,
                        message=SimpleNamespace(text="Death leave\n\n✅ Confirmed.", chat_id=7, message_id=9))
    update = SimpleNamespace(callback_query=q, effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
                             effective_chat=SimpleNamespace(id=7))
    ctx = SimpleNamespace(bot=SimpleNamespace(send_message=_send, delete_message=_del), user_data={})
    asyncio.run(bot._att_go_callback(update, ctx))
    assert any("Already confirmed" in (a or "") for a in answers)
    assert sends == [] and deletes == []   # no nudge, no delete of the confirmed card


def test_att_go_stale_card_does_not_submit(monkeypatch):
    """A3: a stale card whose nonce ≠ the current pend must NOT submit that pend."""
    from gm_bot import bot
    import config
    answers, dispatched = [], []

    async def _ans(text=None, show_alert=False, **k):
        answers.append(text)

    async def _disp(*a, **k):
        dispatched.append(1)

    monkeypatch.setattr(bot, "_att_dispatch", _disp)
    q = SimpleNamespace(data="att:go:3", answer=_ans,
                        message=SimpleNamespace(text="Sick", chat_id=7, message_id=9))
    update = SimpleNamespace(callback_query=q, effective_user=SimpleNamespace(id=config.OWNER_TELEGRAM_ID),
                             effective_chat=SimpleNamespace(id=7))
    ud = {"att_test_pending": {"flow": "sick_me", "_go_nonce": "9"}}
    asyncio.run(bot._att_go_callback(update, SimpleNamespace(bot=SimpleNamespace(), user_data=ud)))
    assert any("Replaced" in (a or "") for a in answers)
    assert dispatched == [] and ud.get("att_test_pending")   # not submitted, pend intact


# ── A5: maintenance toast across staff handlers ──
def test_att_paused_toasts_staff_not_owner(monkeypatch):
    from gm_bot import bot
    import config
    monkeypatch.setattr(bot, "_attendance_live", lambda: False)
    answers = []

    async def _ans(text=None, show_alert=False, **k):
        answers.append((text, show_alert))

    assert asyncio.run(bot._att_paused(SimpleNamespace(answer=_ans), 99999)) is True
    assert answers and answers[0][1] is True and "paused" in (answers[0][0] or "")
    assert asyncio.run(bot._att_paused(SimpleNamespace(answer=_ans),
                                       config.OWNER_TELEGRAM_ID)) is False


# ── A6: media after expiry fires the honest nudge ──
def test_voice_after_expiry_fires_nudge(monkeypatch):
    from gm_bot import bot
    import shared.database as db
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)
    monkeypatch.setattr(bot, "_attendance_live", lambda: True)
    monkeypatch.setattr(db, "flow_load_or_expired",
                        lambda uid: (None, {"flow": "att_pending",
                                            "data": {"_summary": "AL", "_prompt_chat": 7, "_prompt_msg": 9}}))
    nudged = []

    async def _nudge(context, chat_id, detail="", old_chat=None, old_msg=None):
        nudged.append((chat_id, detail))

    monkeypatch.setattr(bot, "_expiry_nudge", _nudge)

    async def _reply(t):
        pass

    msg = SimpleNamespace(voice=True, photo=None, sticker=None, reply_text=_reply, chat_id=7, message_id=2)
    update = SimpleNamespace(message=msg, effective_user=SimpleNamespace(id=9))
    assert asyncio.run(bot._capture_voice_reason(update, SimpleNamespace(user_data={}))) is True
    assert nudged and nudged[0][1] == "AL"


def test_split_late_branches_for_points_display():
    """The 3 branches the test-sim points display reflects (declare-first credits the informed rate)."""
    from gm_bot.points import split_late
    assert split_late(30, -5) == (0, 30)     # declared BEFORE start → all informed (−1/min)
    assert split_late(30, 10) == (10, 20)    # declared 10 min after start → 10 uninformed + 20 informed
    assert split_late(30, None) == (30, 0)   # never declared → all uninformed (−2/min)
