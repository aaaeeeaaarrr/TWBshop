"""LIVE staff entry for the attendance flows (session 30).

Covers the genuinely-new surface: persona LOCKED to self, the menu hides persona-switching for
live staff, terminals are 'armed' for live, and the unified dispatcher diverges correctly between
live (act as self, real recipients, late=declare-only) and test (owner persona, routed to owner,
late collapses declare+arrival). No real Telegram I/O; DB calls are monkeypatched.
"""
import asyncio
import types

from gm_bot import attendance_ui as ui


# ---- fakes -------------------------------------------------------------------

class _Ctx:
    def __init__(self):
        self.user_data = {}
        self.bot = None


class _Msg:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, t, **k):
        self.replies.append(t)


class _Update:
    def __init__(self, uid, text=""):
        self.message = _Msg(text)
        self.effective_user = types.SimpleNamespace(id=uid)


_PERSONA = {"id": 11, "canonical_name": "Sao Visal", "call_name": "Visal",
            "work_start": "08:00", "work_end": "17:00", "org": "TWB", "status": "active"}


# ---- header / menu: live vs test --------------------------------------------

def test_hdr_live_has_no_test_banner():
    live = dict(_PERSONA); live["_live"] = True
    assert "🧪" not in ui._hdr(live, "hi")
    assert "👤" in ui._hdr(live, "hi")
    # owner shell keeps the TEST banner
    assert "🧪 TEST" in ui._hdr(_PERSONA, "hi")


def test_main_menu_hides_persona_switch_for_live():
    live = dict(_PERSONA); live["_live"] = True
    _, kb_live = ui.main_menu(live)
    _, kb_test = ui.main_menu(_PERSONA)
    flat_live = [b.callback_data for row in kb_live.inline_keyboard for b in row]
    flat_test = [b.callback_data for row in kb_test.inline_keyboard for b in row]
    assert "att:pick" not in flat_live          # a live staffer can never switch persona
    assert "att:pick" in flat_test               # the owner role-play shell still can
    # the real action buttons are present in BOTH (same code path, no fork)
    for cd in ("att:ci", "att:late", "att:aw", "att:am"):
        assert cd in flat_live and cd in flat_test


# ---- armed gating ------------------------------------------------------------

def test_armed_true_for_live_even_when_test_off(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    ctx = _Ctx(); ctx.user_data["att_live_self"] = True
    assert ui._is_live(ctx) is True
    assert ui._armed(ctx) is True
    # a non-live, non-test context is NOT armed (terminals show read-only previews)
    assert ui._armed(_Ctx()) is False


def test_armed_true_in_test_mode(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: True)
    assert ui._armed(_Ctx()) is True


def test_persona_annotates_live(monkeypatch):
    monkeypatch.setattr(ui, "staff_all", lambda *_a, **_k: [_PERSONA])
    ctx = _Ctx(); ctx.user_data["att_persona"] = 11; ctx.user_data["att_live_self"] = True
    p = ui._persona(ctx)
    assert p["_live"] is True and p["id"] == 11
    # owner shell (no att_live_self): plain record, no _live flag
    ctx2 = _Ctx(); ctx2.user_data["att_persona"] = 11
    assert "_live" not in ui._persona(ctx2)


def test_arm_pending_routes_to_flow_state_when_live(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    saved = {}
    monkeypatch.setattr(ui, "flow_save",
                        lambda uid, flow, step, data, ttl_min=None: saved.update(
                            uid=uid, flow=flow, step=step, data=data))
    ctx = _Ctx(); ctx.user_data["att_live_self"] = True
    ui._arm_pending(ctx, _Update(777), {"flow": "al", "days": ["2026-06-20"]})
    assert saved["uid"] == 777 and saved["flow"] == "att_pending"
    assert saved["data"]["flow"] == "al"
    assert "att_test_pending" not in ctx.user_data     # live does NOT use user_data


def test_arm_pending_uses_user_data_in_test(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: True)
    ctx = _Ctx()
    ui._arm_pending(ctx, _Update(777), {"flow": "al"})
    assert ctx.user_data["att_test_pending"]["flow"] == "al"


# ---- dispatcher: LIVE late = declare-only (no payback at declare) ------------

def test_dispatch_late_live_declares_only(monkeypatch):
    from gm_bot import bot
    import datetime as _dt
    monkeypatch.setattr(bot, "_now_pp", lambda: _dt.datetime(2026, 6, 11, 12, 0, tzinfo=bot.finance.PP_TZ))
    calls = {"late": 0, "payback": 0, "offer": 0, "send": 0}

    async def _send(*a, **k):
        calls["send"] += 1

    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: dict(_PERSONA))
    monkeypatch.setattr(bot, "late_declare", lambda *a, **k: calls.__setitem__("late", calls["late"] + 1))
    monkeypatch.setattr(bot, "payback_add_debt",
                        lambda *a, **k: calls.__setitem__("payback", calls["payback"] + 1))

    async def _offer(*a, **k):
        calls["offer"] += 1

    monkeypatch.setattr(bot, "_att_send", _send)
    monkeypatch.setattr(bot, "_offer_payback", _offer)

    upd = _Update(uid=555, text="traffic")
    ctx = _Ctx()
    asyncio.run(bot._att_dispatch(upd, ctx, {"flow": "late", "mins": 30}, live=True))

    assert calls["late"] == 1          # heads-up declared
    assert calls["send"] == 1          # Supervisors notice
    assert calls["payback"] == 0       # NO debt at declare (that happens on arrival via location)
    assert calls["offer"] == 0         # NO slot picker at declare
    assert upd.message.replies and "live location" in upd.message.replies[0].lower()


def test_dispatch_al_edits_prompt_into_awaiting_card(monkeypatch):
    """Typing the reason edits the reason-prompt in place into the requester's OWN AL card: request
    line + reason + '⏳ Awaiting approval', carrying the persistent Show-who's-working toggle, and
    registered in al_staff_cards so _al_finalize can flip it to 'decided'."""
    from gm_bot import bot
    edited = []

    class _Bot:
        async def edit_message_text(self, t, chat_id=None, message_id=None,
                                    reply_markup=None, parse_mode=None):
            edited.append((t, chat_id, message_id, reply_markup))

    async def _submit(*a, **k):
        return 77

    persona = dict(_PERSONA)
    req = {"id": 77, "staff_id": 11, "days": ["2026-06-20"], "reason": "dentist", "kind": "days",
           "status": "pending", "hours_start": None, "hours_end": None}
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: persona)
    monkeypatch.setattr(bot, "submit_al_request", _submit)
    monkeypatch.setattr(bot, "al_get_request", lambda i: req)
    monkeypatch.setattr(bot, "staff_absent_dates", lambda sid: set())
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [persona])

    upd = _Update(uid=555, text="dentist")
    ctx = _Ctx(); ctx.bot = _Bot(); ctx.bot_data = {}
    pend = {"flow": "al", "kind": "days", "days": ["2026-06-20"],
            "hours_start": None, "hours_end": None,
            "_summary": "AL: Sat 20/06 — 1 AL day(s).", "_prompt_chat": 555, "_prompt_msg": 42}
    asyncio.run(bot._att_dispatch(upd, ctx, pend, live=True))

    assert edited, "staff card not rendered"
    card, chat_id, msg_id, kb = edited[-1]
    assert chat_id == 555 and msg_id == 42
    assert "requests AL" in card            # the request line
    assert "dentist" in card                # the typed reason
    assert "Awaiting approval" in card      # the new state
    assert ctx.bot_data["al_staff_cards"][77] == (555, 42)       # registered for finalize
    btns = [b.text for row in kb.inline_keyboard for b in row]
    assert any("who's working" in b for b in btns)              # persistent toggle


def test_dispatch_al_blocks_over_balance(monkeypatch):
    """Requesting more AL than the balance → the STAFF is told to pick a smaller amount; the request
    is NOT submitted (seniors aren't bothered with an impossible request)."""
    from gm_bot import bot
    submitted = []

    async def _submit(*a, **k):
        submitted.append(1)
        return 1

    persona = dict(_PERSONA); persona["al_left"] = 1.0; persona["day_off"] = "Sun"
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: persona)
    monkeypatch.setattr(bot, "submit_al_request", _submit)
    monkeypatch.setattr(bot, "staff_absent_dates", lambda sid: set())
    monkeypatch.setattr(bot, "_now_pp",
                        lambda: __import__("datetime").datetime(2026, 6, 11, 12, 0, tzinfo=bot.finance.PP_TZ))
    upd = _Update(uid=555, text="holiday")
    pend = {"flow": "al", "kind": "days",
            "days": ["2026-06-22", "2026-06-23", "2026-06-24"]}      # 3 working days > 1 AL
    asyncio.run(bot._att_dispatch(upd, _Ctx(), pend, live=True))
    assert submitted == []                                            # NOT submitted
    assert upd.message.replies and "only have 1" in upd.message.replies[0]
    assert "3" in upd.message.replies[0]                             # shows the requested amount


def test_dispatch_al_within_balance_submits(monkeypatch):
    """A request within balance goes through to submit (the guard only blocks over-balance)."""
    from gm_bot import bot
    submitted = []

    async def _submit(*a, **k):
        submitted.append(1)
        return 1

    persona = dict(_PERSONA); persona["al_left"] = 5.0; persona["day_off"] = "Sun"
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: persona)
    monkeypatch.setattr(bot, "submit_al_request", _submit)
    monkeypatch.setattr(bot, "al_get_request", lambda i: None)
    monkeypatch.setattr(bot, "staff_absent_dates", lambda sid: set())
    monkeypatch.setattr(bot, "_now_pp",
                        lambda: __import__("datetime").datetime(2026, 6, 11, 12, 0, tzinfo=bot.finance.PP_TZ))
    upd = _Update(uid=555, text="holiday")
    pend = {"flow": "al", "kind": "days", "days": ["2026-06-22", "2026-06-23"]}   # 2 ≤ 5
    asyncio.run(bot._att_dispatch(upd, _Ctx(), pend, live=True))
    assert submitted == [1]                                           # submitted normally


