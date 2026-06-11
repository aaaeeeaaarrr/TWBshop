"""Global PTB error handler — ONE implementation for every bot (the gm_save_concern lesson:
a crash with no error handler dies SILENTLY; that's how a missing import killed the live
concern recorder 69 times unseen, Jun 2026).

Usage:  app.add_error_handler(make_error_handler("retail"))

What it does on any unhandled handler exception:
- full traceback to that bot's log,
- a throttled ⚠ DM to the owner (one per bot per 30 min; the log keeps every occurrence),
- best-effort answer on the callback so the user's button never just spins.
"""
import logging
import time

from telegram import Update

import config

logger = logging.getLogger(__name__)

_THROTTLE_S = 1800
_last_dm: dict = {}   # bot_name → last owner-DM timestamp


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
        logger.error("[%s] UNHANDLED in handler: %s", bot_name, err, exc_info=err)
        try:
            if isinstance(update, Update) and update.callback_query:
                await update.callback_query.answer("⚠ Something broke — the owner has been told.")
        except Exception:
            pass
        now = time.time()
        if now - _last_dm.get(bot_name, 0.0) < _THROTTLE_S:
            return
        _last_dm[bot_name] = now
        where = ""
        try:
            if isinstance(update, Update):
                if update.callback_query:
                    where = " (button: %s)" % (update.callback_query.data or "?")
                elif update.effective_message and update.effective_message.text:
                    where = " (message: %.40s)" % update.effective_message.text
        except Exception:
            pass
        try:
            await context.bot.send_message(config.OWNER_TELEGRAM_ID,
                "⚠ %s bot: a flow crashed%s\n%s: %.200s\n(full traceback in the server log; "
                "more crashes in the next 30 min are logged but not re-sent)"
                % (bot_name, where, type(err).__name__, err))
        except Exception as e:
            logger.error("[%s] error-handler DM failed: %s", bot_name, e)
    return _handler
