"""Behavior proof for the two chokepoints the 2026-07-02 observability build added (the structural
guard greps for their wiring; THESE tests drive the actual paths): `_client_alert` (sink-first
client-ops owner alert) and the shared error handler's durable sink mirror."""
import asyncio
import types

from gm_bot import alarms, bot
from shared import error_handler


def _find(kind, needle):
    return [r for r in alarms.recent_alarms(limit=100, include_test=True)
            if r["kind"] == kind and needle in r["body"]]


# ── _client_alert ─────────────────────────────────────────────────────────────
def test_client_alert_persists_then_marks_delivered(monkeypatch):
    alarms.init_alarms_db()

    async def _ok(context, target, body, kb=None, parse_mode=None, **k):
        return types.SimpleNamespace(message_id=1), False
    monkeypatch.setattr(bot, "_send_once_retrying", _ok)
    body = "🚨 utest client-alert delivered"
    asyncio.run(bot._client_alert(types.SimpleNamespace(bot=None), "utest_client_alert", body))
    got = _find("utest_client_alert", "delivered")
    assert got and got[0]["delivered"] is True


def test_client_alert_survives_a_failed_dm(monkeypatch):
    """The whole point: the books-missing class is durable even when the owner DM never lands —
    delivered=FALSE is what detect_undelivered_alarms re-raises within the half-hour."""
    alarms.init_alarms_db()

    async def _fail(context, target, body, kb=None, parse_mode=None, **k):
        return None, True
    monkeypatch.setattr(bot, "_send_once_retrying", _fail)
    body = "🚨 utest client-alert lost DM (books missing)"
    asyncio.run(bot._client_alert(types.SimpleNamespace(bot=None), "utest_client_alert", body,
                                  severity="money"))
    got = _find("utest_client_alert", "lost DM")
    assert got and got[0]["delivered"] is False and got[0]["severity"] == "money"


# ── shared error handler → sink mirror ────────────────────────────────────────
def _crash_ctx(msg="boom"):
    return types.SimpleNamespace(error=RuntimeError(msg))


def test_error_handler_sinks_every_crash_and_acks_throttled_repeats(monkeypatch):
    alarms.init_alarms_db()
    monkeypatch.setattr(error_handler, "notify_monitor", lambda text: True)
    monkeypatch.setattr(error_handler, "_last_dm", {})                     # fresh throttle window
    handler = error_handler.make_error_handler("UTestObsBot")
    asyncio.run(handler(None, _crash_ctx("first crash")))
    first = _find("error:UTestObsBot", "first crash")
    assert first and first[0]["delivered"] is True and first[0]["acked"] is False
    asyncio.run(handler(None, _crash_ctx("second crash within throttle")))
    second = _find("error:UTestObsBot", "second crash")
    assert second and second[0]["acked"] is True, \
        "a throttled repeat must still land in the sink (forensics) but pre-acked (no re-raise)"


def test_error_handler_sink_survives_failed_monitor_dm(monkeypatch):
    alarms.init_alarms_db()
    monkeypatch.setattr(error_handler, "notify_monitor", lambda text: False)
    monkeypatch.setattr(error_handler, "_last_dm", {})
    handler = error_handler.make_error_handler("UTestObsBot2")
    asyncio.run(handler(None, _crash_ctx("crash with monitor down")))
    got = _find("error:UTestObsBot2", "monitor down")
    assert got and got[0]["delivered"] is False, \
        "Monitor down → the crash must survive in the sink undelivered (the sweep re-raises it)"


# ── transient-network noise gate (the 2026-07-02 Monitor-chat screenshot audit) ──
def _net_ctx(msg="httpx.ReadError"):
    from telegram.error import NetworkError
    return types.SimpleNamespace(error=NetworkError(msg))


def test_single_network_blip_never_dms_but_is_recorded_preacked(monkeypatch):
    alarms.init_alarms_db()
    calls = []
    monkeypatch.setattr(error_handler, "notify_monitor", lambda text: calls.append(text) or True)
    monkeypatch.setattr(error_handler, "_last_dm", {})
    monkeypatch.setattr(error_handler, "_net_blips", {})
    handler = error_handler.make_error_handler("UTestNetBot")
    asyncio.run(handler(None, _net_ctx("lone blip")))
    assert calls == [], "a single self-recovering network blip must NOT DM the owner"
    got = _find("error:UTestNetBot", "lone blip")
    assert got and got[0]["acked"] is True, \
        "the blip must still land in the sink (forensics) pre-acked (no undelivered re-raise)"


def test_network_blip_burst_dms_once(monkeypatch):
    alarms.init_alarms_db()
    calls = []
    monkeypatch.setattr(error_handler, "notify_monitor", lambda text: calls.append(text) or True)
    monkeypatch.setattr(error_handler, "_last_dm", {})
    monkeypatch.setattr(error_handler, "_net_blips", {})
    handler = error_handler.make_error_handler("UTestNetBot2")
    for i in range(4):
        asyncio.run(handler(None, _net_ctx("blip %d" % i)))
    assert len(calls) == 1 and "BURST" in calls[0], \
        "≥3 blips in the window must DM exactly once (throttled) — a burst is real degradation"
    burst = _find("error:UTestNetBot2", "BURST")
    assert burst and burst[0]["delivered"] is True


def test_watchdog_cleared_notices_self_ack():
    """Regression lock for the morning-report pile-up (open 2→2→3 of pure ✅ notices): the live
    watchdog's clean-pass self-ack list must include its own cleared-notices."""
    from pathlib import Path
    bot_src = (Path(__file__).resolve().parent.parent / "gm_bot" / "bot.py").read_text(
        encoding="utf-8", errors="replace")
    ack_call = bot_src.split("ack_open_of_kinds([", 1)[1].split("]", 1)[0]
    assert "watchdog_cleared" in ack_call
