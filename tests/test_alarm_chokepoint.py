"""B1b (session 58): the _alarm() chokepoint — a proactive owner alarm persists to the sink FIRST (so it
survives a failed Telegram DM and still reaches Claude), THEN best-effort DMs the owner. The live
watchdog + the A2 send-failure alarm are routed through it."""
import asyncio
import types

from telegram.error import NetworkError

from gm_bot import bot, alarms


async def _noop(*a, **k):
    return None


class _FakeBot:
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    async def send_message(self, *a, **k):
        self.calls += 1
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _find(kind, body):
    return [r for r in alarms.recent_alarms(limit=100, include_test=True)
            if r["kind"] == kind and r["body"] == body]


def test_alarm_persists_and_marks_delivered_via_monitor(monkeypatch):
    alarms.init_alarms_db()
    monkeypatch.setattr(bot, "_monitor_send_sync", lambda text: True)   # the MONITOR bot delivers it
    body = "🚨 chokepoint test — delivered via Monitor bot (ឈឺ emoji-safe)"
    asyncio.run(bot._alarm(types.SimpleNamespace(bot=None), "utest_delivered", body, severity="warn"))
    got = _find("utest_delivered", body)
    assert got and got[0]["delivered"] is True


def test_alarm_persists_even_when_delivery_fails(monkeypatch):
    alarms.init_alarms_db()
    monkeypatch.setattr(bot, "_monitor_send_sync", lambda text: False)  # Monitor send fails
    body = "🚨 chokepoint test — delivery failed but the sink keeps the alarm"
    asyncio.run(bot._alarm(types.SimpleNamespace(bot=None), "utest_undelivered", body, severity="money"))
    got = _find("utest_undelivered", body)
    assert got and got[0]["delivered"] is False and got[0]["severity"] == "money"
