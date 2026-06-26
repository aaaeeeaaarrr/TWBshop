"""gm_bot.comms — staff comms-responsiveness, DETERMINISTIC via Telegram ids (mention / reply-to / sender id),
not a text guess. Pure logic; GATED OFF until the owner enables it."""
from datetime import datetime, timedelta, timezone

from gm_bot import comms

UTC = timezone.utc
NOW = datetime(2026, 6, 26, 12, 0, tzinfo=UTC)


def _m(i, chat, sender, text, mins_ago, mentions=None, reply_to_sender=None):
    return {"id": i, "chat_id": chat, "sender_id": sender, "text": text,
            "sent_at": NOW - timedelta(minutes=mins_ago),
            "mentioned_ids": mentions or [], "reply_to_sender_id": reply_to_sender}


def test_mention_unanswered_is_flagged():
    msgs = [_m(1, -1, 999, "Norin please check the fridge", 45, mentions=[101]),  # boss @mentions staffer 101
            _m(2, -1, 102, "ok on my way", 40)]                                    # a DIFFERENT staffer answers
    res = comms.find_unanswered(msgs, {101, 102}, NOW, window_min=30)
    assert len(res) == 1 and res[0]["staff_id"] == 101 and res[0]["age_min"] >= 30   # 101 never replied


def test_answered_is_clear():
    msgs = [_m(1, -1, 999, "Norin?", 45, mentions=[101]), _m(2, -1, 101, "yes, here", 20)]
    assert comms.find_unanswered(msgs, {101}, NOW, 30) == []                         # 101 replied → nothing


def test_reply_to_a_staffer_unanswered():
    msgs = [_m(1, -1, 999, "did you finish the report?", 50, reply_to_sender=102)]   # replied to 102's message
    res = comms.find_unanswered(msgs, {102}, NOW, 30)
    assert len(res) == 1 and res[0]["staff_id"] == 102


def test_within_window_not_yet_flagged():
    msgs = [_m(1, -1, 999, "Norin?", 10, mentions=[101])]                            # only 10 min ago
    assert comms.find_unanswered(msgs, {101}, NOW, 30) == []


def test_self_mention_ignored():
    msgs = [_m(1, -1, 101, "reminding myself @Norin", 45, mentions=[101])]           # 101 mentioned themselves
    assert comms.find_unanswered(msgs, {101}, NOW, 30) == []


def test_ops_message_stores_structured_fields():
    """The data capture (the fix per the owner's insight): save_ops_message now persists reply_to + the
    @-mentioned ids, so detection is deterministic instead of a text guess."""
    import shared.database as db
    db.init_ops_db()
    chat, mid = -99001, 778001
    with db._db() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM ops_messages WHERE chat_id=%s", (chat,))
    try:
        db.save_ops_message(chat, mid, "T", 999, "Boss", "Norin?", None, None,
                            reply_to_msg_id=778000, mentioned_ids=[101, 102])
        with db._db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT reply_to_msg_id, mentioned_ids FROM ops_messages "
                            "WHERE chat_id=%s AND message_id=%s", (chat, mid))
                r = cur.fetchone()
        assert r["reply_to_msg_id"] == 778000 and r["mentioned_ids"] == [101, 102]
    finally:
        with db._db() as c:
            with c.cursor() as cur:
                cur.execute("DELETE FROM ops_messages WHERE chat_id=%s", (chat,))


def test_escalation_stages():
    assert comms.stage_for(45, nudged=False, escalated=False) == "nudge"
    assert comms.stage_for(45, nudged=True, escalated=False) == "none"              # already nudged
    assert comms.stage_for(120, nudged=True, escalated=False) == "escalate"
    assert comms.stage_for(120, nudged=True, escalated=True) == "none"             # already escalated
    assert comms.stage_for(10, nudged=False, escalated=False) == "none"           # not yet due
