"""run_automations.py — the scheduled auto-dispatch runner for automation recipes.

Every INTERVAL minutes it sends each OPTED-IN tenant's FIRING recipes to their configured targets
(core.automations.dispatch), debounced so nothing spams. DOUBLY safe by default: a tenant is worked ONLY if
it has explicitly turned on `automations.auto_dispatch` AND has targets set — so this runner is inert until
the owner opts in. A dedicated, channel-agnostic runner — it does NOT touch the gm bot (no HIGH-RISK restart).

Run: TWBSHOP_ENV=prod python run_automations.py  (systemd: twbshop-automations).
"""
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: F401 — presence check; missing secrets.py → the standard "say pull" path

if not os.environ.get("TWBSHOP_ENV"):
    print("TWBSHOP_ENV not set (prod|staging). e.g.  TWBSHOP_ENV=prod python run_automations.py")
    sys.exit(1)

os.makedirs("logs", exist_ok=True)
handler = RotatingFileHandler("logs/automations.log", maxBytes=5_000_000, backupCount=3)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[handler, logging.StreamHandler()])
logger = logging.getLogger("automations")
try:                                            # redact bot tokens from logs — this runner resolves live tokens
    from shared.log_redact import install_log_hygiene
    install_log_hygiene()
except Exception:
    pass

from core.db import init_core_db
from core import automations as au

INTERVAL_MIN = int(os.environ.get("AUTOMATIONS_INTERVAL_MIN", "15"))


def _token_for(org_id):
    """The tenant's bot token: the platform secret store first (multi-tenant), else config.GM_BOT_TOKEN for TWB."""
    try:
        from core.db import get_org_secret
        t = get_org_secret(org_id, "bot_token")
        if t:
            return t
    except Exception:
        pass
    return getattr(config, "GM_BOT_TOKEN", "") if org_id == "twb" else ""


def tick():
    """One pass: dispatch for every opted-in tenant. Returns the total alerts sent (for logging/tests)."""
    total = 0
    for org_id in au.orgs_with_auto_dispatch():
        token = _token_for(org_id)
        if not token:
            logger.warning("[automations] %s opted in but no bot token — skipped", org_id)
            continue
        try:
            sent = au.dispatch(org_id, au.token_sender(token))
        except Exception:
            logger.exception("[automations] dispatch failed for %s", org_id)
            continue
        if sent:
            logger.info("[automations] %s sent %d: %s", org_id, len(sent),
                        ", ".join(s["recipe"] for s in sent))
        total += len(sent)
    return total


def main():
    init_core_db()
    logger.info("Automations runner up — every %d min (opted-in tenants only)", INTERVAL_MIN)
    try:
        from core.heartbeat import init_heartbeats_db
        init_heartbeats_db()
    except Exception:
        logger.exception("init_heartbeats_db failed (non-fatal)")
    while True:
        # observability law: the runner beats per tick so a wedged/dead service alarms via the sweep
        try:
            from core.heartbeat import beat
            beat("twb", "svc:automations_tick", INTERVAL_MIN * 3, phase="start")
        except Exception:
            pass
        try:
            tick()
            try:
                from core.heartbeat import beat
                beat("twb", "svc:automations_tick", INTERVAL_MIN * 3, phase="ok")
            except Exception:
                pass
        except Exception:
            logger.exception("tick failed")
            try:
                from core.heartbeat import beat
                beat("twb", "svc:automations_tick", INTERVAL_MIN * 3, phase="err", err="tick failed (see log)")
            except Exception:
                pass
        time.sleep(INTERVAL_MIN * 60)


if __name__ == "__main__":
    main()