def test_dispatch_late_test_defers_to_simulate_arrival(monkeypatch):
    """TEST late: declare = heads-up only + a 'simulate arrival' button. NO auto-payback (it now
    mirrors live — the picker comes from the simulate-arrival tap)."""
    from gm_bot import bot
    import datetime as _dt
    monkeypatch.setattr(bot, "_now_pp", lambda: _dt.datetime(2026, 6, 11, 12, 0, tzinfo=bot.finance.PP_TZ))
    calls = {"payback": 0, "offer": 0}

    async def _send(*a, **k):
        pass

    async def _offer(*a, **k):
        calls["offer"] += 1

    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [dict(_PERSONA)])
    monkeypatch.setattr(bot, "late_declare", lambda *a, **k: None)
    monkeypatch.setattr(bot, "_att_send", _send)
    monkeypatch.setattr(bot, "payback_add_debt",
                        lambda *a, **k: calls.__setitem__("payback", calls["payback"] + 1))
    monkeypatch.setattr(bot, "_offer_payback", _offer)

    upd = _Update(uid=bot.config.OWNER_TELEGRAM_ID, text="traffic")
    ctx = _Ctx()
    asyncio.run(bot._att_dispatch(upd, ctx,
                {"flow": "late", "persona_id": 11, "mins": 30}, live=False))

    assert calls["payback"] == 0 and calls["offer"] == 0          # deferred — no auto-collapse
    assert upd.message.replies and "simulate" in upd.message.replies[0].lower()


def test_late_simarr_fires_payback(monkeypatch):
    """Tapping 'simulate arrival' in test fires the real payback debt + slot picker."""
    from gm_bot import bot
    calls = {"payback": 0, "offer": 0}
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [dict(_PERSONA)])
    monkeypatch.setattr(bot, "payback_add_debt",
                        lambda *a, **k: calls.__setitem__("payback", calls["payback"] + 1))
    monkeypatch.setattr(bot, "payback_open_debt", lambda *a, **k: {"balance": 30})

    async def _offer(*a, **k):
        calls["offer"] += 1

    monkeypatch.setattr(bot, "_offer_payback", _offer)
    upd = _CbUpdate(bot.config.OWNER_TELEGRAM_ID, "att:simarr:11:late:30")
    asyncio.run(bot._late_simarr_callback(upd, _Ctx()))
    assert calls["payback"] == 1 and calls["offer"] == 1


def test_late_simarr_ontime_is_free(monkeypatch):
    """Simulating an on-time (±5) arrival → free: no payback, just the Checked-in verdict."""
    from gm_bot import bot
    calls = {"payback": 0, "sent": 0}
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [dict(_PERSONA)])
    monkeypatch.setattr(bot, "payback_add_debt",
                        lambda *a, **k: calls.__setitem__("payback", calls["payback"] + 1))

    async def _send(*a, **k):
        calls["sent"] += 1

    monkeypatch.setattr(bot, "_att_send", _send)
    upd = _CbUpdate(bot.config.OWNER_TELEGRAM_ID, "att:simarr:11:ontime")
    asyncio.run(bot._late_simarr_callback(upd, _Ctx()))
    assert calls["payback"] == 0 and calls["sent"] == 1   # free — verdict only, no payback


def test_present_now_for_ot(monkeypatch):
    """⚡ Now OT must offer only staff on shift now or finished < 1h ago — not the whole roster."""
    import datetime as _dt
    monkeypatch.setattr(ui, "_today", lambda: _dt.date(2026, 6, 8))   # a Monday
    monkeypatch.setattr(ui, "al_leave_days_set", lambda sid: set())
    r = {"id": 1, "work_start": "08:00", "work_end": "17:00", "day_off": "Sun"}  # ws=480, ln=540
    monkeypatch.setattr(ui, "_now_min", lambda: 600);  assert ui._present_now(r)        # 10:00 on shift
    monkeypatch.setattr(ui, "_now_min", lambda: 1050); assert ui._present_now(r)        # 17:30 ended 30m
    monkeypatch.setattr(ui, "_now_min", lambda: 1085); assert not ui._present_now(r)    # 18:05 ended 65m
    monkeypatch.setattr(ui, "_now_min", lambda: 400);  assert not ui._present_now(r)    # 06:40 pre-shift
    monkeypatch.setattr(ui, "_now_min", lambda: 600)
    assert not ui._present_now({**r, "day_off": "Mon"})                                 # day off today
    monkeypatch.setattr(ui, "al_leave_days_set", lambda sid: {"2026-06-08"})
    assert not ui._present_now(r)                                                       # AL today


def test_copy_test_rows_builds_is_test_insert():
    """/testseed core: copy real rows → is_test=TRUE duplicates, id excluded, columns passed
    through, is_test forced TRUE. DB-free (fake cursor) so the suite never writes to prod."""
    from shared.database import _copy_test_rows

    class FakeCur:
        def __init__(self):
            self.sql = []

        def execute(self, q, params=None):
            self.sql.append(q)

        def fetchall(self):
            # emulate information_schema already excluding 'id' (WHERE column_name <> 'id')
            return [{"column_name": "staff_id"}, {"column_name": "days"},
                    {"column_name": "is_test"}]

        @property
        def rowcount(self):
            return 2

    cur = FakeCur()
    n = _copy_test_rows(cur, "al_requests", "AND status='approved'")
    assert n == 2
    insert = cur.sql[-1]
    assert insert == ("INSERT INTO al_requests (staff_id, days, is_test) "
                      "SELECT staff_id, days, TRUE FROM al_requests "
                      "WHERE is_test=FALSE AND status='approved'")


class _Query:
    def __init__(self, data):
        self.data = data
        self.edited = []
        self.message = types.SimpleNamespace(text="card")

    async def answer(self, *a, **k):
        pass

    async def edit_message_text(self, t, **k):
        self.edited.append(t)


class _CbUpdate:
    def __init__(self, uid, data):
        self.callback_query = _Query(data)
        self.effective_user = types.SimpleNamespace(id=uid)
        self.effective_chat = types.SimpleNamespace(id=uid, type="private")


def test_reason_terminals_format_bilingual(monkeypatch):
    """Drive the REAL callback for every %-formatted terminal — proves the prompts format without a
    ValueError (the runtime risk from Khmer with embedded numbers). The /test shell stays BILINGUAL
    for the owner (only message BODIES are stripped), so the English AND Khmer both render."""
    import config
    monkeypatch.setattr(ui, "staff_all", lambda *a, **k: [dict(_PERSONA)])
    monkeypatch.setattr(ui, "att_test_on", lambda: True)         # armed (owner test mode)
    monkeypatch.setattr(ui, "flow_save", lambda *a, **k: None)
    cases = [
        ("att:scp:cf:11:0:780:1140", "Shift change"),     # shift redefine 1pm-7pm
        ("att:late:o:30", "30 min"),                       # late ~30 min (2× %d)
        ("att:sp:mard:2026-06-25", "Marriage leave"),      # marriage 3 days (%d %s %d)
        ("att:sp:famf:mother:2026-06-25", "Family sick"),  # family sick (2× %s)
        ("att:al:full", "AL"),                              # AL full-day suffix
    ]
    for data, needle in cases:
        upd = _CbUpdate(config.OWNER_TELEGRAM_ID, data)
        ctx = _Ctx(); ctx.user_data["att_persona"] = 11
        asyncio.run(ui.callback(upd, ctx))
        out = upd.callback_query.edited[-1]
        assert needle in out, "%s → missing %r in: %s" % (data, needle, out[:120])
    # shell keeps Khmer (the shift-redefine prompt is bilingual) — routed bodies stay English-only
    upd = _CbUpdate(config.OWNER_TELEGRAM_ID, "att:scp:cf:11:0:780:1140")
    ctx = _Ctx(); ctx.user_data["att_persona"] = 11
    asyncio.run(ui.callback(upd, ctx))
    assert "មូលហេតុ" in upd.callback_query.edited[-1]


def test_al_summary_bold_spaced_english():
    """AL request line: English only, BOLD from→to dates."""
    from gm_bot import bot
    s = bot._al_summary("Pisey", ["2026-06-21", "2026-06-22"], "country side")
    assert "<b>Sun 21/06 → Mon 22/06</b>" in s   # consecutive days collapse to a from→to range
    assert "requests AL" in s and "country side" in s
    assert "ស" not in s                          # no Khmer


def test_al_day_off_excluded_and_span_bridges():
    """A day off inside the leave is never charged AL, and the span shows from→to across it."""
    from gm_bot import al as alm
    days = ["2026-06-23", "2026-06-24", "2026-06-25"]   # Tue, Wed(off), Thu
    assert alm.al_day_count(days, "days", day_off="Wed") == 2.0          # Wed not charged
    assert alm.al_charged_days(days, "Wed") == ["2026-06-23", "2026-06-25"]
    assert alm.al_span_label(days, "Wed") == "Tue 23/06 → Thu 25/06"     # bridges the day off
    # day off NOT clicked, but still bridged (out from first to last)
    assert alm.al_span_label(["2026-06-23", "2026-06-25"], "Wed") == "Tue 23/06 → Thu 25/06"
    # a real WORKING-day gap does NOT bridge (never imply days he works)
    gap = alm.al_span_label(["2026-06-22", "2026-06-26"], "Wed")
    assert "→" not in gap and "Mon 22/06" in gap and "Fri 26/06" in gap
    # no day_off → everything counts
    assert alm.al_day_count(days, "days") == 3.0


def test_public_holidays_placeholder(monkeypatch):
    """PH placeholder: empty by default, parses the gm_state JSON list when set."""
    from shared import database as db
    monkeypatch.setattr(db, "gm_get_state", lambda k: None)
    assert db.public_holidays() == set()                       # empty until holidays are added
    monkeypatch.setattr(db, "gm_get_state", lambda k: '["2026-04-14", "2026-04-15"]')
    assert db.public_holidays() == {"2026-04-14", "2026-04-15"}


