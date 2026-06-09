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
    ui._arm_pending(ctx, 777, {"flow": "al", "days": ["2026-06-20"]})
    assert saved["uid"] == 777 and saved["flow"] == "att_pending"
    assert saved["data"]["flow"] == "al"
    assert "att_test_pending" not in ctx.user_data     # live does NOT use user_data


def test_arm_pending_uses_user_data_in_test(monkeypatch):
    monkeypatch.setattr(ui, "att_test_on", lambda: True)
    ctx = _Ctx()
    ui._arm_pending(ctx, 777, {"flow": "al"})
    assert ctx.user_data["att_test_pending"]["flow"] == "al"


# ---- dispatcher: LIVE late = declare-only (no payback at declare) ------------

def test_dispatch_late_live_declares_only(monkeypatch):
    from gm_bot import bot
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


def test_dispatch_late_test_collapses_payback(monkeypatch):
    from gm_bot import bot
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
    monkeypatch.setattr(bot, "payback_open_debt", lambda *a, **k: {"balance": 30})
    monkeypatch.setattr(bot, "_offer_payback", _offer)

    upd = _Update(uid=bot.config.OWNER_TELEGRAM_ID, text="traffic")
    ctx = _Ctx()
    asyncio.run(bot._att_dispatch(upd, ctx,
                {"flow": "late", "persona_id": 11, "mins": 30}, live=False))

    assert calls["payback"] == 1       # test collapses declare+arrival so the owner can book
    assert calls["offer"] == 1


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
    ValueError (the runtime risk from Khmer with embedded numbers). Owner shell = English-only, so
    we assert the English survives (the Khmer is correctly stripped for the owner)."""
    import config
    monkeypatch.setattr(ui, "staff_all", lambda *a, **k: [dict(_PERSONA)])
    monkeypatch.setattr(ui, "att_test_on", lambda: True)         # armed (owner test mode)
    monkeypatch.setattr(ui, "flow_save", lambda *a, **k: None)
    cases = [
        ("att:ot:en:now:11:0:480:540", "60 min"),         # OT 60 min (2× %d)
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


def test_al_summary_bold_spaced_english():
    """AL request line: English only, BOLD dates, spaced."""
    from gm_bot import bot
    s = bot._al_summary("Pisey", ["2026-06-21", "2026-06-22"], "country side")
    assert "<b>Sun 21/06</b>" in s and "<b>Mon 22/06</b>" in s   # bold dates
    assert "<b>Sun 21/06</b>   <b>Mon 22/06</b>" in s            # spaced
    assert "requests AL" in s and "country side" in s
    assert "ស" not in s                                          # no Khmer


def test_al_finalize_edits_cards_in_place(monkeypatch):
    """On decision the senior cards are EDITED in place (request intact + verdict); no new
    per-senior messages; requester + Supervisors notices still sent."""
    from gm_bot import bot
    edits, roles = [], []
    g = {"id": 50, "staff_id": 2, "days": ["2026-06-21"], "reason": "r", "kind": "days",
         "status": "pending", "hours_start": None, "hours_end": None}
    monkeypatch.setattr(bot, "al_get_request", lambda i: g)
    monkeypatch.setattr(bot, "al_set_status", lambda *a, **k: None)
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
        async def edit_message_text(self, text, chat_id=None, message_id=None, parse_mode=None):
            edits.append((chat_id, message_id, text))

    ctx = _Ctx()
    ctx.bot = _Bot()
    ctx.bot_data = {"al_cards": {50: [(111, 7), (111, 8)]}}
    asyncio.run(bot._al_finalize(ctx, g, approved=True))
    assert len(edits) == 2                                   # both cards edited in place
    assert "Approved by A and B" in edits[0][2]
    assert "Senior" not in roles                             # NO new per-senior message
    assert "Requester" in roles and "Supervisors group" in roles


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
    monkeypatch.setattr(bot, "swap_set_status", lambda *a, **k: None)
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [
        {"id": 1, "canonical_name": "Req", "call_name": "Req", "telegram_ids": [11]},
        {"id": 2, "canonical_name": "Par", "call_name": "Par", "telegram_ids": [22]}])
    monkeypatch.setattr(bot, "dayoff_set_override", lambda *a, **k: None)

    async def _send(ctx, to_uid, role, to_name, text, kb=None, group=False, parse_mode=None):
        roles.append(role)

    monkeypatch.setattr(bot, "_att_send", _send)

    class _Bot:
        async def edit_message_text(self, text, chat_id=None, message_id=None, parse_mode=None):
            edits.append((chat_id, message_id, text))

    ctx = _Ctx()
    ctx.bot = _Bot()
    ctx.bot_data = {"swap_cards": {9: [(111, 5), (111, 6)]}}
    asyncio.run(bot._swap_apply(ctx, sw, approved=True))
    assert len(edits) == 2
    assert "✅ Approved" in edits[0][2] and "Day-off swap" in edits[0][2]
    assert "Requester" in roles and "Partner" in roles and "Supervisors group" in roles


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


def test_ot_window_shows_time_not_now():
    """OT confirmations show the real time window (e.g. 4pm-5pm), never just 'now'."""
    from gm_bot import bot
    assert bot._ot_window("now", None, 960, 60) == "4pm-5pm"
    assert bot._ot_window("later", "2026-06-20", 540, 120) == "2026-06-20 9am-11am"
    assert bot._ot_window("now", None, None, 60) == "now"   # fallback if no start recorded


def test_ot_started_veto_window():
    """Owner veto window: open until OT start. Yesterday's OT started; tomorrow's hasn't."""
    from gm_bot import bot, finance
    import datetime as _dt
    today = _dt.datetime.now(finance.PP_TZ).date()
    past = (today - _dt.timedelta(days=1)).isoformat()
    future = (today + _dt.timedelta(days=1)).isoformat()
    assert bot._ot_started({"when_date": past, "start_min": 600}) is True
    assert bot._ot_started({"when_date": future, "start_min": 600}) is False
    assert bot._ot_started({"when_date": future, "start_min": None}) is False


