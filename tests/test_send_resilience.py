"""A2 (session 58): GM staff-send resilience — retry transient Telegram errors + a burst-alarm on an
outage (the Heng silent-drop class, 2026-06-28). _att_send used to log-and-return-None on any send
error, so a transient Bad-Gateway dropped a sick staffer's menu with no retry and no alert."""
import asyncio
import types

from telegram.error import NetworkError, RetryAfter, Forbidden

from gm_bot import bot


async def _noop(*a, **k):
    return None


# ---- burst-alarm decision (pure) ----------------------------------------------------------------

def test_burst_alarms_at_threshold():
    assert bot._send_fail_should_alarm([0.0, 1.0, 2.0], 3.0, 0.0) is True


def test_burst_below_threshold_no_alarm():
    assert bot._send_fail_should_alarm([0.0, 1.0], 2.0, 0.0) is False


def test_burst_respects_cooldown():
    # 3 recent failures but we alarmed 50s ago (cooldown 900s) → stay quiet
    assert bot._send_fail_should_alarm([1000.0, 1001.0, 1002.0], 1002.0, 952.0) is False


def test_burst_only_counts_recent_window():
    # two old (outside 300s) + one recent → only 1 in-window → no alarm
    assert bot._send_fail_should_alarm([0.0, 1.0, 1000.0], 1000.0, 0.0) is False


# ---- retry behaviour ----------------------------------------------------------------------------

class _FakeBot:
    def __init__(self, script):
        self._script = list(script)   # each item: an Exception to raise, or a value to return
        self.calls = 0

    async def send_message(self, *a, **k):
        self.calls += 1
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _ctx(fakebot):
    return types.SimpleNamespace(bot=fakebot)


def test_retry_then_succeeds(monkeypatch):
    monkeypatch.setattr(bot.asyncio, "sleep", _noop)
    fb = _FakeBot([NetworkError("Bad Gateway"), "SENT"])
    msg, transient = asyncio.run(bot._send_once_retrying(_ctx(fb), 123, "hi"))
    assert msg == "SENT" and transient is False and fb.calls == 2   # retried once, then delivered


def test_persistent_transient_gives_up(monkeypatch):
    monkeypatch.setattr(bot.asyncio, "sleep", _noop)
    fb = _FakeBot([NetworkError("x"), NetworkError("x"), NetworkError("x")])
    msg, transient = asyncio.run(bot._send_once_retrying(_ctx(fb), 123, "hi", attempts=3))
    assert msg is None and transient is True and fb.calls == 3       # tried 3×, flagged as an outage


def test_retry_after_is_honored(monkeypatch):
    monkeypatch.setattr(bot.asyncio, "sleep", _noop)
    fb = _FakeBot([RetryAfter(2), "SENT"])
    msg, transient = asyncio.run(bot._send_once_retrying(_ctx(fb), 123, "hi"))
    assert msg == "SENT" and fb.calls == 2


def test_non_transient_no_retry(monkeypatch):
    monkeypatch.setattr(bot.asyncio, "sleep", _noop)
    fb = _FakeBot([Forbidden("bot was blocked by the user")])
    msg, transient = asyncio.run(bot._send_once_retrying(_ctx(fb), 123, "hi"))
    assert msg is None and transient is False and fb.calls == 1      # not an outage; don't retry