def test_al_span_bridges_any_absence():
    """The span bridges ANY non-working day (other AL, PH, swap…), not just the weekly day off."""
    from gm_bot import al as alm
    picked = ["2026-06-22", "2026-06-25"]                 # Mon, Thu
    nw = {"2026-06-23", "2026-06-24"}                      # Tue+Wed = e.g. another AL + a PH
    assert alm.al_span_label(picked, non_working=nw) == "Mon 22/06 → Thu 25/06"
    # without the absence info, a genuine working gap does NOT bridge
    assert "→" not in alm.al_span_label(picked, non_working=set())
    # a tapped day that's already an absence isn't charged again
    assert alm.al_day_count(["2026-06-22", "2026-06-23"], "days", non_working={"2026-06-23"}) == 1.0


def test_al_finalize_edits_cards_in_place(monkeypatch):
    """On decision the senior cards are EDITED in place (request intact + verdict); no new
    per-senior messages; requester + Supervisors notices still sent."""
    from gm_bot import bot
    edits, roles = [], []
    g = {"id": 50, "staff_id": 2, "days": ["2026-06-21"], "reason": "r", "kind": "days",
         "status": "pending", "hours_start": None, "hours_end": None}
    monkeypatch.setattr(bot, "al_get_request", lambda i: g)
    monkeypatch.setattr(bot, "al_set_status", lambda i, st: g.__setitem__("status", st))
    monkeypatch.setattr(bot, "staff_absent_dates", lambda sid: set())
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [
        {"id": 2, "canonical_name": "Pisey", "call_name": "Pisey", "telegram_ids": [222],
         "work_start": "08:00", "work_end": "17:00", "day_off": "Sun"}])
    monkeypatch.setattr(bot, "al_get_approvals", lambda i: [
        {"decision": "approve", "canonical_name": "A", "call_name": "A"},
        {"decision": "approve", "canonical_name": "B", "call_name": "B"}])
    monkeypatch.setattr(bot, "al_deduct", lambda sid, amt: 5)
    monkeypatch.setattr(bot, "_seniors", lambda exclude_staff_id=None: [])

    async def _send(ctx, to_uid, role, to_name, text, kb=None, group=False, parse_mode=None):
        roles.append(role)

    monkeypatch.setattr(bot, "_att_send", _send)

    class _Bot:
        async def edit_message_text(self, text, chat_id=None, message_id=None,
                                    parse_mode=None, reply_markup=None):
            edits.append((chat_id, message_id, text, reply_markup))

    ctx = _Ctx()
    ctx.bot = _Bot()
    ctx.bot_data = {"al_cards": {50: [(111, 7), (111, 8)]}}
    asyncio.run(bot._al_finalize(ctx, g, approved=True))
    assert len(edits) == 2                                   # both cards edited in place
    assert "Approved by A and B" in edits[0][2]
    assert "Senior" not in roles                             # NO new per-senior message
    assert "Requester" in roles and "Supervisors group" in roles
    # the decided senior card KEEPS the Show-who's-working toggle
    tog = [b.text for row in edits[0][3].inline_keyboard for b in row]
    assert any("who's working" in b for b in tog)


def test_al_availability_excludes_delis(monkeypatch):
    """Coverage 'working those days' is TWB-only — Delis staff must never leak in."""
    from gm_bot import bot
    req = {"id": 1, "work_start": "08:00", "work_end": "17:00", "org": "TWB", "day_off": "Sun",
           "canonical_name": "Req", "call_name": "Req"}
    twb = {"id": 2, "work_start": "08:00", "work_end": "17:00", "org": "TWB", "day_off": "Mon",
           "canonical_name": "TwbMate", "call_name": "TwbMate"}
    delis = {"id": 3, "work_start": "08:00", "work_end": "17:00", "org": "DELIS", "day_off": "Mon",
             "canonical_name": "DelisMate", "call_name": "DelisMate"}
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [req, twb, delis])
    monkeypatch.setattr(bot, "al_pending_requests", lambda: [])
    out = bot._al_availability_lines(req, ["2026-06-23"])   # Tuesday — nobody's day off
    assert "TwbMate" in out
    assert "DelisMate" not in out


def test_swap_apply_edits_senior_cards(monkeypatch):
    """Day-off swap decision edits the senior cards in place (request intact + verdict)."""
    from gm_bot import bot
    edits, roles = [], []
    sw = {"id": 9, "requester_id": 1, "partner_id": 2, "req_off_date": "2026-06-21",
          "partner_off_date": "2026-06-24", "reason": "x", "status": "partner_ok"}
    monkeypatch.setattr(bot, "swap_get", lambda i: sw)
    monkeypatch.setattr(bot, "swap_set_status", lambda i, st: sw.__setitem__("status", st))
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [
        {"id": 1, "canonical_name": "Req", "call_name": "Req", "telegram_ids": [11]},
        {"id": 2, "canonical_name": "Par", "call_name": "Par", "telegram_ids": [22]}])
    monkeypatch.setattr(bot, "dayoff_set_override", lambda *a, **k: None)

    async def _send(ctx, to_uid, role, to_name, text, kb=None, group=False, parse_mode=None):
        roles.append(role)

    monkeypatch.setattr(bot, "_att_send", _send)

    class _Bot:
        async def edit_message_text(self, text, chat_id=None, message_id=None,
                                    parse_mode=None, reply_markup=None):
            edits.append((chat_id, message_id, text, reply_markup))

    ctx = _Ctx()
    ctx.bot = _Bot()
    ctx.bot_data = {"swap_cards": {9: [(111, 5), (111, 6)]}}
    asyncio.run(bot._swap_apply(ctx, sw, approved=True))
    assert len(edits) == 2
    assert "✅ Approved" in edits[0][2] and "Day-off swap" in edits[0][2]
    assert "Requester" in roles and "Partner" in roles and "Supervisors group" in roles
    # the decided senior swap card KEEPS the both-days Show-who's-working toggle
    tog = [b.text for row in edits[0][3].inline_keyboard for b in row]
    assert any("who's working" in b for b in tog)


def test_al_prompt_coverage_toggle(monkeypatch):
    """The AL reason PROMPT (before typing) carries a 👁 Show-who's-working toggle, computed live from
    the in-progress selection and stashed so the toggle can re-render."""
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    from gm_bot import bot
    p = {"id": 11, "canonical_name": "Visal", "call_name": "Visal",
         "work_start": "08:00", "work_end": "17:00"}
    ctx = _Ctx()
    text, kb = ui._al_prompt(p, ctx, "AL: Sat 20/06 — 1 AL day(s).", ["2026-06-20"], None, None, False)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("Show who's working" in l for l in labels)
    assert "Working those" not in text
    assert ctx.user_data["att_al_cov"]["days"] == ["2026-06-20"]     # stashed for the toggle

    monkeypatch.setattr(bot, "_al_availability_lines", lambda *a, **k: "Sat 20/06: Other")
    text2, kb2 = ui._al_prompt(p, ctx, "AL: Sat 20/06 — 1 AL day(s).", ["2026-06-20"], None, None, True)
    assert "Working those days" in text2 and "Other" in text2
    labels2 = [b.text for row in kb2.inline_keyboard for b in row]
    assert any("Hide who's working" in l for l in labels2)


def test_swap_prompt_coverage_toggle(monkeypatch):
    """The day-off-swap reason PROMPT (before typing) also carries a both-days Show-who's-working
    toggle, computed live from the picked dates and stashed for re-render."""
    monkeypatch.setattr(ui, "att_test_on", lambda: False)
    from gm_bot import bot
    monkeypatch.setattr(ui, "staff_all", lambda *a, **k: [
        {"id": 2, "canonical_name": "Par", "call_name": "Par", "work_start": "08:00",
         "work_end": "17:00", "org": "TWB", "day_off": "Wed"}])
    p = {"id": 1, "canonical_name": "Req", "call_name": "Req", "work_start": "08:00", "work_end": "17:00"}
    ctx = _Ctx()
    text, kb = ui._swap_prompt(p, ctx, "Day-off swap — your off Sun ↔ partner off Wed.",
                               2, "2026-06-21", "2026-06-24", False)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("Show who's working" in l for l in labels)
    assert "Working those" not in text
    assert ctx.user_data["att_do_cov"]["partner_id"] == 2

    monkeypatch.setattr(bot, "_al_availability_lines", lambda req, days, *a, **k: "%s: X" % days[0])
    text2, kb2 = ui._swap_prompt(p, ctx, "base", 2, "2026-06-21", "2026-06-24", True)
    assert "Working those days" in text2 and "2026-06-21" in text2 and "2026-06-24" in text2
    labels2 = [b.text for row in kb2.inline_keyboard for b in row]
    assert any("Hide who's working" in l for l in labels2)


def test_swap_senior_card_states_and_both_days_toggle(monkeypatch):
    """The senior day-off-swap card: Approve+toggle while partner_ok; expanded shows BOTH affected
    days' coverage; once decided the verdict shows and the toggle STAYS (no Approve)."""
    from gm_bot import bot
    roster = [
        {"id": 1, "canonical_name": "Req", "call_name": "Req", "work_start": "08:00",
         "work_end": "17:00", "org": "TWB", "day_off": "Sun"},
        {"id": 2, "canonical_name": "Par", "call_name": "Par", "work_start": "08:00",
         "work_end": "17:00", "org": "TWB", "day_off": "Wed"},
        {"id": 3, "canonical_name": "Other", "call_name": "Other", "work_start": "08:00",
         "work_end": "17:00", "org": "TWB", "day_off": "Mon"}]
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: roster)
    req, partner = roster[0], roster[1]
    sw = {"id": 9, "requester_id": 1, "partner_id": 2, "req_off_date": "2026-06-21",   # Sun
          "partner_off_date": "2026-06-24", "reason": "x", "status": "partner_ok"}     # Wed

    body, kb = bot._swap_card(sw, req, partner, audience="senior", show_cov=False)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("Approve" in l for l in labels) and any("Show who's working" in l for l in labels)
    assert "Working those days" not in body

    body2, _ = bot._swap_card(sw, req, partner, audience="senior", show_cov=True)
    assert "Working those days" in body2
    assert "Sun 21/06" in body2 and "Wed 24/06" in body2     # BOTH affected days

    sw["status"] = "approved"
    body3, kb3 = bot._swap_card(sw, req, partner, audience="senior", show_cov=False)
    assert "✅ Approved" in body3
    labels3 = [b.text for row in kb3.inline_keyboard for b in row]
    assert not any("Approve" in l for l in labels3)          # decided → no Approve
    assert any("Show who's working" in l for l in labels3)   # toggle persists


