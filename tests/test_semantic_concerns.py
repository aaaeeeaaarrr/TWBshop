"""Tests for gm_bot/analyzer.py semantic concern detection.

No API and no DB: the AI detector is injected as a fake. Covers the free pre-gate,
meaning-based accept/reject, rules suppression, the error->keyword fallback, and the
concern-dict shape.
"""
import asyncio

import config
from gm_bot import analyzer


def _run(coro):
    return asyncio.run(coro)


def _msg(text, mid=1, chat_id=None, sender="Dara"):
    return {
        "id": str(mid),
        "chat_id": chat_id if chat_id is not None else config.STOCK_CHECKS_CHAT_ID,
        "text": text,
        "sender_name": sender,
    }


def _fake(result):
    """Return an async detector that always yields `result`, ignoring input."""
    async def detect(text):
        return dict(result)
    return detect


def _by_text(mapping, default=None):
    """Async detector that returns a result keyed by the message text."""
    default = default or {"is_concern": False, "concern_type": None}
    async def detect(text):
        return dict(mapping.get(text, default))
    return detect


# ── Pre-gate ────────────────────────────────────────────────────────────────

def test_worth_checking_skips_trivial():
    assert not analyzer._worth_checking("")
    assert not analyzer._worth_checking("   ")
    assert not analyzer._worth_checking("ok")
    assert not analyzer._worth_checking("👍")
    assert not analyzer._worth_checking("12 30 600")      # numbers only
    assert not analyzer._worth_checking("done")            # one word


def test_worth_checking_accepts_real_messages():
    assert analyzer._worth_checking("the tray slipped and 6 cakes fell")
    assert analyzer._worth_checking("no waste today")
    assert analyzer._worth_checking("we are almost out of butter")


def test_gate_blocks_ai_call_for_trivial():
    # A trivial message must never reach the detector.
    calls = []

    async def detect(text):
        calls.append(text)
        return {"is_concern": True, "concern_type": "mistake", "severity": "info"}

    concerns = _run(analyzer._semantic_text_concerns([_msg("ok")], [], detector=detect))
    assert concerns == []
    assert calls == []


# ── Meaning-based accept / reject ─────────────────────────────────────────────

def test_zero_keyword_mistake_is_caught():
    detector = _fake({"is_concern": True, "concern_type": "mistake",
                      "severity": "warning", "summary": "tray dropped"})
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("the tray slipped and six cakes fell on the floor")], [], detector=detector))
    assert len(concerns) == 1
    assert concerns[0]["concern_type"] == "mistake"
    assert concerns[0]["severity"] == "warning"


def test_negation_is_rejected():
    # "no waste today" — AI says not a concern, so nothing is flagged.
    detector = _fake({"is_concern": False, "concern_type": None})
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("no waste today, nothing got thrown away")], [], detector=detector))
    assert concerns == []


def test_unknown_concern_type_dropped():
    detector = _fake({"is_concern": True, "concern_type": "philosophy", "severity": "info"})
    concerns = _run(analyzer._semantic_text_concerns([_msg("a real message here")], [], detector=detector))
    assert concerns == []


def test_waste_low_stock_mistake_routing():
    detector = _by_text({
        "we binned a whole batch of croissants": {
            "is_concern": True, "concern_type": "waste", "severity": "warning"},
        "almost out of butter please order": {
            "is_concern": True, "concern_type": "low_stock", "severity": "info"},
        "I burnt the first oven load sorry": {
            "is_concern": True, "concern_type": "mistake", "severity": "info"},
        "morning everyone ready to start": {
            "is_concern": False, "concern_type": None},
    })
    msgs = [
        _msg("we binned a whole batch of croissants", mid=1),
        _msg("almost out of butter please order", mid=2),
        _msg("I burnt the first oven load sorry", mid=3),
        _msg("morning everyone ready to start", mid=4),
    ]
    concerns = _run(analyzer._semantic_text_concerns(msgs, [], detector=detector))
    types = sorted(c["concern_type"] for c in concerns)
    assert types == ["low_stock", "mistake", "waste"]


# ── Rules suppression ─────────────────────────────────────────────────────────

def test_rule_suppresses_concern():
    detector = _fake({"is_concern": True, "concern_type": "waste", "severity": "info"})
    rules = [{"concern_type": "waste", "pattern": "test cake", "action": "ignore"}]
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("we threw out the test cake batch as usual")], rules, detector=detector))
    assert concerns == []


def test_rule_for_other_type_does_not_suppress():
    detector = _fake({"is_concern": True, "concern_type": "mistake", "severity": "info"})
    rules = [{"concern_type": "waste", "pattern": "test cake", "action": "ignore"}]
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("dropped the test cake on the floor")], rules, detector=detector))
    assert len(concerns) == 1


# ── Error -> keyword fallback ─────────────────────────────────────────────────

def test_ai_error_falls_back_to_keyword_and_catches():
    # Detector errors; the message has a keyword ("threw") so keyword scan catches it.
    detector = _fake({"is_concern": False, "_error": True})
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("we threw away the old bread")], [], detector=detector))
    assert len(concerns) == 1
    assert concerns[0]["concern_type"] == "waste"


def test_ai_error_keyword_miss_yields_nothing():
    # Detector errors; no keyword present -> keyword fallback finds nothing.
    detector = _fake({"is_concern": False, "_error": True})
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("the cake fell over but we caught it")], [], detector=detector))
    assert concerns == []


# ── Concern-dict shape ────────────────────────────────────────────────────────

def test_concern_dict_shape():
    detector = _fake({"is_concern": True, "concern_type": "mistake",
                      "severity": "critical", "summary": "broke the mixer"})
    concerns = _run(analyzer._semantic_text_concerns(
        [_msg("the mixer broke down completely", mid=42)], [], detector=detector))
    c = concerns[0]
    assert c["source_msg_key"] == "msg:%s:42:mistake" % config.STOCK_CHECKS_CHAT_ID
    assert c["concern_type"] == "mistake"
    assert c["severity"] == "critical"
    assert c["sender_name"] == "Dara"
    assert c["source_chat_id"] == config.STOCK_CHECKS_CHAT_ID
    assert "reported a mistake" in c["description"]
    assert "[Stock Checks]" in c["description"]


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
