"""F1 al_approver_id: an AL approver OVERRIDE routes the card to ONLY that person, lets THEM decide (even
if they're not a senior), and ONE approval finalises; with no override it's the normal senior ladder +
quorum. Pure authz (_al_authz) + routing (_approvers_for, monkeypatched roster) — no live AL flow needed."""
from gm_bot import bot
from gm_bot import al as alm
from gm_bot import exceptions_live as el


# ---- pure authorization + quorum (_al_authz) ---------------------------------------------------

def test_no_override_uses_the_senior_ladder_and_normal_quorum():
    assert bot._al_authz(5, True, False, None) == (True, alm.approvals_needed(False))    # senior decides regular's AL
    assert bot._al_authz(5, False, False, None) == (False, alm.approvals_needed(False))  # a non-senior can't
    assert bot._al_authz(5, True, True, None) == (True, alm.approvals_needed(True))      # senior's own AL → fewer


def test_override_locks_to_that_approver_with_quorum_one():
    OV = 28
    assert bot._al_authz(OV, False, False, OV) == (True, 1)   # the override approver decides; ONE approval
    assert bot._al_authz(99, True, False, OV) == (False, 1)   # any OTHER senior is locked out by the override


# ---- routing (_approvers_for) ------------------------------------------------------------------

def _patch(monkeypatch, roster, overrides):
    monkeypatch.setattr(bot, "staff_all", lambda *a, **k: roster)
    monkeypatch.setattr(el, "approver", lambda staff_id, kind="al": overrides.get(staff_id))


_ROSTER = [
    {"id": 1, "is_senior": True, "org": "TWB", "telegram_ids": [11], "canonical_name": "Sen1"},
    {"id": 2, "is_senior": True, "org": "TWB", "telegram_ids": [22], "canonical_name": "Sen2"},
    {"id": 28, "is_senior": False, "org": "TWB", "telegram_ids": [288], "canonical_name": "Tyty"},
    {"id": 34, "is_senior": False, "org": "TWB", "telegram_ids": [344], "canonical_name": "Thyda"},
]


def test_routes_to_the_override_only(monkeypatch):
    _patch(monkeypatch, _ROSTER, {34: 28})            # Thyda's AL → only Tyty
    assert [s["id"] for s in bot._approvers_for(34, "al")] == [28]


def test_falls_back_to_ladder_without_override(monkeypatch):
    _patch(monkeypatch, _ROSTER, {})                  # no override
    assert sorted(s["id"] for s in bot._approvers_for(34, "al")) == [1, 2]   # the senior ladder


def test_self_override_falls_back_to_ladder(monkeypatch):
    _patch(monkeypatch, _ROSTER, {34: 34})            # foot-gun: override points at self
    assert sorted(s["id"] for s in bot._approvers_for(34, "al")) == [1, 2]   # never self-approve → ladder


def test_unreachable_override_falls_back_to_ladder(monkeypatch):
    _patch(monkeypatch, _ROSTER, {34: 999})           # override points at a non-existent staffer
    assert sorted(s["id"] for s in bot._approvers_for(34, "al")) == [1, 2]
