"""Global PTB error handler — ONE implementation for every bot (the gm_save_concern lesson:
a crash with no error handler dies SILENTLY; that's how a missing import killed the live
concern recorder 69 times unseen, Jun 2026).

Usage:  app.add_error_handler(make_error_handler("retail"))

What it does on any unhandled handler exception:
- full traceback to that bot's log,
- a throttled ⚠ DM to the owner (one per bot per 30 min; the log keeps every occurrence),
- best-effort answer on the callback so the user's button never just spins.
"""
import asyncio
import logging
import time

from telegram import Update

try:
    from telegram.error import Conflict
except Exception:  # keep this shared handler import-safe across PTB versions
    Conflict = ()  # isinstance(err, ()) is always False → the 409 branch stays inert
try:
    from telegram.error import NetworkError
except Exception:
    NetworkError = ()   # same inert-fallback trick → network blips fall through to the generic branch

import config
from shared.monitor_notify import notify_monitor   # builder/system alarms go via the MONITOR bot, not a client bot

logger = logging.getLogger(__name__)

_THROTTLE_S = 1800
_last_dm: dict = {}     # bot_name → last owner-DM timestamp
_net_blips: dict = {}   # bot_name → recent transient-network-error timestamps (burst window)


def _sink(kind: str, body: str, throttled: bool = False):
    """Durable mirror (observability law, 2026-07-02): EVERY crash lands in the gm_alarms sink, so a
    crash alarm survives a failed Monitor DM (the sentinel sweep re-raises undelivered ones ≤30 min;
    the morning report next day) and Claude can read crashes from ANY bot via scripts/alarms.py — the
    old path was Monitor-DM-or-nothing. A THROTTLED repeat is sunk pre-acked: recorded for forensics,
    but the throttle already decided no re-DM, so it must not re-raise as 'undelivered'. Best-effort."""
    try:
        from gm_bot.alarms import ack_alarm, log_alarm
        aid = log_alarm(kind, body)
        if throttled:
            ack_alarm(aid)
        return aid
    except Exception:
        return None


def _mark_delivered(aid) -> None:
    try:
        from gm_bot.alarms import mark_delivered
        mark_delivered(aid)
    except Exception:
        pass


def make_error_handler(bot_name: str):
    async def _handler(update, context) -> None:
        err = context.error
        # "Message is not modified" = a double-tap / re-tap of the screen already showing —
        # Telegram refuses the identical re-render. Benign no-op: answer the tap quietly,
        # never alarm the owner (first real alert, Jun 11, was exactly this on att:sp).
        if "message is not modified" in str(err).lower():
            logger.info("[%s] no-op re-tap (message not modified)", bot_name)
            try:
                if isinstance(update, Update) and update.callback_query:
                    await update.callback_query.answer()
            except Exception:
                pass
            return
        if isinstance(err, Conflict):
            # 409: a SECOND process is polling THIS bot token (a stray/dev poller) and is
            # stealing live updates. Distinct, loud, separately-throttled owner alert.
            logger.error("[%s] 409 CONFLICT — another process is polling this token: %s", bot_name, err)
            ckey = bot_name + ":conflict"
            body = ("🚨 %s bot: 409 CONFLICT — a SECOND process is polling this token.\n"
                    "A stray/dev poller is stealing live updates (lost check-ins/orders). "
                    "Stop it now, or check for a duplicate service." % bot_name)
            throttled = time.time() - _last_dm.get(ckey, 0.0) < _THROTTLE_S
            aid = _sink("error:%s" % bot_name, body, throttled=throttled)
            if not throttled:
                _last_dm[ckey] = time.time()
                if await asyncio.to_thread(notify_monitor, body):
                    _mark_delivered(aid)
                else:
                    logger.error("[%s] conflict-alert: monitor delivery failed", bot_name)
            return
        if isinstance(err, NetworkError) and not isinstance(err, Conflict):
            # Transient infra blip (httpx ReadError / Bad Gateway): PTB's polling self-recovers and A2
            # retries staff sends — a SINGLE blip is not owner-actionable (the 2026-07-02 screenshot
            # audit: these were most of the Monitor-chat noise). Record it durable + PRE-ACKED
            # (forensics kept; no undelivered re-raise); DM the owner only on a BURST (≥3 in 10 min,
            # throttled) — a burst means the network is actually degraded, not blinking.
            logger.error("[%s] transient network error in handler: %s", bot_name, err)
            now = time.time()
            blips = _net_blips.setdefault(bot_name, [])
            blips.append(now)
            while blips and now - blips[0] > 600:
                blips.pop(0)
            if len(blips) >= 3 and now - _last_dm.get(bot_name + ":net", 0.0) >= _THROTTLE_S:
                _last_dm[bot_name + ":net"] = now
                body = ("⚠ %s bot: network blip BURST — %d transient Telegram errors in ~10 min "
                        "(latest %s: %.120s). Polling self-recovers; check the server network if it persists."
                        % (bot_name, len(blips), type(err).__name__, err))
                aid = _sink("error:%s" % bot_name, body)
                if await asyncio.to_thread(notify_monitor, body):
                    _mark_delivered(aid)
            else:
                _sink("error:%s" % bot_name,
                      "⚠ %s bot: transient network error (self-recovering, not DM'd): %s: %.200s"
                      % (bot_name, type(err).__name__, err), throttled=True)
            return
        logger.error("[%s] UNHANDLED in handler: %s", bot_name, err, exc_info=err)
        try:
            if isinstance(update, Update) and update.callback_query:
                await update.callback_query.answer("⚠ Something broke — the owner has been told.")
        except Exception:
            pass
        where = ""
        try:
            if isinstance(update, Update):
                if update.callback_query:
                    where = " (button: %s)" % (update.callback_query.data or "?")
                elif update.effective_message and update.effective_message.text:
                    where = " (message: %.40s)" % update.effective_message.text
        except Exception:
            pass
        body = ("⚠ %s bot: a flow crashed%s\n%s: %.200s\n(full traceback in the server log; "
                "more crashes in the next 30 min are logged but not re-sent)"
                % (bot_name, where, type(err).__name__, err))
        now = time.time()
        throttled = now - _last_dm.get(bot_name, 0.0) < _THROTTLE_S
        aid = _sink("error:%s" % bot_name, body, throttled=throttled)
        if throttled:
            return
        _last_dm[bot_name] = now
        if await asyncio.to_thread(notify_monitor, body):
            _mark_delivered(aid)
        else:
            logger.error("[%s] error-handler: monitor delivery failed", bot_name)
    return _handler
