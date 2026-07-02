"""F1 Thyda-spec gaps (2026-07-02) — the two pieces beyond the already-live F1 gates:

 3a  swap_approver_id — a day-off-swap override routes the card to ONLY that approver, lets THEM decide
     (even if not a senior), and ONE approval finalises; no override = the normal senior ladder + quorum.
 3b  escalate_to_id — a Supervisors-group attendance post ABOUT a staffer is REROUTED to that person's
     private DM instead of the group. Reroute WINS over no_supervisor_posts suppress; Management posts are
     untouched (supervisor-only); a normal staffer / no exception posts exactly as today.

Pure authz (_swap_authz) + routing (_approvers_for, kind='swap') + the _att_send reroute (FakeBot).
Safe-by-construction: with no exception set, every path is byte-identical to today."""
import asyncio
import types

from core.db import init_core_db, ensure_org
from core.onboarding_flow import add_staff_manual
from core import exceptions as ex
from gm_bot import bot, al as alm, exceptions_live


# ---- 3a: pure authorization + quorum (_swap_authz) ---------------------------------------------

def test_swap_no_override_uses_senior_ladder_and_quorum():
    assert bot._swap_authz(5, True, False, None) == (True, alm.approvals_needed(False))    # a senior decides
    assert bot._swap_authz(5, False, False, None) == (False, alm.approvals_needed(False))  # a non-senior can't
    assert bot._swap_authz(5, True, True, None) == (True, alm.approvals_needed(True))       # a party is senior → fewer


def test_swap_override_locks_to_that_approver_quorum_one():
    OV = 28
    assert bot._swap_authz(OV, False, False, OV) == (True, 1)   # Tyty (non-senior) decides; ONE approval
    assert bot._swap_authz(99, True, False, OV) == (False, 1)   # any OTHER senior is locked out by the override


# ---- 3a: routing (_approvers_for with kind='swap') --------------------------------------------

_ROSTER = [
    {"id": 1, "is_senior": True, "org": "TWB", "telegram_ids": [11], "canonical_name": "Sen1"},
    {"id": 2, "is_senior": True, "org": "TWB", "telegram_ids": [22], "canonical_name": "Sen2"},
    {"id": 28, "is_senior": False, "org": "TWB", "telegram_ids": [288], "canonical_name": "Tyty"},
    {"id": 34, "is_senior": False, "org": "TWB", "telegram_ids": [344], "canonical_name": "Thyda"},
]


def _patch_roster(monkeypatch, overrides):
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: _ROSTER)
    monkeypatch.setattr(exceptions_live, "approver", lambda staff_id, kind="al": overrides.get((staff_id, kind)))


def test_swap_routes_to_override_only(monkeypatch):
    _patch_roster(monkeypatch, {(34, "swap"): 28})            # Thyda's swaps → only Tyty
    assert [s["id"] for s in bot._approvers_for(34, "swap")] == [28]


def test_swap_without_override_uses_ladder(monkeypatch):
    _patch_roster(monkeypatch, {})                            # no override → the senior ladder
    assert sorted(s["id"] for s in bot._approvers_for(34, "swap")) == [1, 2]


def test_swap_self_override_falls_back_to_ladder(monkeypatch):
    _patch_roster(monkeypatch, {(34, "swap"): 34})            # foot-gun → never self-approve → ladder
    assert sorted(s["id"] for s in bot._approvers_for(34, "swap")) == [1, 2]


# ---- 3b: escalate reroute inside _att_send ----------------------------------------------------

class _FakeBot:
    async def send_message(self, *a, **k):
        return types.SimpleNamespace(message_id=1)


def _ctx():
    return types.SimpleNamespace(bot=_FakeBot())


def _setup(monkeypatch):
    init_core_db()
    org = "thydagap"
    ensure_org(org, "ThydaGapTest", "Asia/Phnom_Penh")
    monkeypatch.setattr(exceptions_live, "ORG", org)
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: _ROSTER)   # reroute resolves the target here
    return org


def _capture_send(monkeypatch):
    sent = []

    async def fake(context, target, body, kb=None, parse_mode=None, **k):
        sent.append((target, body))
        return types.SimpleNamespace(message_id=1), False

    monkeypatch.setattr(bot, "_send_once_retrying", fake)
    return sent


def test_escalate_reroutes_supervisor_post_to_dm(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Thyda")
    ex.set_exceptions(org, sid, {"escalate_to_id": 28})
    sent = _capture_send(monkeypatch)
    msg = asyncio.run(bot._att_send(_ctx(), None, "Supervisors group", "", "FYI: Thyda late",
                                    group=True, subject_staff_id=sid))
    assert msg is not None
    assert len(sent) == 1 and sent[0][0] == 288          # delivered to Tyty's DM (uid 288), not the group
    assert "Escalated to you" in sent[0][1]


def test_escalate_wins_over_suppress(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Thyda")
    ex.set_exceptions(org, sid, {"no_supervisor_posts": True, "escalate_to_id": 28})
    sent = _capture_send(monkeypatch)
    msg = asyncio.run(bot._att_send(_ctx(), None, "Supervisors group", "", "x",
                                    group=True, subject_staff_id=sid))
    assert msg is not None and len(sent) == 1 and sent[0][0] == 288   # rerouted, NOT suppressed


def test_escalate_does_not_touch_management_posts(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Thyda")
    ex.set_exceptions(org, sid, {"escalate_to_id": 28})
    sent = _capture_send(monkeypatch)
    asyncio.run(bot._att_send(_ctx(), None, "Management group", "", "x",
                              group=True, subject_staff_id=sid))
    # escalate is supervisor-only → a Management post is NOT rerouted to Tyty's DM
    assert len(sent) == 1 and sent[0][0] != 288


def test_no_escalate_posts_as_today(monkeypatch):
    org = _setup(monkeypatch)
    sid = add_staff_manual(org, name="Normal")           # default {} → unchanged
    sent = _capture_send(monkeypatch)
    asyncio.run(bot._att_send(_ctx(), None, "Supervisors group", "", "x",
                              group=True, subject_staff_id=sid))
    assert len(sent) == 1 and sent[0][0] != 288          # normal group post, no reroute
