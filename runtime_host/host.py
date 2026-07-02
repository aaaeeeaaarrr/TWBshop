"""runtime_host.host — ONE process, N tenants' Telegram bot applications (S60 A6, INERT).

Kills the process-per-bot wall (~30 clients on a 2 GB box → hundreds): each tenant keeps its own
token/handlers/error-handler; they share one asyncio loop and the one pooled DB. Design + the
"what it is NOT yet" honesty → docs/RUNTIME_HOST_DESIGN.md. Nothing schedules or runs this today —
the first real user is the onboarding demo / tenant #2.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class TenantSpec:
    """One tenant's bot, as CONFIG (the platform law — no per-tenant code):
    registrar(app, org_id) attaches the tenant's handlers (e.g. adapters.telegram_onboarding.register
    partial'd with its chat ids)."""
    org_id: str
    bot_token: str
    registrar: Callable


def build_apps(tenants: list) -> tuple[list, list]:
    """PURE assembly (offline-testable): specs → [(org_id, Application)], skipping — and
    reporting — any spec that fails to build. Fail-soft: the fleet must not die on one
    tenant's typo'd token; the skipped list is the caller's alarm payload."""
    from telegram.ext import Application

    from shared.error_handler import make_error_handler

    apps, skipped = [], []
    for t in tenants:
        try:
            app = Application.builder().token(t.bot_token).build()
            app.add_error_handler(make_error_handler("host:%s" % t.org_id))
            t.registrar(app, t.org_id)
            apps.append((t.org_id, app))
        except Exception as e:
            logger.error("tenant %s skipped: %s", t.org_id, e)
            skipped.append((t.org_id, str(e)))
    return apps, skipped


async def run(tenants: list, stop_event: asyncio.Event = None) -> None:
    """Start every tenant app on THIS loop (initialize → start → start_polling), beat liveness,
    idle until stop_event, then stop in reverse. PTB's run_polling owns a loop, so the host uses
    the manual lifecycle — the documented multi-application pattern."""
    from core import heartbeat

    apps, skipped = build_apps(tenants)
    if skipped:
        logger.error("runtime host: %d tenant(s) skipped: %s", len(skipped), skipped)
    started = []
    try:
        for org_id, app in apps:
            await app.initialize()
            await app.start()
            await app.updater.start_polling()
            started.append((org_id, app))
            logger.info("tenant %s polling", org_id)
        stop_event = stop_event or asyncio.Event()
        while not stop_event.is_set():
            for org_id, _ in started:
                try:
                    heartbeat.beat(org_id, "host:%s" % org_id, 5, phase="ok")
                except Exception:
                    pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=120)
            except asyncio.TimeoutError:
                pass
    finally:
        for org_id, app in reversed(started):
            try:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception:
                logger.exception("tenant %s shutdown error", org_id)
