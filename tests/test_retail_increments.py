"""A5 (retail increments, 2026-07-03): missed-summary catch-up on boot (ports b2b's
`_startup_summary_check`) + the durable staff-flag record (observability audit #14 —
a failed group post must not lose the AI flag)."""
import asyncio
import datetime
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "telegram_bot"))

import config
import bot as retail_bot          # telegram_bot/bot.py, imported the way run_bot.py does
import staff_monitor
from shared.database import _db, get_bot_meta, set_bot_meta


def test_summary_catchup_decision_is_exact():
    mk = lambda h, m: datetime.datetime(2026, 7, 3, h, m, tzinfo=datetime.timezone.utc)
    H, M = config.SUMMARY_HOUR, config.SUMMARY_MINUTE
    today = "2026-07-03"
    assert not retail_bot._summary_catchup_due(mk(H - 1, 59), None), "before the hour → never due"
    assert not retail_bot._summary_catchup_due(mk(H, M), today), "already sent today → not due"
    assert retail_bot._summary_catchup_due(mk(H, M), None), "past + no record → due"
    assert retail_bot._summary_catchup_due(mk(H + 2, 0), "2026-07-02"), "past + stale record → due"


def test_send_daily_summary_records_the_day(monkeypatch):
    async def fake(bot_, target_date=None):
        pass
    monkeypatch.setattr(retail_bot, "send_production_summary", fake)
    monkeypatch.setattr(retail_bot, "send_fulfillment_list", fake)
    set_bot_meta("retail_last_summary_date", None)
    asyncio.run(retail_bot._send_daily_summary(object()))
    assert get_bot_meta("retail_last_summary_date") == \
        datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def _flag_update_context(send):
    update = SimpleNamespace(message=SimpleNamespace(text="suspicious talk"),
                             effective_user=SimpleNamespace(id=999001))
    context = SimpleNamespace(bot=SimpleNamespace(send_message=send))
    return update, context


def _newest_staff_flag():
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, severity, body, delivered FROM gm_alarms "
                        "WHERE kind='staff_flag' ORDER BY id DESC LIMIT 1")
            return cur.fetchone()


def _cleanup_staff_flags():
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gm_alarms WHERE kind='staff_flag'")


def test_staff_flag_lands_in_the_sink_and_marks_delivered(monkeypatch):
    from gm_bot.alarms import init_alarms_db
    init_alarms_db()
    _cleanup_staff_flags()
    try:
        async def flagged(text, prior):
            return {"action": "urgent", "flag": True, "reason": "test-fraud-hint"}
        monkeypatch.setattr(staff_monitor, "check_staff_message", flagged)
        posts = []

        async def send(chat_id, text_):
            posts.append(text_)
        update, context = _flag_update_context(send)
        asyncio.run(staff_monitor.handle_staff_message(update, context))
        assert posts and "URGENT" in posts[0]
        row = _newest_staff_flag()
        assert row and row["delivered"] is True
        assert row["severity"] == "money" and "test-fraud-hint" in row["body"]
    finally:
        _cleanup_staff_flags()


def test_staff_flag_survives_a_failed_group_post(monkeypatch):
    from gm_bot.alarms import init_alarms_db
    init_alarms_db()
    _cleanup_staff_flags()
    try:
        async def flagged(text, prior):
            return {"action": "alert", "flag": True, "reason": "test-blip"}
        monkeypatch.setattr(staff_monitor, "check_staff_message", flagged)

        async def send(chat_id, text_):
            raise RuntimeError("telegram down")
        update, context = _flag_update_context(send)
        with pytest.raises(RuntimeError):
            asyncio.run(staff_monitor.handle_staff_message(update, context))
        row = _newest_staff_flag()
        assert row and row["delivered"] is False, \
            "the flag must survive durably (undelivered → sentinel re-raises)"
        assert row["severity"] == "warn"
    finally:
        _cleanup_staff_flags()