def test_ot_now_end_times_latest_per_staff(monkeypatch):
    """A 2nd Now-OT extends, not duplicates — ot_now_end_times returns the LATEST end per staff,
    as a tz-aware DATETIME (midnight-safe), and an overnight grant from yesterday is included."""
    from shared import database as db
    from datetime import timezone
    rows = [
        {"staff_id": 2, "when_date": "2026-06-09", "start_min": 960, "minutes": 120},  # 16:00 +2h = 18:00
        {"staff_id": 2, "when_date": "2026-06-09", "start_min": 960, "minutes": 240},  # 16:00 +4h = 20:00 (wins)
        {"staff_id": 5, "when_date": "2026-06-09", "start_min": 1020, "minutes": 60},  # 17:00 +1h = 18:00
        {"staff_id": 9, "when_date": "2026-06-08", "start_min": 1380, "minutes": 180}, # 23:00 yest +3h = 02:00 today
        {"staff_id": 7, "when_date": "2026-06-09", "start_min": None, "minutes": 60},  # ignored (no start)
    ]

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return rows

    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False

    class _Conn:
        def cursor(self): return _CM(_Cur())

    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))
    out = db.ot_now_end_times("2026-06-09", timezone.utc)
    assert (out[2].hour, out[2].minute) == (20, 0) and out[2].date().isoformat() == "2026-06-09"
    assert (out[5].hour, out[5].minute) == (18, 0)
    assert (out[9].hour, out[9].minute) == (2, 0) and out[9].date().isoformat() == "2026-06-09"  # crossed midnight
    assert 7 not in out


def test_staff_day_events_redefine_override():
    """A redefined shift fires the day's prompts at the REDEFINED start/length, not the normal sched."""
    p = {"work_start": "08:00", "work_end": "17:00"}    # normal ws=480, len=540
    base = ui.staff_day_events(p)
    assert any(m == 480 and lbl.startswith("T0") for _o, m, lbl in base)            # normal T0 = 8:00
    red = ui.staff_day_events(p, ws_override=780, len_override=360)                 # 1pm start, 6h
    assert any(m == 780 and lbl.startswith("T0") for _o, m, lbl in red)            # redefined T0 = 1pm
    assert any(m == 770 and lbl.startswith("T−10") for _o, m, lbl in red)          # T−10 = 12:50
    assert any(m == 1140 and lbl.startswith("check-out") for _o, m, lbl in red)    # checkout = 7pm


def test_compute_day_events_uses_redefine(monkeypatch):
    """compute_day_events shifts a staffer's whole prompt schedule to the approved redefine."""
    from shared import database as db
    import datetime as _dt
    target = _dt.date(2026, 6, 15)   # a Monday
    p = {"id": 7, "canonical_name": "X", "call_name": "X", "org": "TWB",
         "work_start": "08:00", "work_end": "17:00", "day_off": "Sun"}
    monkeypatch.setattr(ui, "staff_all", lambda *a, **k: [p])

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return []          # no approved al_requests
    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False
    class _Conn:
        def cursor(self): return _CM(_Cur())
    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))
    monkeypatch.setattr(db, "dayoff_override_for", lambda sid, iso: None)

    # no redefine → normal T0 at 8:00 (480)
    monkeypatch.setattr(db, "shift_changes_active_map", lambda days: {})
    t0 = [m for m, _n, lbl, _t, _sd in ui.compute_day_events(target) if lbl.startswith("T0")]
    assert t0 == [480]

    # redefine on target: 1pm–7pm → T0 at 780, checkout at 1140
    monkeypatch.setattr(db, "shift_changes_active_map",
                        lambda days: {(7, target.isoformat()): (780, 1140)})
    ev = ui.compute_day_events(target)
    assert [m for m, _n, lbl, _t, _sd in ev if lbl.startswith("T0")] == [780]
    assert any(m == 1140 and lbl.startswith("check-out") for m, _n, lbl, _t, _sd in ev)


def test_compute_day_events_overnight_carries_shift_date(monkeypatch):
    """OVERNIGHT (the bakers, 9pm–6am): the 6am checkout fires today but belongs to YESTERDAY's
    shift — the event must carry the START date so the checkout write + OT settle bind to the
    right attendance session (was: armed with today → wrote to a nonexistent session, never banked)."""
    from shared import database as db
    import datetime as _dt
    target = _dt.date(2026, 6, 16)   # a Tuesday
    p = {"id": 7, "canonical_name": "Davy", "call_name": "Davy", "org": "TWB",
         "work_start": "21:00", "work_end": "06:00", "day_off": "Sun"}
    monkeypatch.setattr(ui, "staff_all", lambda *a, **k: [p])

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return []          # no approved al_requests
    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False
    class _Conn:
        def cursor(self): return _CM(_Cur())
    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))
    monkeypatch.setattr(db, "dayoff_override_for", lambda sid, iso: None)
    monkeypatch.setattr(db, "shift_changes_active_map", lambda days: {})

    ev = ui.compute_day_events(target)
    # Tuesday 6am checkout = MONDAY's shift; Tuesday's own T0 at 9pm = Tuesday
    outs = [(m, sd) for m, _n, lbl, _t, sd in ev if lbl.startswith("check-out")]
    assert outs == [(360, "2026-06-15")]
    assert [(m, sd) for m, _n, lbl, _t, sd in ev if lbl.startswith("T0")] == [(1260, "2026-06-16")]
    # the leave-early nudges after the overnight checkout carry yesterday too
    nudges = {sd for _m, _n, lbl, _t, sd in ev if lbl.startswith("leave-early")}
    assert nudges == {"2026-06-15"}

    # an overnight REDEFINE extending Monday's shift to 8am moves the checkout AND keeps Monday's date
    monkeypatch.setattr(db, "shift_changes_active_map",
                        lambda days: {(7, "2026-06-15"): (1260, 1260 + 660)})   # 9pm +11h = 8am
    ev2 = ui.compute_day_events(target)
    outs2 = [(m, sd) for m, _n, lbl, _t, sd in ev2 if lbl.startswith("check-out")]
    assert outs2 == [(480, "2026-06-15")]


_BAKER = {"id": 11, "canonical_name": "Davy", "call_name": "Davy", "org": "TWB",
          "work_start": "21:00", "work_end": "06:00", "day_off": "Sun"}
_DAYREC = {"id": 11, "canonical_name": "Visal", "call_name": "Visal", "org": "TWB",
           "work_start": "08:00", "work_end": "17:00", "day_off": "Sun"}


def _sc_env(monkeypatch, rec, today, redefines=None):
    import datetime as _dt
    from shared import database as db
    monkeypatch.setattr(ui, "staff_all", lambda *a, **k: [rec])
    monkeypatch.setattr(ui, "_today", lambda: _dt.date.fromisoformat(today))
    monkeypatch.setattr(ui, "al_leave_days_set", lambda sid: set())
    monkeypatch.setattr(db, "shift_change_active",
                        lambda sid, iso: (redefines or {}).get(iso))


def test_sc_running_day_shift(monkeypatch):
    _sc_env(monkeypatch, _DAYREC, "2026-06-16")          # Tuesday
    monkeypatch.setattr(ui, "_now_min", lambda: 600)     # 10:00 — mid-shift
    assert ui._sc_running(11) == (0, 480, "2026-06-16")
    monkeypatch.setattr(ui, "_now_min", lambda: 400)     # 6:40 — before
    assert ui._sc_running(11) is None
    monkeypatch.setattr(ui, "_now_min", lambda: 1030)    # 17:10 — after
    assert ui._sc_running(11) is None


def test_sc_running_overnight_yesterday(monkeypatch):
    """A 9pm–6am baker at 2am is running YESTERDAY's shift → tdidx −1 with yesterday's date."""
    _sc_env(monkeypatch, _BAKER, "2026-06-16")
    monkeypatch.setattr(ui, "_now_min", lambda: 120)     # 2am — yesterday's overnight tail
    assert ui._sc_running(11) == (-1, 1260, "2026-06-15")
    monkeypatch.setattr(ui, "_now_min", lambda: 1380)    # 11pm — today's own shift
    assert ui._sc_running(11) == (0, 1260, "2026-06-16")
    monkeypatch.setattr(ui, "_now_min", lambda: 600)     # 10am — between shifts
    assert ui._sc_running(11) is None


def test_sc_running_redefine_aware(monkeypatch):
    """An approved redefine supplies the effective [start,len] — incl. making a day-off day count."""
    _sc_env(monkeypatch, _DAYREC, "2026-06-16",
            redefines={"2026-06-16": {"start_min": 780, "end_min": 1140}})   # 1pm–7pm
    monkeypatch.setattr(ui, "_now_min", lambda: 800)     # 1:20pm — inside the REDEFINED window
    assert ui._sc_running(11) == (0, 780, "2026-06-16")
    monkeypatch.setattr(ui, "_now_min", lambda: 700)     # 11:40am — before redefined start
    assert ui._sc_running(11) is None
    # day-off Tuesday: nothing without a redefine, running WITH one (change-day moved a shift here)
    off = dict(_DAYREC, day_off="Tue")
    _sc_env(monkeypatch, off, "2026-06-16")
    monkeypatch.setattr(ui, "_now_min", lambda: 600)
    assert ui._sc_running(11) is None
    _sc_env(monkeypatch, off, "2026-06-16",
            redefines={"2026-06-16": {"start_min": 480, "end_min": 1020}})
    assert ui._sc_running(11) == (0, 480, "2026-06-16")


def test_sc_day_pick_offers_running_extension(monkeypatch):
    """Mid-shift: the day list grows an 'extend the running shift' button straight to the END ladder
    with the LOCKED start — the only way to reach yesterday's overnight date (tdidx −1)."""
    _sc_env(monkeypatch, _BAKER, "2026-06-16")
    monkeypatch.setattr(ui, "_sc_running", lambda sid: (-1, 1260, "2026-06-15"))
    _, kb = ui.sc_day_pick(_BAKER, 11)
    cds = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "att:scp:st:11:-1:1260" in cds
    monkeypatch.setattr(ui, "_sc_running", lambda sid: None)
    _, kb2 = ui.sc_day_pick(_BAKER, 11)
    assert not any(cd.startswith("att:scp:st:") for cd in
                   (b.callback_data for row in kb2.inline_keyboard for b in row))