def test_submit_ot_later_asks_staff_without_owner_approval(monkeypatch):
    """LATER OT: staff is asked immediately + owner gets a reject-only notice — NO owner gate."""
    from gm_bot import bot
    sent, sets = [], []

    async def _send(ctx, to_uid, role, to_name, text, kb=None, group=False):
        sent.append((role, kb is not None))

    monkeypatch.setattr(bot, "_att_send", _send)
    monkeypatch.setattr(bot, "ot_grant_create", lambda *a, **k: 99)
    monkeypatch.setattr(bot, "ot_grant_set", lambda gid, **k: sets.append(k.get("status")))
    monkeypatch.setattr(bot, "ot_bank_balance", lambda sid: 0)
    senior = {"id": 1, "canonical_name": "Samphass", "call_name": "Samphass"}
    staff = {"id": 2, "canonical_name": "Tra", "call_name": "Tra", "telegram_ids": [222]}
    asyncio.run(bot.submit_ot_grant(_Ctx(), senior, staff, "later", 120, "2026-06-20", 540, "busy"))
    roles = [r for r, _kb in sent]
    assert "Owner" in roles and "Staff" in roles      # both engaged, in parallel
    assert "staff_asked" in sets                        # staff consent pending, no owner approval gate


def test_submit_ot_now_asks_staff_first(monkeypatch):
    """NOW OT: the staff is ASKED first (no auto-bank); owner gets a reject notice. Nothing banks
    until the staff accepts."""
    from gm_bot import bot
    seen, sets, banked = [], [], []

    async def _send(ctx, to_uid, role, to_name, text, kb=None, group=False):
        seen.append(role)

    async def _buy(*a, **k):
        banked.append("buyback")

    monkeypatch.setattr(bot, "_att_send", _send)
    monkeypatch.setattr(bot, "_offer_buyback", _buy)
    monkeypatch.setattr(bot, "ot_grant_create", lambda *a, **k: 5)
    monkeypatch.setattr(bot, "ot_grant_set", lambda gid, **k: sets.append(k.get("status")))
    monkeypatch.setattr(bot, "ot_bank_balance", lambda sid: 0)
    monkeypatch.setattr(bot, "ot_bank_add", lambda sid, m: banked.append(m) or 120)
    senior = {"id": 1, "canonical_name": "S", "call_name": "S"}
    staff = {"id": 2, "canonical_name": "Tra", "call_name": "Tra", "telegram_ids": [222]}
    asyncio.run(bot.submit_ot_grant(_Ctx(), senior, staff, "now", 120, None, 540, "x"))
    assert "Owner" in seen and "Staff" in seen          # both engaged; staff ASKED
    assert "staff_asked" in sets
    assert banked == []                                  # NOTHING banked/offered until consent


def test_ot_future_now_accept_banks(monkeypatch):
    """NOW OT consent: when the staff taps Yes, THEN it banks + offers buyback (status=banked)."""
    from gm_bot import bot
    seen = {"bank": 0, "buyback": 0, "status": None}
    g = {"id": 7, "staff_id": 2, "senior_id": 1, "kind": "now", "minutes": 60,
         "status": "staff_asked", "when_date": None, "start_min": 960}
    monkeypatch.setattr(bot, "ot_grant_get", lambda i: g)
    monkeypatch.setattr(bot, "_att_test_mode", lambda: True)
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: [
        {"id": 2, "canonical_name": "Tra", "call_name": "Tra", "telegram_ids": [222]}])

    def _bank(sid, m):
        seen["bank"] += 1
        return 60

    monkeypatch.setattr(bot, "ot_bank_add", _bank)
    monkeypatch.setattr(bot, "ot_grant_set",
                        lambda i, **k: seen.__setitem__("status", k.get("status") or seen["status"]))

    async def _buy(*a, **k):
        seen["buyback"] += 1

    monkeypatch.setattr(bot, "_offer_buyback", _buy)
    asyncio.run(bot._ot_future_callback(_CbUpdate(222, "att:otf:yes:7"), _Ctx()))
    assert seen["bank"] == 1 and seen["buyback"] == 1 and seen["status"] == "banked"


def test_dispatch_live_rejects_unknown_uid(monkeypatch):
    from gm_bot import bot
    monkeypatch.setattr(bot, "staff_get_by_uid", lambda uid: None)
    upd = _Update(uid=999999, text="x")
    ctx = _Ctx()
    asyncio.run(bot._att_dispatch(upd, ctx, {"flow": "al", "days": ["2026-06-20"]}, live=True))
    # no persona → silently no-op, nothing sent
    assert upd.message.replies == []
