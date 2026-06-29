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
import json
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))   # scripts/
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)    # config / secrets / shared
sys.path.insert(0, HERE)    # monitor

from telegram.ext import Application, CommandHandler

import monitor as mon
import integration_audit as ia
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
EVENTS_FILE = os.path.expanduser("~/.twbshop_lane_events.jsonl")  # lane_guard appends here (shared sink)


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
        "/issues — what needs you, with the fix\n"
        "/crossings — recent cross-lane edits\n"
        "/audit — integrator cross-lane sweep (map + no-cross-lane)\n"
        "/alarms — system-health alarms (watchdog / sentinel / send-resilience / config) — moved here off the client GM bot\n\n"
        "I DM you on a service-down OR a cross-lane edit. Silence = healthy.")


async def cmd_alarms(update, context):
    """The SYSTEM-HEALTH alarms (watchdog / sentinel / send-resilience / config-health / audit) — moved off
    the client-facing GM bot to here, the builder's oversight. Reads the durable alarm sink (gm_alarms)."""
    if not _owner(update):
        return
    try:
        from gm_bot import alarms
        rows = alarms.open_alarms()
    except Exception as e:
        await update.message.reply_text("alarms unavailable: %s" % e)
        return
    if not rows:
        await update.message.reply_text("🟢 No open system alarms.")
        return
    lines = ["🔔 OPEN SYSTEM ALARMS (%d):" % len(rows)]
    for a in rows[:20]:
        flag = "" if a["delivered"] else " ⚠undelivered"
        lines.append("#%d [%s] %s%s — %s" % (a["id"], a["severity"], a["kind"], flag,
                                             (a["body"] or "").replace("\n", " ")[:90]))
    await update.message.reply_text("\n".join(lines)[:4000])


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
    rows = mon.lane_board()
    svc = mon.service_health()
    items = mon.issues(rows, svc)
    behind = [r for r in rows if r["behind"] > 0]
    if items:
        icon = {"DOWN": "🔴", "WORK": "✏️", "PUSH": "⬆️"}
        lines = ["❗ NEEDS YOU"]
        for tag, text, fix in items:
            lines.append("%s %s\n   → %s" % (icon.get(tag, "•"), text, fix))
    else:
        lines = ["✅ Nothing needs you — no problems."]
    if behind:
        lines.append("\nℹ️ FYI (optional, not a problem): " +
                     ", ".join("%s %d behind" % (r["name"], r["behind"]) for r in behind) +
                     " — run `pull` in each to get the latest (e.g. guard v3).")
    await update.message.reply_text("\n".join(lines))


def _is_repo_event(e):
    """True if the event's file is a repo-relative path. Out-of-repo scratch files (a Temp diag
    script, a log elsewhere) aren't lane-relevant — skip them even if an old-guard lane logged one."""
    f = e.get("file") or ""
    return not (":" in f or f.startswith("/"))  # a drive letter or leading / => absolute => out-of-repo


def _read_events():
    """Recorded cross-lane events (newest last), out-of-repo scratch writes filtered out."""
    try:
        with open(EVENTS_FILE, encoding="utf-8") as f:
            evs = [json.loads(l) for l in f.read().splitlines() if l.strip()]
        return [e for e in evs if _is_repo_event(e)]
    except Exception:
        return []


def _ev_line(e):
    tag = "🛑 BLOCKED" if e.get("verdict") == "block" else "⚠️ shared"
    return "%s: %s → %s (%s)" % (tag, e.get("lane"), e.get("file"), e.get("concerns"))


async def cmd_crossings(update, context):
    if not _owner(update):
        return
    evs = _read_events()[-10:]
    if not evs:
        await update.message.reply_text("✅ No cross-lane edits recorded.")
        return
    await update.message.reply_text("📛 RECENT CROSS-LANE EDITS\n" + "\n".join(_ev_line(e) for e in evs))


async def cmd_audit(update, context):
    """Run the integrator's cross-lane sweep (fast checks; the heavy --suite is CLI-only)."""
    if not _owner(update):
        return
    rep = ia.audit(with_suite=False)
    text, total = ia.format_report(rep, with_suite=False)
    head = "✅ Integration CLEAN" if total == 0 else "⚠️ Integration: %d finding(s)" % total
    await update.message.reply_text(head + "\n" + text)


async def _events_tick(context):
    """DM the owner about NEW cross-lane edits (lane_guard appends them to EVENTS_FILE). Skips the
    backlog on first run so a restart doesn't replay history. Byte-offset tracked in binary mode."""
    try:
        size = os.path.getsize(EVENTS_FILE)
    except OSError:
        return
    pos = context.bot_data.get("events_pos")
    if pos is None:
        context.bot_data["events_pos"] = size   # skip the backlog on first tick
        return
    if size <= pos:
        return
    try:
        with open(EVENTS_FILE, "rb") as f:
            f.seek(pos)
            chunk = f.read().decode("utf-8", "replace")
            context.bot_data["events_pos"] = f.tell()
    except OSError:
        return
    evs = []
    for ln in chunk.splitlines():
        try:
            evs.append(json.loads(ln))
        except Exception:
            pass
    evs = [e for e in evs if _is_repo_event(e)]   # ignore out-of-repo scratch (old-guard lanes)
    if evs:
        await context.bot.send_message(
            OWNER_TELEGRAM_ID,
            "🚨🔴 CROSS-LANE EDIT 🔴🚨\n" + "\n".join(_ev_line(e) for e in evs) +
            "\n→ pause the named lane(s) if you're working them.")


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
    app.add_handler(CommandHandler("crossings", cmd_crossings))
    app.add_handler(CommandHandler("audit", cmd_audit))
    app.add_handler(CommandHandler("alarms", cmd_alarms))
    app.add_error_handler(make_error_handler("Monitor"))   # crashes are never silent
    app.job_queue.run_repeating(_watch_tick, interval=300, first=15)
    app.job_queue.run_repeating(_events_tick, interval=60, first=20)   # cross-lane edit alerts
    return app


if __name__ == "__main__":
    if not MONITOR_BOT_TOKEN:
        print("ERROR: MONITOR_BOT_TOKEN missing in secrets.py")
        sys.exit(1)
    asyncio.set_event_loop(asyncio.new_event_loop())  # Python 3.14: run_polling needs a current loop
    logger.info("Starting monitor dashboard bot...")
    build_application(MONITOR_BOT_TOKEN).run_polling(drop_pending_updates=True)
