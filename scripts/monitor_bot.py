#!/usr/bin/env python3
"""monitor_bot.py — interactive owner-only dashboard over @TWB_Monitor_bot.

Graduates the send-only watcher into a bot you QUERY. OWNER ONLY — every other sender is ignored
(kills the random-spam class). Commands:
  /board   - lanes: dirty / ahead / behind  (so you never close a window with unsaved work)
  /health  - the twbshop-* services
  /issues  - only what needs you, each with a one-line FIX
  /start /help - this list
It also DMs the owner when a service that was up goes down (a JobQueue tick — same spam-free rule:
silence = healthy). READ-ONLY: it shells git + ssh `systemctl is-active`; it never writes git,
deploys, or restarts anything. Reuses scripts/monitor.py for all data (one source of truth).

Run:  python scripts/monitor_bot.py     (ONE poller per token — do NOT also run `monitor.py --watch`)
"""
import asyncio
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))   # scripts/
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)    # config / secrets / shared
sys.path.insert(0, HERE)    # monitor

from telegram.ext import Application, CommandHandler

import monitor as mon
from shared.error_handler import make_error_handler

try:
    from config import OWNER_TELEGRAM_ID
except Exception:
    OWNER_TELEGRAM_ID = 0
try:
    from secrets import MONITOR_BOT_TOKEN
except Exception:
    MONITOR_BOT_TOKEN = ""

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("monitor_bot")


def _owner(update) -> bool:
    u = update.effective_user
    return bool(u and u.id == OWNER_TELEGRAM_ID)


def _fmt_lanes(rows) -> str:
    out = ["📋 LANES"]
    for r in rows:
        flags = []
        if r["dirty"]:
            flags.append("%d dirty" % r["dirty"])
        if r["ahead"]:
            flags.append("%d ahead" % r["ahead"])
        if r["behind"]:
            flags.append("%d behind" % r["behind"])
        out.append("• %s (%s) — %s" % (r["name"], r["branch"], ", ".join(flags) or "clean"))
    return "\n".join(out)


def _fmt_services(svc) -> str:
    if not svc:
        return "🩺 SERVICES: (ssh unavailable)"
    out = ["🩺 SERVICES"]
    for name, state in svc.items():
        if state == "active":
            mark = "🟢"
        elif name in mon.EXPECTED_INACTIVE:
            mark = "⚪"
        else:
            mark = "🔴"
        tail = " (off on purpose)" if (name in mon.EXPECTED_INACTIVE and state != "active") else ""
        out.append("%s %s — %s%s" % (mark, name, state, tail))
    return "\n".join(out)


async def cmd_start(update, context):
    if not _owner(update):
        return
    await update.message.reply_text(
        "🖥 TWB Monitor — your dashboard.\n"
        "/board — lanes (dirty / ahead / behind)\n"
        "/health — the services\n"
        "/issues — what needs you, with the fix\n\n"
        "I also DM you if a live service goes down. Silence = healthy.")


async def cmd_board(update, context):
    if not _owner(update):
        return
    await update.message.reply_text(_fmt_lanes(mon.lane_board()))


async def cmd_health(update, context):
    if not _owner(update):
        return
    await update.message.reply_text(_fmt_services(mon.service_health()))


async def cmd_issues(update, context):
    if not _owner(update):
        return
    items = mon.issues(mon.lane_board(), mon.service_health())
    if not items:
        await update.message.reply_text("✅ Nothing needs you — all clean.")
        return
    icon = {"DOWN": "🔴", "WORK": "✏️", "PUSH": "⬆️"}
    lines = ["❗ NEEDS YOU"]
    for tag, text, fix in items:
        lines.append("%s %s\n   → %s" % (icon.get(tag, "•"), text, fix))
    await update.message.reply_text("\n".join(lines))


async def _watch_tick(context):
    """JobQueue: DM the owner only when the service-down set CHANGES (spam-free; silence = healthy)."""
    try:
        anoms = mon.anomalies(mon.lane_board(), mon.service_health())
    except Exception:
        return
    sig = "|".join(sorted(anoms))
    if sig != context.bot_data.get("last_sig"):
        if anoms:
            await context.bot.send_message(OWNER_TELEGRAM_ID,
                                           "🔴 TWB monitor — needs attention:\n- " + "\n- ".join(anoms))
        elif context.bot_data.get("last_sig"):
            await context.bot.send_message(OWNER_TELEGRAM_ID, "🟢 TWB monitor: all clear.")
        context.bot_data["last_sig"] = sig


async def _on_start(app):
    try:
        await app.bot.send_message(
            OWNER_TELEGRAM_ID,
            "🖥 TWB Monitor dashboard online. Try /board, /health, /issues. "
            "I'll DM you if a service drops — silence = healthy.")
    except Exception:
        pass


def build_application(token):
    app = Application.builder().token(token).post_init(_on_start).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("board", cmd_board))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("issues", cmd_issues))
    app.add_error_handler(make_error_handler("Monitor"))   # crashes are never silent
    app.job_queue.run_repeating(_watch_tick, interval=300, first=15)
    return app


if __name__ == "__main__":
    if not MONITOR_BOT_TOKEN:
        print("ERROR: MONITOR_BOT_TOKEN missing in secrets.py")
        sys.exit(1)
    asyncio.set_event_loop(asyncio.new_event_loop())  # Python 3.14: run_polling needs a current loop
    logger.info("Starting monitor dashboard bot...")
    build_application(MONITOR_BOT_TOKEN).run_polling(drop_pending_updates=True)