def test_sc_mode_midshift_locks_start(monkeypatch):
    """Mid-shift today: 'Change time' is replaced by 'Extend the end' (start LOCKED to the real
    start, straight to the end ladder); 'Change day' stays for future re-planning."""
    _sc_env(monkeypatch, _BAKER, "2026-06-16")
    monkeypatch.setattr(ui, "_sc_running", lambda sid: (0, 1260, "2026-06-16"))
    text, kb = ui.sc_mode(_BAKER, 11, 0)
    cds = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "MID-SHIFT" in text
    assert "att:scp:st:11:0:1260" in cds                      # extend-the-end, locked start
    assert not any(cd.startswith("att:scp:ss:") for cd in cds)  # no start ladder
    assert "att:scp:cd:11:0" in cds                            # Change day kept
    # a future day keeps the normal Change time / Change day pair
    _, kb2 = ui.sc_mode(_BAKER, 11, 2)
    cds2 = [b.callback_data for row in kb2.inline_keyboard for b in row]
    assert "att:scp:ss:11:2" in cds2 and "att:scp:cd:11:2" in cds2


def test_sc_start_bounces_to_locked_mode_when_running(monkeypatch):
    """Any route into today's START ladder while mid-shift (e.g. Back from the end ladder) bounces
    to the locked mode screen — a start that happened can never be re-picked."""
    _sc_env(monkeypatch, _BAKER, "2026-06-16")
    monkeypatch.setattr(ui, "_sc_running", lambda sid: (0, 1260, "2026-06-16"))
    text, _ = ui.sc_start(_BAKER, 11, 0)
    assert "MID-SHIFT" in text


def test_sc_end_back_skips_start_ladder_for_yesterday(monkeypatch):
    """END ladder for yesterday's running overnight (tdidx −1): Back goes to the day list, never to
    a start ladder for a date whose start already happened."""
    from shared import database as db
    _sc_env(monkeypatch, _BAKER, "2026-06-16")
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: None)
    _, kb = ui.sc_end(_BAKER, 11, -1, 1260)
    assert kb.inline_keyboard[0][0].callback_data == "att:scp:d:11"


def test_settle_clamps_to_approved_window(monkeypatch):
    """OT banked at checkout = presence INSIDE the approved [start,end] only. Early arrival /
    lingering past the approved end can't inflate the bank; late arrival still reduces it."""
    import datetime as _dt
    from shared import database as db
    from gm_bot import bot, finance
    sc = {"id": 5, "status": "approved", "normal_len": 540,        # normal 9h
          "start_min": 780, "end_min": 1440}                        # approved 1pm–12am = 11h (+2h OT)
    banked = []
    monkeypatch.setattr(db, "shift_change_active", lambda sid, iso: sc)
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: None)
    monkeypatch.setattr(db, "payback_credit", lambda did, m: None)
    monkeypatch.setattr(db, "ot_bank_balance", lambda sid: 0)
    monkeypatch.setattr(db, "ot_bank_add", lambda sid, m: banked.append(m))
    monkeypatch.setattr(db, "shift_change_set_banked", lambda cid, m: None)
    monkeypatch.setattr(db, "shift_change_claim_settle", lambda cid: True)   # each scenario is its own shift

    def _at(hh, mm, day=15):
        return _dt.datetime(2026, 6, day, hh, mm, tzinfo=finance.PP_TZ)

    staff = {"id": 11}
    sess = {"checked_in_at": _at(13, 0)}
    monkeypatch.setattr(db, "att_get_session", lambda sid, iso: sess)

    # on time, checkout at the approved midnight end → exactly the agreed 2h bank
    bot._settle_redefined_shift(staff, "2026-06-15", _at(0, 0, day=16))
    assert banked == [120]

    # arrived 30 min EARLY + lingered 15 min past the end → still exactly 2h (clamped both sides)
    banked.clear(); sess["checked_in_at"] = _at(12, 30)
    bot._settle_redefined_shift(staff, "2026-06-15", _at(0, 15, day=16))
    assert banked == [120]

    # arrived 2h LATE → worked 9h = normal length → nothing banks
    banked.clear(); sess["checked_in_at"] = _at(15, 0)
    bot._settle_redefined_shift(staff, "2026-06-15", _at(0, 0, day=16))
    assert banked == []


def test_payback_ladder_shielded_by_agreed_ot(monkeypatch):
    """OT_DESIGN §4 shield: an agreed upcoming OT landing before the debt's 14-day deadline pauses
    the ignore-ladder (no warn, no auto-book); without it the ladder runs as before. Stateless —
    re-exposure is just the query no longer matching."""
    import datetime as _dt
    from gm_bot import bot, finance
    from shared import database as db
    today = _dt.datetime.now(finance.PP_TZ).date()
    debt = {"id": 1, "staff_id": 11, "balance": 60,
            "created_date": today - _dt.timedelta(days=6)}        # ≥4 ladder days → autobook stage
    staff = {"id": 11, "canonical_name": "Visal", "call_name": "Visal", "telegram_ids": [555],
             "work_start": "08:00", "work_end": "17:00", "day_off": "Sun"}
    booked, sent, asked = [], [], []
    monkeypatch.setattr(bot, "_att_active", lambda: True)
    monkeypatch.setattr(bot, "payback_all_open", lambda: [debt])
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [staff])
    monkeypatch.setattr(bot, "al_leave_days_set", lambda sid: set())
    monkeypatch.setattr(bot, "payback_book", lambda *a, **k: booked.append(a))

    async def _send(*a, **k):
        sent.append(a)

    monkeypatch.setattr(bot, "_att_send", _send)

    def _shield(sid, t, ddl):
        asked.append((sid, t, ddl))
        return {"id": 9}

    monkeypatch.setattr(db, "ot_shield_until", _shield)
    asyncio.run(bot._payback_ladder_job(_Ctx()))
    assert booked == [] and sent == []                            # shield → ladder fully paused
    assert asked and asked[0][0] == 11
    ddl = _dt.date.fromisoformat(asked[0][2])
    assert ddl == debt["created_date"] + _dt.timedelta(days=14)   # deadline = created + 14

    monkeypatch.setattr(db, "ot_shield_until", lambda sid, t, ddl: None)
    asyncio.run(bot._payback_ladder_job(_Ctx()))
    assert booked and sent                                        # no shield → autobook fires


def test_ot_shield_until_requires_real_ot(monkeypatch):
    """The shield needs the latest redefine to actually CARRY OT — a retime without extension
    (end ≤ start+normal_len) never shields."""
    from shared import database as db
    rows = []

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return rows

    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False

    class _Conn:
        def cursor(self): return _CM(_Cur())

    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))
    # plain retime (9h window, 9h normal) → no shield
    rows = [{"id": 1, "start_min": 780, "end_min": 780 + 540, "normal_len": 540}]
    assert db.ot_shield_until(11, "2026-06-16", "2026-06-30") is None
    # +2h extension → shields
    rows = [{"id": 2, "start_min": 780, "end_min": 780 + 660, "normal_len": 540}]
    assert db.ot_shield_until(11, "2026-06-16", "2026-06-30")["id"] == 2


def test_simcheckout_runs_settle_and_thanks(monkeypatch):
    """/test simulate-checkout: ensures a check-in, checks out at the redefined end, runs the REAL
    settle, reports the banking, and sends the thank-you — all in test, no live mode."""
    from gm_bot import bot
    from shared import database as db
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    persona = {"id": 11, "canonical_name": "Meng", "call_name": "Meng",
               "work_start": "21:00", "work_end": "06:00", "telegram_ids": [555]}
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [persona])
    # approved redefine: 9pm–10am = 13h, normal 9h → +4h OT
    sc = {"id": 9, "status": "approved", "start_min": 1260, "end_min": 1260 + 13 * 60, "normal_len": 540}
    calls = {"checkin": 0, "checkout": 0, "settle": 0}
    monkeypatch.setattr(db, "shift_change_active",
                        lambda sid, iso: sc if iso == _dt_today_iso(bot) else None)
    monkeypatch.setattr(db, "att_check_in", lambda *a, **k: calls.__setitem__("checkin", 1) or True)
    monkeypatch.setattr(db, "att_check_out", lambda *a, **k: calls.__setitem__("checkout", 1))
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: None)
    # settle returns (banked_min, new_bank_balance); +4h banked → triggers the buyback offer
    monkeypatch.setattr(bot, "_settle_redefined_shift",
                        lambda *a, **k: (calls.__setitem__("settle", 1), (240, 240))[1])
    offered = []

    async def _buy(ctx, staff, bank_min, uid, just_added):
        offered.append((bank_min, just_added))

    monkeypatch.setattr(bot, "_offer_buyback", _buy)
    sent = []

    async def _send(ctx, to_uid, role, to_name, text, **k):
        sent.append((role, text))

    monkeypatch.setattr(bot, "_att_send", _send)
    upd = _CbUpdate(bot.config.OWNER_TELEGRAM_ID, "att:cisco:11")
    asyncio.run(bot._ci_simcheckout_callback(upd, _Ctx()))

    assert calls == {"checkin": 1, "checkout": 1, "settle": 1}      # real chain ran
    edited = upd.callback_query.edited[-1]
    assert "OT earned 4h" in edited and "banked 4h OT" in edited     # banking reported
    assert any("nice day" in t for _r, t in sent)                    # thank-you sent to staff
    assert offered == [(240, 240)]                                   # buyback offered for the banked OT


def _dt_today_iso(bot):
    import datetime as _dt
    return _dt.datetime.now(bot.finance.PP_TZ).date().isoformat()


