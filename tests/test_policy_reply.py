"""Tests for gm_bot/bot.py _policy_reply_plan and the 72h repeat-notify helpers.
Pure: no DB, no Telegram, no AI."""

from datetime import datetime, timedelta, timezone

from gm_bot import bot

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_to_staff_posts_raw_reply_in_group():
    plan = bot._policy_reply_plan(
        "Thanks Dara, please log those 2 trays on the waste sheet.",
        to_staff=True, sender="Dara", chat_title="Stock Checks", trigger="found 2 stale trays")
    assert plan["destination"] == "group"
    assert plan["text"] == "Thanks Dara, please log those 2 trays on the waste sheet."


def test_owner_preview_when_not_live():
    reply = "Please log the waste and move the rest to the discount shelf."
    plan = bot._policy_reply_plan(
        reply, to_staff=False, sender="Dara", chat_title="Stock Checks",
        trigger="found 2 trays of baguettes still on the rack, all hard now")
    assert plan["destination"] == "owner"
    assert "NOT sent to staff" in plan["text"]
    assert "Stock Checks" in plan["text"]
    assert "Dara posted:" in plan["text"]
    assert reply in plan["text"]


def test_preview_truncates_long_trigger():
    long_trigger = "x" * 500
    plan = bot._policy_reply_plan(
        "ok", to_staff=False, sender="A", chat_title="G", trigger=long_trigger)
    assert ("x" * 200) in plan["text"]
    assert ("x" * 201) not in plan["text"]


def test_preview_tolerates_missing_fields():
    plan = bot._policy_reply_plan(
        "reply", to_staff=False, sender="", chat_title="", trigger="")
    assert plan["destination"] == "owner"
    assert "reply" in plan["text"]


# ── 72h repeat-notify helpers ─────────────────────────────────────────────────

def test_repeat_within_true_inside_window():
    last = (NOW - timedelta(hours=10)).isoformat()
    assert bot._repeat_within(last, NOW, 72) is True


def test_repeat_within_false_outside_window():
    last = (NOW - timedelta(hours=80)).isoformat()
    assert bot._repeat_within(last, NOW, 72) is False


def test_repeat_within_edge_exactly_window():
    last = (NOW - timedelta(hours=72)).isoformat()
    assert bot._repeat_within(last, NOW, 72) is True


def test_repeat_within_handles_missing_or_bad():
    assert bot._repeat_within(None, NOW, 72) is False
    assert bot._repeat_within("", NOW, 72) is False
    assert bot._repeat_within("not-a-date", NOW, 72) is False


def test_repeat_within_ignores_future_timestamp():
    # A clock-skewed future stamp should not count as a repeat.
    last = (NOW + timedelta(hours=1)).isoformat()
    assert bot._repeat_within(last, NOW, 72) is False


def test_humanize_gap():
    assert bot._humanize_gap(timedelta(minutes=40)) == "40 min"
    assert bot._humanize_gap(timedelta(hours=12, minutes=5)) == "12h 5m"
    assert bot._humanize_gap(timedelta(days=2, hours=3)) == "2d 3h"
    assert bot._humanize_gap(timedelta(seconds=-5)) == "0 min"


def test_repeat_alert_text_contents():
    policy = {"group_name": "Log waste before close"}
    txt = bot._repeat_alert_text(policy, "Stock Checks", "waste",
                                 "Dara", "binned 3 trays again", "10h 0m")
    assert "Repeat issue" in txt
    assert "Stock Checks" in txt
    assert "waste" in txt
    assert "Log waste before close" in txt
    assert "Dara" in txt
    assert "10h 0m" in txt
    assert "replied in-group" in txt


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
