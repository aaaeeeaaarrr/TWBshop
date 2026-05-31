"""Tests for gm_bot/lateness.py — pay-back ladder decision logic + text builders.
Pure: no DB, no Telegram, no AI."""

from datetime import datetime, timedelta, timezone

from gm_bot import lateness

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _ago(**kw):
    return NOW - timedelta(**kw)


# ── decide_lateness_action ────────────────────────────────────────────────────

def test_awaiting_waits_before_30min():
    action = lateness.decide_lateness_action(
        lateness.AWAITING_PAYBACK, asked_senior_at=_ago(minutes=10),
        asked_group_at=None, now=NOW)
    assert action == "wait"


def test_awaiting_asks_group_at_30min():
    action = lateness.decide_lateness_action(
        lateness.AWAITING_PAYBACK, asked_senior_at=_ago(minutes=30),
        asked_group_at=None, now=NOW)
    assert action == "ask_group"


def test_group_asked_waits_before_24h():
    action = lateness.decide_lateness_action(
        lateness.GROUP_ASKED, asked_senior_at=_ago(hours=2),
        asked_group_at=_ago(hours=10), now=NOW)
    assert action == "wait"


def test_group_asked_escalates_at_24h():
    action = lateness.decide_lateness_action(
        lateness.GROUP_ASKED, asked_senior_at=_ago(hours=25),
        asked_group_at=_ago(hours=24), now=NOW)
    assert action == "escalate"


def test_resolved_and_escalated_are_inert():
    assert lateness.decide_lateness_action(
        lateness.RESOLVED, _ago(hours=99), _ago(hours=99), NOW) == "none"
    assert lateness.decide_lateness_action(
        lateness.ESCALATED, _ago(hours=99), _ago(hours=99), NOW) == "none"


def test_missing_timestamps_wait():
    assert lateness.decide_lateness_action(
        lateness.AWAITING_PAYBACK, None, None, NOW) == "wait"
    assert lateness.decide_lateness_action(
        lateness.GROUP_ASKED, None, None, NOW) == "wait"


# ── Text builders ─────────────────────────────────────────────────────────────

def test_ask_senior_text():
    out = lateness.ask_senior_text("Boss [tag]", "Seth [tag]")
    assert out == "Boss [tag] when will Seth [tag] pay back the missed time?"


def test_ask_group_text():
    out = lateness.ask_group_text("Seth [tag]")
    assert out == "Does anyone know when Seth [tag] will be paying back the missed time?"


def test_escalation_text_contents():
    out = lateness.escalation_text("Supervisors", "Seth", "Boss TT", "Seth came late again")
    assert "Pay-back unanswered" in out
    assert "Supervisors" in out
    assert "Seth" in out
    assert "Boss TT" in out
    assert "Seth came late again" in out


def test_escalation_text_optional_fields():
    out = lateness.escalation_text("Management", "X", None, None)
    assert "Reported by" not in out
    assert "Original" not in out


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