def test_parse_testclock():
    from gm_bot import bot, finance
    import datetime as _dt
    base = _dt.datetime(2026, 6, 11, 14, 30, tzinfo=finance.PP_TZ)
    assert bot._parse_testclock("off", base) == (None, True)
    assert bot._parse_testclock("real", base) == (None, True)
    dt, ok = bot._parse_testclock("+3d", base)
    assert ok and dt == base + _dt.timedelta(days=3)
    dt, ok = bot._parse_testclock("-90m", base)
    assert ok and dt == base - _dt.timedelta(minutes=90)
    dt, ok = bot._parse_testclock("tomorrow 08:00", base)
    assert ok and (dt.date(), dt.hour, dt.minute) == (_dt.date(2026, 6, 12), 8, 0)
    dt, ok = bot._parse_testclock("tomorrow", base)            # default 08:00
    assert ok and (dt.hour, dt.minute) == (8, 0)
    dt, ok = bot._parse_testclock("2026-06-15 06:00", base)
    assert ok and (dt.date(), dt.hour) == (_dt.date(2026, 6, 15), 6)
    assert bot._parse_testclock("garbage", base) == (None, False)


def test_now_pp_only_overrides_in_test_mode(monkeypatch):
    from gm_bot import bot
    frozen = "2026-06-20T06:00:00+07:00"
    monkeypatch.setattr(bot, "gm_get_state", lambda k: frozen if k == "att_test_now" else None)
    # test mode ON → frozen pretend-now is used
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    assert bot._now_pp().date().isoformat() == "2026-06-20"
    assert bot._today_pp().isoformat() == "2026-06-20"
    # test mode OFF → the wall clock, never the override (live staff are never time-warped)
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)
    assert bot._now_pp().date().isoformat() != "2026-06-20"


def test_job_gate_force_run(monkeypatch):
    """A job body is normally skipped when not live/active, but /testrun forces it ON in test mode."""
    from gm_bot import bot
    monkeypatch.setattr(bot, "_attendance_live", lambda: False)
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)        # test mode, NOT live
    # normal: live-only job skipped, test+live job runs (test mode counts as active)
    assert bot._job_gate(live_only=True) is False
    assert bot._job_gate() is True
    # forced (during /testrun): both run, even the live-only ones
    monkeypatch.setattr(bot, "_TEST_FORCE_RUN", True)
    assert bot._job_gate(live_only=True) is True
    # force NEVER applies outside test mode (real staff never force-fired)
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)
    assert bot._job_gate(live_only=True) is False


def test_testrun_fires_job_with_force(monkeypatch):
    """/testrun checkin sets the force flag, awaits the job, and clears the flag afterwards."""
    from gm_bot import bot
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    monkeypatch.setattr(bot, "_tyty_uid", lambda: None)
    seen = {}

    async def _fake_checkin(context):
        seen["forced_during"] = bot._TEST_FORCE_RUN          # flag must be set while it runs

    monkeypatch.setattr(bot, "_checkin_scheduler_job", _fake_checkin)
    upd = _Update(bot.config.OWNER_TELEGRAM_ID, "")
    ctx = _Ctx()
    ctx.args = ["checkin"]
    asyncio.run(bot.cmd_testrun(upd, ctx))
    assert seen.get("forced_during") is True                 # ran with force ON
    assert bot._TEST_FORCE_RUN is False                      # flag cleared after


def test_can_auto_checkout(monkeypatch):
    """Spec §3.7: a live share still in-zone near shift end → silent auto-checkout; a stale share
    (turned off) or an out-of-zone ping (walked off) → False (ask the normal way)."""
    from gm_bot import checkin as ci
    import datetime as _dt
    now = _dt.datetime(2026, 6, 16, 6, 0, tzinfo=_dt.timezone.utc)

    def ping(in_zone, age_min):
        return {"in_zone": in_zone, "ts": now - _dt.timedelta(minutes=age_min)}

    assert ci.can_auto_checkout(ping(True, 2), now) is True       # fresh + in-zone → yes
    assert ci.can_auto_checkout(ping(True, 4), now) is False      # past the 3-min grace → ask
    assert ci.can_auto_checkout(ping(True, 20), now) is False     # share went stale → ask
    assert ci.can_auto_checkout(ping(False, 2), now) is False     # in shop? no — walked off → ask
    assert ci.can_auto_checkout(None, now) is False               # never shared → ask
    assert ci.can_auto_checkout({"in_zone": True, "ts": None}, now) is False


def test_is_share_stop():
    """A stopped live-share = an EDITED update whose live_period is gone. A static pin (new message)
    and an active live update (live_period set) never match."""
    from gm_bot import checkin as ci
    assert ci.is_share_stop(True, None) is True          # edited + no live_period → STOP
    assert ci.is_share_stop(True, 0) is True             # edited + live_period 0 → STOP
    assert ci.is_share_stop(True, 3600) is False         # edited + live → active movement update
    assert ci.is_share_stop(False, None) is False        # new message + no live_period → static pin
    assert ci.is_share_stop(False, 3600) is False        # new message + live → share START


def test_ot_pending_extension_min(monkeypatch):
    """Sum of approved upcoming redefines' OT (end-start beyond normal_len), positive part only."""
    from shared import database as db
    rows = [
        {"start_min": 120, "end_min": 900, "normal_len": 540},   # 13h window, 9h normal → +4h OT
        {"start_min": 540, "end_min": 1080, "normal_len": 540},  # 9h window, 9h normal → 0 OT
    ]

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return rows

    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False

    class _Conn:
        def cursor(self): return _CM(_Cur())

    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))
    assert db.ot_pending_extension_min(11, "2026-06-11") == 240   # 4h + 0


def test_my_schedule_shows_booked_payback(monkeypatch):
    """My Schedule shows '(Xh booked)' next to the debt when an approved upcoming OT will clear it."""
    from gm_bot import attendance_ui as ui
    from shared import database as db
    p = {"id": 11, "canonical_name": "Seth", "call_name": "Seth", "work_start": "21:00",
         "work_end": "06:00", "day_off": "Sun", "al_left": 5, "expertise": ["bakery"]}
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: {"balance": 300})   # 5h debt
    monkeypatch.setattr(db, "ot_bank_balance", lambda sid: 0)
    monkeypatch.setattr(db, "ot_pending_extension_min", lambda sid, iso: 240)    # 4h agreed OT
    monkeypatch.setattr(ui, "att_test_on", lambda: False)

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return []

    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False

    class _Conn:
        def cursor(self): return _CM(_Cur())

    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))
    text, _kb = ui.my_screen(p)
    # Seth's case: 5h debt, 4h agreed OT → all 4h books against the debt, NOTHING upcoming in the bank
    assert "Payback debt: 5h (4h booked" in text
    assert "OT bank: 0h\n" in text and "upcoming" not in text


def _my_screen_env(monkeypatch, debt_min, bank_min, pending_ext):
    """Helper: stub the DB for my_screen with the three numbers that drive the booked/upcoming split."""
    from gm_bot import attendance_ui as ui
    from shared import database as db
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: {"balance": debt_min} if debt_min else None)
    monkeypatch.setattr(db, "ot_bank_balance", lambda sid: bank_min)
    monkeypatch.setattr(db, "ot_pending_extension_min", lambda sid, iso: pending_ext)
    monkeypatch.setattr(ui, "att_test_on", lambda: False)

    class _Cur:
        def execute(self, *a, **k): pass
        def fetchall(self): return []

    class _CM:
        def __init__(self, o): self.o = o
        def __enter__(self): return self.o
        def __exit__(self, *a): return False

    class _Conn:
        def cursor(self): return _CM(_Cur())

    monkeypatch.setattr(db, "_db", lambda: _CM(_Conn()))


def test_my_schedule_booked_vs_upcoming_no_double_count(monkeypatch):
    """The agreed extension is partitioned with NO overlap: min(ext,debt) books against the debt,
    max(0,ext−debt) is upcoming into the bank — and the upcoming part is capped at the 14h bank room."""
    from gm_bot import attendance_ui as ui
    p = {"id": 11, "canonical_name": "X", "call_name": "X", "work_start": "21:00",
         "work_end": "06:00", "day_off": "Sun", "al_left": 5, "expertise": ["bakery"]}

    # ext 6h, debt 2h → 2h books, 4h upcoming (sum = 6h, no double-count)
    _my_screen_env(monkeypatch, debt_min=120, bank_min=0, pending_ext=360)
    t, _ = ui.my_screen(p)
    assert "Payback debt: 2h (2h booked" in t and "OT bank: 0h (4h upcoming" in t

    # no debt, ext 4h → nothing booked, all 4h upcoming
    _my_screen_env(monkeypatch, debt_min=0, bank_min=0, pending_ext=240)
    t, _ = ui.my_screen(p)
    assert "Payback debt: 0h\n" in t and "OT bank: 0h (4h upcoming" in t

    # bank already 13h (60 min room), no debt, ext 4h → upcoming capped at 1h, not 4h
    _my_screen_env(monkeypatch, debt_min=0, bank_min=13 * 60, pending_ext=240)
    t, _ = ui.my_screen(p)
    assert "(1h upcoming" in t and "(4h upcoming" not in t


