"""Mandatory typed sick reason (owner Jun 21) — never a blank FYI again (Long's bug)."""
import gm_bot.bot as bot


def test_sick_flows_require_a_typed_reason():
    # a bare tap-confirm or blank must NOT file a sick case
    for blank in ("", "   ", "(no reason)", "(confirmed)", None):
        assert bot._reason_gate_blank("sick_me", blank) is True
        assert bot._reason_gate_blank("sick_fam", blank) is True


def test_real_reason_passes():
    assert bot._reason_gate_blank("sick_me", "fever and headache") is False
    assert bot._reason_gate_blank("sick_fam", "son has a fever") is False


def test_shift_keeps_old_behavior():
    # 'shift' still accepts a tap-confirm ('(confirmed)') — only blank is rejected (unchanged)
    assert bot._reason_gate_blank("shift", "(confirmed)") is False
    assert bot._reason_gate_blank("shift", "") is True


def test_non_reason_flows_unaffected():
    assert bot._reason_gate_blank("al", "") is False
    assert bot._reason_gate_blank(None, "") is False


def test_reason_prompt_is_relationship_aware():
    assert "What's wrong?" in bot._sick_reason_prompt(None)
    assert "What's wrong?" in bot._sick_reason_prompt("me")
    assert "your child" in bot._sick_reason_prompt("child")
    assert "your husband/wife" in bot._sick_reason_prompt("spouse")
    assert "your parent" in bot._sick_reason_prompt("parent")
