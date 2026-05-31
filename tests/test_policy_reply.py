"""Tests for gm_bot/bot.py _policy_reply_plan — the owner-gate routing for live
policy replies. Pure: no DB, no Telegram, no AI."""

from gm_bot import bot


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