def test_weekly_brain_block(monkeypatch):
    """The split digest's BRAIN half: exact time-ledger + counts + frequency flags + open-debt list,
    and a reasons block for Opus. Deterministic — no model involved."""
    from gm_bot import bot
    import datetime as _dt
    today = _dt.date(2026, 6, 15)   # a Monday
    facts = {
        "lates": [
            {"staff": "Davy", "date": "2026-06-08", "min": 20, "reason": "moto broke", "informed": False},
            {"staff": "Davy", "date": "2026-06-01", "min": 15, "reason": "traffic", "informed": True},
            {"staff": "Seth", "date": "2026-06-10", "min": 10, "reason": "", "informed": True},
        ],
        "no_shows": [{"staff": "Tra", "date": "2026-06-12"}],
        "als": [{"staff": "Meng", "days": ["2026-06-13"], "reason": "dentist"}],
        "specials": [],
        "open_debts": [{"staff": "Seth", "min": 300}, {"staff": "Davy", "min": 90}],
        "owe_min": 390, "bank_min": 120, "bank_count": 1,
        # Davy: 4 lates with 3 on Monday → same_weekday flag
        "late_dates_by_staff": {"Davy": ["2026-06-01", "2026-06-08", "2026-05-25", "2026-05-18"],
                                "Seth": ["2026-06-10"]},
    }
    # Brain aggregated the model's labels into a per-staff category tally (30d)
    mix = {"Davy": {"transport": 3, "oversleep": 1}}
    owner, summary, reasons, flags = bot._weekly_brain_block(facts, today, mix)
    assert "staff owe 6h 30m (2 debts) · shop owes 2h (1 banks)" in owner   # exact time-ledger
    assert "Late: 3 · No-show: 1 · AL approved: 1 · Special leave: 0" in owner
    assert "Open debts: Seth 5h, Davy 1h 30m" in owner                  # sorted, biggest first
    assert any("Davy" in s and "Monday" in d for s, d in flags)         # Brain frequency flag
    assert "Davy" in owner and "Monday" in owner
    assert "Davy reasons (30d): transport×3, oversleep×1" in owner       # mix shown for the flagged staffer
    # reasons block (for Opus) carries verbatim reasons incl. the AL reason + uninformed tag
    assert "moto broke" in reasons and "uninformed" in reasons and "Meng (AL): dentist" in reasons
    # the figures are NOT repeated in the summary header line (Opus must not recount)
    assert "📊 This week" not in summary


def test_categorize_reasons_shape(monkeypatch):
    """Haiku categorizer: valid labels kept, unknown → 'other', length always matches input,
    no API key → all 'other'. Brain depends on a clean, same-length list."""
    import asyncio as _aio
    from shared import ai_client as ai

    class _Block:
        def __init__(self, t): self.text = t
    class _Resp:
        def __init__(self, t): self.content = [_Block(t)]
    class _Msgs:
        async def create(self, **k): return _Resp('["transport", "weird", "family"]')
    class _Cli:
        messages = _Msgs()

    monkeypatch.setattr(ai.config, "ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(ai, "_get_client", lambda: _Cli())
    out = _aio.run(ai.categorize_reasons(["traffic", "??", "kid sick"]))
    assert out == ["transport", "other", "family"]                      # unknown 'weird' → 'other'
    # length mismatch (model returned fewer) → padded with 'other'
    class _Msgs2:
        async def create(self, **k): return _Resp('["health"]')
    _Cli.messages = _Msgs2()
    out2 = _aio.run(ai.categorize_reasons(["a", "b", "c"]))
    assert out2 == ["health", "other", "other"]
    # no API key → all 'other', never calls the model
    monkeypatch.setattr(ai.config, "ANTHROPIC_API_KEY", "")
    assert _aio.run(ai.categorize_reasons(["x", "y"])) == ["other", "other"]


def test_takeback_windows_are_shift_edges():
    """Take-back of earned OT = rest at the shift's START (come in late) or END (leave early),
    INSIDE the shift — not the before/after-shift windows used for payback."""
    from gm_bot import payback as pb
    wins = pb.takeback_windows(480, 1020, 60)        # shift 8am-5pm, 1h
    assert ("start late", 480, 540) in wins           # rest 8-9am → come in at 9
    assert ("leave early", 960, 1020) in wins         # rest 4-5pm → leave at 4
    # payback (work extra) is the opposite — before/after the shift
    assert ("before", 420, 480) in pb.slot_windows(480, 1020, 60)


def test_strip_khmer_owner_english_only():
    from gm_bot.attendance import strip_khmer
    assert strip_khmer("Hello.\nសួស្តី។") == "Hello."
    assert strip_khmer("What would you like? · តើអ្នកចង់អ្វី?") == "What would you like?"
    assert strip_khmer("OT cancelled.\nOT ត្រូវបានលុបចោល។") == "OT cancelled."
    assert strip_khmer("English only, no khmer") == "English only, no khmer"


def test_back_row_bilingual():
    """The Back button shows Khmer too."""
    row = ui._back_row("att:menu")
    assert "Back" in row[0].text and "ត្រឡប់ក្រោយ" in row[0].text


def test_att_go_confirms_no_reason_flow(monkeypatch):
    """Tap '✅ I confirm' (att:go) fires the real submit_* — no typing 'go'."""
    from gm_bot import bot
    fired = {}

    async def _dispatch(update, context, pend, *, live, reason=None):
        fired.update(pend=pend, live=live, reason=reason)

    monkeypatch.setattr(bot, "_att_dispatch", _dispatch)
    upd = _CbUpdate(bot.config.OWNER_TELEGRAM_ID, "att:go")
    ctx = _Ctx()
    ctx.user_data["att_test_pending"] = {"flow": "sick_me", "persona_id": 11}
    asyncio.run(bot._att_go_callback(upd, ctx))
    assert fired.get("pend", {}).get("flow") == "sick_me"
    assert fired["live"] is False and fired["reason"] == "(confirmed)"
    assert "att_test_pending" not in ctx.user_data   # consumed


def test_dispatch_live_rejects_unknown_uid(monkeypatch):
    from gm_bot import bot
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: None)
    upd = _Update(uid=999999, text="x")
    ctx = _Ctx()
    asyncio.run(bot._att_dispatch(upd, ctx, {"flow": "al", "days": ["2026-06-20"]}, live=True))
    # no persona → silently no-op, nothing sent
    assert upd.message.replies == []


def test_settle_claims_once_no_double_bank(monkeypatch):
    """OT banking is idempotent. The atomic claim lets exactly ONE checkout path bank a redefined
    shift; a second call — the auto-checkout scheduler firing the same minute as a manual checkout,
    or a duplicate Telegram update re-delivered after a crash — banks nothing. No silent double-pay."""
    import gm_bot.bot as bot
    from shared import database as db
    from datetime import date, datetime, timedelta

    sd = "2026-06-15"
    tz = bot.finance.PP_TZ
    base = datetime.combine(date.fromisoformat(sd), datetime.min.time(), tzinfo=tz)
    ci_dt = base + timedelta(minutes=360)      # checked in at the approved start (06:00)
    now_pp = base + timedelta(minutes=900)     # checking out at the approved end (15:00)
    sc = {"id": 7, "status": "approved", "normal_len": 480, "start_min": 360, "end_min": 900}

    calls = {"bank": 0, "credit": 0}
    claimed = {"v": False}

    def _claim(cid):                            # the real atomic compare-and-swap, in memory
        if claimed["v"]:
            return False
        claimed["v"] = True
        return True

    monkeypatch.setattr(db, "shift_change_active", lambda sid, d: dict(sc))
    monkeypatch.setattr(db, "att_get_session", lambda sid, d: {"checked_in_at": ci_dt})
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: None)
    monkeypatch.setattr(db, "ot_bank_balance", lambda sid: 0)
    monkeypatch.setattr(db, "shift_change_claim_settle", _claim)
    monkeypatch.setattr(db, "shift_change_set_banked", lambda cid, m: None)

    def _credit(did, m):
        calls["credit"] += 1
        return {}

    def _bank(sid, m):
        calls["bank"] += 1
        return m

    monkeypatch.setattr(db, "payback_credit", _credit)
    monkeypatch.setattr(db, "ot_bank_add", _bank)

    staff = {"id": 3}
    b1, _ = bot._settle_redefined_shift(staff, sd, now_pp)
    b2, _ = bot._settle_redefined_shift(staff, sd, now_pp)   # re-delivery / concurrent second path
    assert b1 == 60 and b2 == 0          # 540 worked − 480 normal = 60 OT, banked once only
    assert calls["bank"] == 1            # ot_bank_add hit exactly once, never twice


def test_att_send_testkhmer_toggle(monkeypatch):
    """In test mode /testkhmer ON keeps the bilingual body (owner proof-reads the Khmer); OFF (the
    default) strips to English-only. The wall that stopped the owner at test 1.1."""
    import gm_bot.bot as bot

    sent = {}

    class _Bot:
        async def send_message(self, chat_id, text, **k):
            sent["text"] = text
            return None

    ctx = types.SimpleNamespace(bot=_Bot())
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    msg = "Approved.\nបានអនុម័ត។"

    # OFF (default) → English only, Khmer stripped
    monkeypatch.setattr(bot, "gm_get_state", lambda k: "false" if k == "att_test_khmer" else "")
    asyncio.run(bot._att_send(ctx, None, "Staff", "Davy", msg))
    assert "Approved." in sent["text"] and "បាន" not in sent["text"]

    # ON → full bilingual kept
    monkeypatch.setattr(bot, "gm_get_state", lambda k: "true" if k == "att_test_khmer" else "")
    asyncio.run(bot._att_send(ctx, None, "Staff", "Davy", msg))
    assert "បានអនុម័ត។" in sent["text"]


def test_dryrun_checkout_uses_live_constant():
    """Dry-run 1's checkout preview must BE the live _CO_DONE thank-you, not a hardcoded copy that
    drifts when the live wording changes (it had: 'rest well' while live said 'have a nice day')."""
    from gm_bot import attendance_ui as ui
    texts = [t for _, t, _ in ui.build_catalogue(_PERSONA)]
    assert ui._CO_DONE in texts            # the dry-run shows exactly what staff get


def _own_roster():
    import datetime as _dt
    return [
        {"id": 1, "canonical_name": "Chea Chaktopor", "call_name": "Por", "org": "TWB",
         "status": "active", "al_left": 12, "salary_usd": 300, "first_pay_usd": 150,
         "second_pay_usd": 170, "joined_date": None},
        {"id": 2, "canonical_name": "An Davy", "call_name": "Davy", "org": "TWB",
         "status": "active", "al_left": 14, "salary_usd": 250, "first_pay_usd": 120,
         "second_pay_usd": 140, "bonus_usd": 20, "joined_date": _dt.date(2023, 5, 3)},
        {"id": 3, "canonical_name": "Zo NoCall", "call_name": None, "org": "TWB",
         "status": "active", "al_left": 0, "salary_usd": None, "joined_date": None},
        {"id": 4, "canonical_name": "Sok Anan", "call_name": "Anan", "org": "DELIS",
         "status": "active", "al_left": 5, "salary_usd": 100, "first_pay_usd": 50,
         "second_pay_usd": 50, "bonus_usd": 20, "joined_date": None},
        {"id": 5, "canonical_name": "Tyty", "call_name": "Tyty", "org": "TWB",
         "status": "active", "al_left": None, "salary_usd": 1700, "first_pay_usd": 1700,
         "second_pay_usd": 0, "bonus_usd": 0, "joined_date": None},
    ]


