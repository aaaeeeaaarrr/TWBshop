"""F1: the no_supervisor_posts / no_management_posts gate inside _att_send. A GROUP post ABOUT an exempt
staffer (subject_staff_id passed) is suppressed before any send; subject_staff_id=None (every un-converted
call site) or a normal staffer posts exactly as today. Uses the FakeBot pattern from test_send_resilience."""
import asyncio
import types

from core.db import init_core_db, ensure_org
from core.onboarding_flow import add_staff_manual
from core import exceptions as ex
from gm_bot import bot, exceptions_live


class _FakeBot:
    def __init__(self):
        self.calls = 0

    async def send_message(self, *a, **k):
        self.calls += 1
        return types.SimpleNamespace(message_id=1)


def _ctx(fb):
    return types.SimpleNamespace(bot=fb)


def _setup(monkeypatch):
    init_core_db()
    org = "supost58"
    ensure_org(org, "SupPostTest", "Asia/Phnom_Penh")
    monkeypatch.setattr(exceptions_live, "ORG", org)
    return org


def test_supervisor_post_suppressed_for_exempt_subject(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Thyda")
    ex.set_exceptions(org, sid, {"no_supervisor_posts": True})
    fb = _FakeBot()
    msg = asyncio.run(bot._att_send(_ctx(fb), None, "Supervisors group", "", "FYI: out sick",
                                    group=True, subject_staff_id=sid))
    assert msg is None and fb.calls == 0          # suppressed before any send


def test_supervisor_post_sent_for_normal_subject(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Normal")
    fb = _FakeBot()
    asyncio.run(bot._att_send(_ctx(fb), None, "Supervisors group", "", "FYI", group=True, subject_staff_id=sid))
    assert fb.calls == 1                            # default {} → posts as today


def test_no_subject_posts_as_today(monkeypatch):
    _setup(monkeypatch)
    fb = _FakeBot()
    asyncio.run(bot._att_send(_ctx(fb), None, "Supervisors group", "", "FYI", group=True))
    assert fb.calls == 1                            # subject_staff_id=None → unchanged behaviour


def test_management_key_is_separate_from_supervisor(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Mgr")
    ex.set_exceptions(org, sid, {"no_management_posts": True})   # off Management only, NOT Supervisors
    fb = _FakeBot()
    m1 = asyncio.run(bot._att_send(_ctx(fb), None, "Management group", "", "x", group=True, subject_staff_id=sid))
    assert m1 is None and fb.calls == 0            # Management post suppressed
    asyncio.run(bot._att_send(_ctx(fb), None, "Supervisors group", "", "x", group=True, subject_staff_id=sid))
    assert fb.calls == 1                            # Supervisors post still goes (only off Management)