def test_staff_btn_label_and_sort():
    """Picker buttons: 'POR — Chea Chaktopor' (CAPSED call name first), alphabetical by call name;
    no call name on record → canonical only."""
    r = _own_roster()
    assert ui.staff_btn_label(r[0]) == "POR — Chea Chaktopor"
    assert ui.staff_btn_label(r[2]) == "Zo NoCall"
    assert [x["id"] for x in ui.staff_sort(r)] == [4, 2, 1, 5, 3]   # Anan < Davy < Por < Tyty < Zo


def test_owner_pbot_partition_and_skip(monkeypatch):
    """PB+OT view mirrors My Schedule's no-double-count: booked=min(ext,debt) beside PB, only the
    leftover is upcoming OT; staff with nothing on the ledger are skipped entirely."""
    import gm_bot.bot as bot
    from shared import database as db
    monkeypatch.setattr(bot, "staff_all", lambda st=None: _own_roster())
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)
    debts = {1: {"balance": 220}}                       # Por owes 3h40
    monkeypatch.setattr(db, "payback_open_debt", lambda sid: debts.get(sid))
    monkeypatch.setattr(db, "ot_bank_balance", lambda sid: 60 if sid == 2 else 0)
    monkeypatch.setattr(db, "ot_pending_extension_min", lambda sid, iso: 120 if sid == 1 else 0)
    t = bot._own_pbot_text("2026-06-11")
    assert "POR — PB 3h 40m (2h booked)" in t            # ext 2h all eaten by the debt
    assert "upcoming" not in t                           # nothing left over → no upcoming OT
    assert "DAVY — OT 1h" in t                           # bank only
    assert "Zo NoCall" not in t                          # both zero → skipped


def test_owner_al_and_salary_views(monkeypatch):
    """AL+Joined shows every staffer (date only when known); the pay lists show payroll staff with
    a total underneath; CAPSED call names throughout."""
    import gm_bot.bot as bot
    monkeypatch.setattr(bot, "staff_all", lambda st=None: _own_roster())
    al = bot._own_al_text()
    assert "• DAVY — 14 AL · 03/05/2023" in al
    assert "• POR — 12 AL" in al
    assert "Zo NoCall — 0 AL" in al                      # everyone shows, even 0 / no date
    assert "ANAN" not in al                              # AL view stays TWB-only
    assert "TYTY" not in al                              # …and keeps excluding Tyty
    s1 = bot._own_sal_text(1)
    assert "• DAVY — $120.00" in s1 and "• POR — $150.00" in s1
    assert "• TYTY — $1700.00" in s1                     # Tyty included in the pay views (owner)
    assert "TWB total: $1970.00" in s1                   # 120+150+1700
    assert "• ANAN — $50.00" in s1                       # Delis gets its own section
    assert "Delis total: $50.00" in s1
    assert "Total: $2020.00" in s1                       # grand total of both orgs
    assert "Zo" not in s1                                # nothing on record → not listed
    s2 = bot._own_sal_text(2)
    assert "• DAVY — $120.00 +$20.00" in s2              # base = pay2 − bonus, + the earnable bonus
    assert "• POR — $170.00\n" in s2 or "• POR — $170.00" in s2   # no bonus → no '+'
    assert "• ANAN — $30.00 +$20.00" in s2               # the owner's exact example shape
    assert "TYTY" not in s2                              # 1st-pay-only → never clutters the 2nd list
    assert "TWB total: $310.00" in s2
    assert "Total: $360.00" in s2


def test_shift_changes_active_map_real_sql_types():
    """REGRESSION (the dry-run-1 crash): the batch redefine lookup passes ISO strings into a
    DATE = ANY(...) — Postgres needs the ::date[] cast or every caller (dry-run 1's schedule
    summary, the check-in scheduler) dies with 'operator does not exist: date = text'. Mocked
    tests can't catch SQL typing, so this one touches the real DB (read-only; skips without one)."""
    import pytest
    from shared import database as db
    try:
        out = db.shift_changes_active_map(["2026-01-01", "2026-01-02"])
    except Exception as e:
        if "operator does not exist" in str(e):
            raise                                  # the regression itself — never skip THAT
        pytest.skip("no database available: %s" % e)
    assert isinstance(out, dict)


def test_prorate_join_month_owner_rule():
    """30-day basis always; missed = join_day−1; 1st = 80% of prorated rounded UP to next 5/0
    (never above prorated); 2nd base = remainder. Kimying (owner-worked example) is the anchor."""
    from gm_bot.payroll import prorate_join_month
    p = prorate_join_month(160, 4)                       # Kimying: Jun 4 → 27/30
    assert p == {"prorated": 144.0, "first": 120.0, "second_base": 24.0}
    p1 = prorate_join_month(160, 1)                      # joined the 1st → full month
    assert p1["prorated"] == 160.0 and p1["first"] == 130.0   # 128 → up to 130
    pr5 = prorate_join_month(100, 16)                    # 50 → 80% = 40, already a 5/0 → stays
    assert pr5 == {"prorated": 50.0, "first": 40.0, "second_base": 10.0}
    tiny = prorate_join_month(10, 28)                    # 1.0 → 80% = .8 → ceil to 5 BUT capped
    assert tiny["first"] == tiny["prorated"] == 1.0 and tiny["second_base"] == 0


def test_pay_restore_job_due_and_not_due(monkeypatch):
    """The daily job restores the FULL split only once the join month has PASSED; current-month
    records wait; the record is cleared after restoring (never restores twice)."""
    import gm_bot.bot as bot
    from shared import database as db

    restored, cleared, dms = [], [], []
    monkeypatch.setattr(db, "gm_state_prefix", lambda p: [
        ("pay_restore:42", '{"first": 145.0, "second": 30.0, "after": "2026-05"}'),   # passed → due
        ("pay_restore:7",  '{"first": 100.0, "second": 20.0, "after": "2099-12"}'),   # future → wait
    ])
    monkeypatch.setattr(db, "staff_set_pay_split", lambda sid, f, s: restored.append((sid, f, s)))
    monkeypatch.setattr(db, "gm_set_state", lambda k, v: cleared.append(k))
    monkeypatch.setattr(bot, "staff_all", lambda st=None: [
        {"id": 42, "canonical_name": "Sun Kimying", "call_name": "Kimying"}])

    class _Bot:
        async def send_message(self, chat_id, text, **k):
            dms.append(text)

    ctx = types.SimpleNamespace(bot=_Bot())
    asyncio.run(bot._pay_restore_job(ctx))
    assert restored == [(42, 145.0, 30.0)]               # only the passed month restored
    assert cleared == ["pay_restore:42"]                 # record cleared → can't restore twice
    assert any("KIMYING" in d and "$145" in d for d in dms)   # owner told


def test_parse_joined_full_and_month_only():
    """/joined accepts full dates AND month/year when the day is unknown — stored as the 1st but
    flagged month_only so the views show mm/yyyy, never a fake '01/'."""
    import gm_bot.bot as bot
    assert bot._parse_joined("03/05/2023") == ("2023-05-03", False)
    assert bot._parse_joined("2023-05-03") == ("2023-05-03", False)
    assert bot._parse_joined("05/2023") == ("2023-05-01", True)     # month only
    assert bot._parse_joined("2023-05") == ("2023-05-01", True)
    assert bot._parse_joined("31/02/2023") is None                  # impossible date rejected
    assert bot._parse_joined("nonsense") is None


def test_msg_time_pp_judges_by_telegram_stamp(monkeypatch):
    """Queued updates are judged by the staffer's send time (Telegram stamp), never by when a
    recovering bot processed them — a punctual check-in must not turn late because WE were down.
    Edits prefer edit_date; test mode keeps the test clock; no stamp → fallback."""
    import datetime as _dt
    import gm_bot.bot as bot

    pp = bot.finance.PP_TZ
    sent_utc = _dt.datetime(2026, 6, 11, 14, 0, tzinfo=_dt.timezone.utc)      # 9pm PP
    processed = _dt.datetime(2026, 6, 11, 21, 12, tzinfo=pp)                  # bot back 12 min later
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)

    upd = types.SimpleNamespace(edited_message=None,
                                message=types.SimpleNamespace(date=sent_utc, edit_date=None))
    out = bot._msg_time_pp(upd, processed)
    assert (out.hour, out.minute) == (21, 0)             # the SEND time in PP, not 21:12

    # an edited live-share carries edit_date — that wins over the original send date
    edit_utc = _dt.datetime(2026, 6, 11, 14, 5, tzinfo=_dt.timezone.utc)
    upd2 = types.SimpleNamespace(message=None,
                                 edited_message=types.SimpleNamespace(date=sent_utc, edit_date=edit_utc))
    assert bot._msg_time_pp(upd2, processed).minute == 5

    # test mode → the test clock (fallback) wins so /testclock rehearsals still work
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    assert bot._msg_time_pp(upd, processed) == processed

    # no Telegram stamp at all → fallback
    monkeypatch.setattr(bot, "_att_test_mode", lambda: False)
    upd3 = types.SimpleNamespace(edited_message=None,
                                 message=types.SimpleNamespace(date=None, edit_date=None))
    assert bot._msg_time_pp(upd3, processed) == processed


def test_owner_al_month_only_display(monkeypatch):
    """A month-only hire date displays as mm/yyyy in AL+Joined (no invented day)."""
    import datetime as _dt
    import gm_bot.bot as bot
    roster = _own_roster()
    roster[0]["joined_date"] = _dt.date(2022, 11, 1)
    roster[0]["joined_month_only"] = True
    monkeypatch.setattr(bot, "staff_all", lambda st=None: roster)
    al = bot._own_al_text()
    assert "• POR — 12 AL · 11/2022" in al               # month/year only
    assert "01/11/2022" not in al                        # the stored day-1 never shows
    assert "• DAVY — 14 AL · 03/05/2023" in al           # full dates unchanged
